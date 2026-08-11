"""Local, dependency-light document extraction and BM25 retrieval for the web app."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import zipfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Iterable
from xml.etree import ElementTree


SUPPORTED = {".txt", ".md", ".markdown", ".csv", ".json", ".html", ".htm", ".docx", ".pdf"}
ASCII_WORD = re.compile(r"[A-Za-z0-9_]+")
CJK_RUN = re.compile(r"[\u3400-\u9fff]+")
INDEX_FORMAT_VERSION = 2
FULL_TEXT_DOCUMENT_MAX_CHARS = 24_000
FULL_TEXT_REQUEST_MAX_CHARS = 48_000
REQUESTED_FULL_TEXT_DOCUMENT_MAX_CHARS = 80_000
REQUESTED_FULL_TEXT_TOTAL_MAX_CHARS = 120_000


class TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if value:
            self.parts.append(value)


def decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "utf-16"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def plain_units(path: Path) -> list[tuple[str, str]]:
    text = decode_text(path.read_bytes())
    if path.suffix.lower() in {".html", ".htm"}:
        parser = TextHTMLParser()
        parser.feed(text)
        text = "\n".join(parser.parts)
    return [(f"line {index}", line) for index, line in enumerate(text.splitlines(), 1) if line.strip()]


def docx_units(path: Path) -> list[tuple[str, str]]:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    units: list[tuple[str, str]] = []
    for index, paragraph in enumerate(root.iter(f"{namespace}p"), 1):
        text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t")).strip()
        if text:
            units.append((f"paragraph {index}", text))
    return units


def pdf_units(path: Path) -> list[tuple[str, str]]:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise RuntimeError("要读取PDF，请先运行：python -m pip install -r requirements.txt") from exc
    reader = PdfReader(str(path))
    units: list[tuple[str, str]] = []
    for index, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        if text:
            units.append((f"page {index}", text))
    if not units:
        raise RuntimeError("无法读取PDF中的文字；如果是扫描图片，请先进行文字识别")
    return units


def extract_units(path: Path) -> list[tuple[str, str]]:
    if path.suffix.lower() == ".docx":
        return docx_units(path)
    if path.suffix.lower() == ".pdf":
        return pdf_units(path)
    return plain_units(path)


def chunk_units(
    units: Iterable[tuple[str, str]], max_chars: int = 1800, overlap_chars: int = 180
) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    current: list[str] = []
    labels: list[str] = []
    length = 0

    def flush() -> None:
        nonlocal current, labels, length
        if not current:
            return
        locator = labels[0] if labels[0] == labels[-1] else f"{labels[0]}–{labels[-1]}"
        text = "\n".join(current).strip()
        if text:
            chunks.append((locator, text))
        tail = text[-overlap_chars:] if overlap_chars else ""
        current = [tail] if tail else []
        labels = [labels[-1]] if tail else []
        length = len(tail)

    for label, text in units:
        text = re.sub(r"[ \t]+", " ", text).strip()
        if not text:
            continue
        if len(text) > max_chars:
            flush()
            step = max(1, max_chars - overlap_chars)
            for start in range(0, len(text), step):
                piece = text[start : start + max_chars]
                chunks.append((label, piece))
                if start + max_chars >= len(text):
                    break
            current, labels, length = [], [], 0
            continue
        projected = length + len(text) + (1 if current else 0)
        if current and projected > max_chars:
            flush()
        current.append(text)
        labels.append(label)
        length += len(text) + (1 if length else 0)
    flush()
    return chunks


def full_document(units: Iterable[tuple[str, str]]) -> tuple[str, str, int]:
    """Preserve a document's extracted reading order and location labels."""
    cleaned: list[tuple[str, str]] = []
    character_count = 0
    for label, text in units:
        text = re.sub(r"[ \t]+", " ", text).strip()
        if text:
            cleaned.append((label, text))
            character_count += len(text)
    if not cleaned:
        return "", "", 0
    locator = cleaned[0][0] if len(cleaned) == 1 else f"{cleaned[0][0]}–{cleaned[-1][0]}"
    text = "\n\n".join(f"[{label}]\n{value}" for label, value in cleaned)
    return locator, text, character_count


def _write_jsonl_atomic(path: Path, records: Iterable[dict]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    os.replace(temporary, path)


def build_index(corpus_dir: Path, index_dir: Path, max_file_bytes: int) -> dict:
    """Rebuild the generated index from files stored under corpus_dir."""
    corpus_dir.mkdir(parents=True, exist_ok=True)
    index_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    all_chunks: list[dict] = []
    documents: list[dict] = []
    for candidate in sorted(corpus_dir.rglob("*")):
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        try:
            relative = resolved.relative_to(corpus_dir.resolve()).as_posix()
        except ValueError:
            continue
        stat = resolved.stat()
        suffix = resolved.suffix.lower()
        record = {
            "path": relative,
            "extension": suffix,
            "size": stat.st_size,
            "status": "pending",
            "source_id": None,
            "chunk_count": 0,
            "character_count": 0,
            "error": None,
        }
        if suffix not in SUPPORTED:
            record["status"] = "unsupported"
            manifest.append(record)
            continue
        if stat.st_size > max_file_bytes:
            record["status"] = "skipped"
            record["error"] = "file exceeds local web app size limit"
            manifest.append(record)
            continue
        try:
            source_id = sha256(resolved)[:16]
            units = extract_units(resolved)
            document_locator, document_text, character_count = full_document(units)
            chunks = chunk_units(units)
            record["source_id"] = source_id
            record["chunk_count"] = len(chunks)
            record["character_count"] = character_count
            record["status"] = "extracted" if chunks else "empty"
            if document_text:
                documents.append(
                    {
                        "source_id": source_id,
                        "path": relative,
                        "extension": suffix,
                        "locator": document_locator,
                        "character_count": character_count,
                        "text": document_text,
                    }
                )
            for index, (locator, text) in enumerate(chunks, 1):
                all_chunks.append(
                    {
                        "source_id": source_id,
                        "path": relative,
                        "extension": suffix,
                        "chunk": index,
                        "locator": locator,
                        "text": text,
                    }
                )
        except Exception as exc:
            record["status"] = "error"
            record["error"] = f"{type(exc).__name__}: {exc}"
        manifest.append(record)
    _write_jsonl_atomic(index_dir / "manifest.jsonl", manifest)
    _write_jsonl_atomic(index_dir / "chunks.jsonl", all_chunks)
    _write_jsonl_atomic(index_dir / "documents.jsonl", documents)
    report = {
        "index_version": INDEX_FORMAT_VERSION,
        "full_text_max_chars": FULL_TEXT_DOCUMENT_MAX_CHARS,
        "file_count": len(manifest),
        "extracted_files": sum(item["status"] == "extracted" for item in manifest),
        "chunk_count": len(all_chunks),
        "files": [
            {
                "path": item["path"],
                "extension": item["extension"],
                "size": item["size"],
                "status": item["status"],
                "chunk_count": item["chunk_count"],
                "character_count": item["character_count"],
                "error": item["error"],
            }
            for item in manifest
        ],
        "issues": [
            {"path": item["path"], "status": item["status"], "error": item["error"]}
            for item in manifest
            if item["status"] not in {"extracted", "empty"}
        ],
    }
    temporary = index_dir / "report.json.tmp"
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, index_dir / "report.json")
    return report


def index_status(index_dir: Path) -> dict:
    empty = {
        "index_version": INDEX_FORMAT_VERSION,
        "full_text_max_chars": FULL_TEXT_DOCUMENT_MAX_CHARS,
        "file_count": 0,
        "extracted_files": 0,
        "chunk_count": 0,
        "files": [],
        "issues": [],
    }
    report = index_dir / "report.json"
    if not report.is_file():
        return empty
    try:
        value = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty
    if not isinstance(value, dict):
        return empty
    if not isinstance(value.get("files"), list):
        files: list[dict] = []
        manifest_path = index_dir / "manifest.jsonl"
        if manifest_path.is_file():
            try:
                with manifest_path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        item = json.loads(line)
                        if isinstance(item, dict) and isinstance(item.get("path"), str):
                            files.append(
                                {
                                    "path": item["path"],
                                    "extension": item.get("extension", ""),
                                    "size": item.get("size", 0),
                                    "status": item.get("status", "unknown"),
                                    "chunk_count": item.get("chunk_count", 0),
                                    "character_count": item.get("character_count", 0),
                                    "error": item.get("error"),
                                }
                            )
            except (OSError, json.JSONDecodeError):
                files = []
        value["files"] = files
    return value


def tokenize(text: str) -> list[str]:
    tokens = [item.lower() for item in ASCII_WORD.findall(text)]
    for run in CJK_RUN.findall(text):
        tokens.extend(run)
        tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
    return tokens


def load_documents(index_dir: Path) -> list[dict]:
    document_file = index_dir / "documents.jsonl"
    if not document_file.is_file():
        return []
    documents: list[dict] = []
    with document_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            if (
                isinstance(item, dict)
                and isinstance(item.get("path"), str)
                and isinstance(item.get("text"), str)
            ):
                documents.append(item)
    return documents


def match_requested_documents(index_dir: Path, query: str, select_all: bool = False) -> list[str]:
    """Return paths explicitly named by the user, or the sole available document."""
    documents = load_documents(index_dir)
    if select_all:
        return [str(item["path"]) for item in documents]

    normalized_query = query.casefold().replace("\\", "/")
    direct_matches: list[str] = []
    for item in documents:
        path = str(item["path"])
        normalized_path = path.casefold().replace("\\", "/")
        name = PurePosixPath(normalized_path).name
        stem = PurePosixPath(normalized_path).stem
        if any(
            len(value) >= 2 and value in normalized_query
            for value in (normalized_path, name, stem)
        ):
            direct_matches.append(path)
    if direct_matches:
        return direct_matches

    bracketed_names = [value.strip() for value in re.findall(r"《([^》]+)》", query) if value.strip()]
    requested = [value.casefold().replace("\\", "/") for value in bracketed_names]
    matches: list[str] = []
    for item in documents:
        path = str(item["path"])
        normalized_path = path.casefold().replace("\\", "/")
        name = Path(path).name.casefold()
        stem = Path(path).stem.casefold()
        candidates = {normalized_path, name, stem}
        if requested:
            matched = any(
                value in candidates or any(value == Path(candidate).stem.casefold() for candidate in candidates)
                for value in requested
            )
        else:
            matched = any(len(value) >= 2 and value in normalized_query for value in candidates)
        if matched:
            matches.append(path)
    if matches:
        return matches
    if not requested and len(documents) == 1:
        return [str(documents[0]["path"])]
    return []


def search_index(
    index_dir: Path,
    query: str,
    top: int = 8,
    full_text_max_chars: int = FULL_TEXT_DOCUMENT_MAX_CHARS,
    full_text_total_chars: int = FULL_TEXT_REQUEST_MAX_CHARS,
    force_full_paths: Iterable[str] | None = None,
    excerpts_only: bool = False,
    requested_full_document_max_chars: int = REQUESTED_FULL_TEXT_DOCUMENT_MAX_CHARS,
    requested_full_total_chars: int = REQUESTED_FULL_TEXT_TOTAL_MAX_CHARS,
    restrict_paths: Iterable[str] | None = None,
) -> list[dict]:
    documents_list = load_documents(index_dir)
    documents_by_id = {
        str(item.get("source_id", "")): item
        for item in documents_list
        if str(item.get("source_id", ""))
    }
    requested_paths = {
        str(path).casefold().replace("\\", "/") for path in (force_full_paths or [])
    }
    if requested_paths:
        selected = [
            item
            for item in documents_list
            if str(item["path"]).casefold().replace("\\", "/") in requested_paths
        ]
        missing = requested_paths - {
            str(item["path"]).casefold().replace("\\", "/") for item in selected
        }
        if missing:
            raise ValueError(f"文献库中未找到：{', '.join(sorted(missing))}")
        total_chars = sum(len(str(item["text"])) for item in selected)
        for item in selected:
            if len(str(item["text"])) > max(0, requested_full_document_max_chars):
                raise ValueError(
                    f"《{item['path']}》全文超出本次可处理范围。请分篇、分章节提问，或改为只查相关部分。"
                )
        if total_chars > max(0, requested_full_total_chars):
            raise ValueError("所选文献全文总量超出本次可处理范围。请减少文献数量或分次提问。")
        return [
            {
                "source_id": str(item.get("source_id", "")),
                "path": item["path"],
                "extension": item.get("extension", ""),
                "chunk": 0,
                "locator": item.get("locator", "全文"),
                "text": item["text"],
                "content_mode": "full",
                "score": 0.0,
            }
            for item in selected
        ]

    chunk_file = index_dir / "chunks.jsonl"
    if not chunk_file.is_file():
        return []
    chunks: list[dict] = []
    with chunk_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                item = json.loads(line)
                if isinstance(item.get("text"), str):
                    chunks.append(item)
    restricted_paths = [
        str(path).casefold().replace("\\", "/") for path in (restrict_paths or [])
    ]
    if restricted_paths:
        restricted_set = set(restricted_paths)
        chunks = [
            item
            for item in chunks
            if str(item.get("path", "")).casefold().replace("\\", "/") in restricted_set
        ]
    query_tokens = tokenize(query)
    if not chunks or not query_tokens:
        return []
    tokenized = [tokenize(item["text"]) for item in chunks]
    document_frequency: Counter[str] = Counter()
    for terms in tokenized:
        document_frequency.update(set(terms))
    average_length = sum(len(terms) for terms in tokenized) / len(tokenized)
    query_counts = Counter(query_tokens)
    ranked: list[tuple[float, dict]] = []
    k1, b = 1.5, 0.75
    for item, terms in zip(chunks, tokenized):
        frequencies = Counter(terms)
        length_norm = 1 - b + b * len(terms) / max(average_length, 1)
        score = 0.0
        for term, query_weight in query_counts.items():
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            document_count = document_frequency[term]
            inverse = math.log(1 + (len(chunks) - document_count + 0.5) / (document_count + 0.5))
            score += query_weight * inverse * (frequency * (k1 + 1)) / (frequency + k1 * length_norm)
        if query in item["text"]:
            score += 5.0
        if score:
            ranked.append((score, item))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    if restricted_paths:
        primary: list[tuple[float, dict]] = []
        primary_keys: set[tuple[str, int]] = set()
        for requested_path in restricted_paths:
            candidate = next(
                (
                    pair
                    for pair in ranked
                    if str(pair[1].get("path", "")).casefold().replace("\\", "/")
                    == requested_path
                ),
                None,
            )
            if candidate is None:
                fallback = next(
                    (
                        item
                        for item in chunks
                        if str(item.get("path", "")).casefold().replace("\\", "/")
                        == requested_path
                    ),
                    None,
                )
                if fallback is not None:
                    candidate = (0.0, fallback)
            if candidate is not None:
                key = (str(candidate[1].get("source_id", "")), int(candidate[1].get("chunk", 0)))
                if key not in primary_keys:
                    primary.append(candidate)
                    primary_keys.add(key)
        ranked = primary + [
            pair
            for pair in ranked
            if (str(pair[1].get("source_id", "")), int(pair[1].get("chunk", 0)))
            not in primary_keys
        ]
    results: list[dict] = []
    full_text_sources: set[str] = set()
    full_text_chars = 0
    for score, item in ranked:
        source_id = str(item.get("source_id", ""))
        if source_id in full_text_sources:
            continue
        document = documents_by_id.get(source_id)
        document_chars = int(document.get("character_count", 0)) if document else 0
        document_text = str(document.get("text", "")) if document else ""
        can_use_full_text = (
            not excerpts_only
            and bool(document_text)
            and document_chars <= max(0, full_text_max_chars)
            and full_text_chars + len(document_text) <= max(0, full_text_total_chars)
        )
        if can_use_full_text:
            result = {
                "source_id": source_id,
                "path": document["path"],
                "extension": document.get("extension", item.get("extension", "")),
                "chunk": 0,
                "locator": document.get("locator", "全文"),
                "text": document_text,
                "content_mode": "full",
                "score": round(score, 4),
            }
            full_text_sources.add(source_id)
            full_text_chars += len(document_text)
            results.append(result)
        else:
            result = dict(item)
            result["score"] = round(score, 4)
            result["text"] = result["text"][:2200]
            result["content_mode"] = "excerpt"
            results.append(result)
        if len(results) >= max(1, top, len(restricted_paths)):
            break
    return results
