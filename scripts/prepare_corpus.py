#!/usr/bin/env python3
"""Extract and chunk a user-designated document corpus without external services."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree


SUPPORTED = {".txt", ".md", ".markdown", ".csv", ".json", ".html", ".htm", ".docx", ".pdf"}


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
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    units: list[tuple[str, str]] = []
    for index, paragraph in enumerate(root.iter(f"{ns}p"), 1):
        text = "".join(node.text or "" for node in paragraph.iter(f"{ns}t")).strip()
        if text:
            units.append((f"paragraph {index}", text))
    return units


def pdf_units(path: Path) -> list[tuple[str, str]]:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PDF extraction requires optional dependency: pypdf") from exc
    reader = PdfReader(str(path))
    units: list[tuple[str, str]] = []
    for index, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        if text:
            units.append((f"page {index}", text))
    if not units:
        raise RuntimeError("PDF contains no extractable text; OCR may be required")
    return units


def extract_units(path: Path) -> list[tuple[str, str]]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return docx_units(path)
    if suffix == ".pdf":
        return pdf_units(path)
    return plain_units(path)


def chunk_units(
    units: Iterable[tuple[str, str]], max_chars: int, overlap_chars: int
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
        if overlap_chars:
            tail = text[-overlap_chars:]
            current = [tail] if tail else []
            labels = [labels[-1]] if tail else []
            length = len(tail)
        else:
            current, labels, length = [], [], 0

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


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-chars", type=int, default=1800)
    parser.add_argument("--overlap-chars", type=int, default=180)
    parser.add_argument("--max-file-mb", type=int, default=100)
    args = parser.parse_args()

    corpus = args.corpus.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not corpus.is_dir():
        raise SystemExit(f"Corpus directory does not exist: {corpus}")
    if output.exists():
        raise SystemExit(f"Output already exists: {output}")
    if args.max_chars < 200 or not 0 <= args.overlap_chars < args.max_chars:
        raise SystemExit("Require max-chars >= 200 and 0 <= overlap-chars < max-chars")

    output.mkdir(parents=True)
    manifest: list[dict] = []
    all_chunks: list[dict] = []
    max_bytes = args.max_file_mb * 1024 * 1024

    for candidate in sorted(corpus.rglob("*")):
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if not is_within(resolved, corpus):
            continue
        if is_within(resolved, output):
            continue
        relative = resolved.relative_to(corpus).as_posix()
        stat = resolved.stat()
        suffix = resolved.suffix.lower()
        record = {
            "path": relative,
            "extension": suffix,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
            "status": "pending",
            "source_id": None,
            "chunk_count": 0,
            "error": None,
        }
        if suffix not in SUPPORTED:
            record["status"] = "unsupported"
            manifest.append(record)
            continue
        if stat.st_size > max_bytes:
            record["status"] = "skipped"
            record["error"] = f"file exceeds {args.max_file_mb} MB limit"
            manifest.append(record)
            continue
        try:
            digest = sha256(resolved)
            source_id = digest[:16]
            units = extract_units(resolved)
            chunks = chunk_units(units, args.max_chars, args.overlap_chars)
            record["source_id"] = source_id
            record["chunk_count"] = len(chunks)
            record["status"] = "extracted" if chunks else "empty"
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
        except Exception as exc:  # record extraction failure rather than hiding files
            record["status"] = "error"
            record["error"] = f"{type(exc).__name__}: {exc}"
        manifest.append(record)

    write_jsonl(output / "manifest.jsonl", manifest)
    write_jsonl(output / "chunks.jsonl", all_chunks)
    report = {
        "corpus": str(corpus),
        "file_count": len(manifest),
        "extracted_files": sum(item["status"] == "extracted" for item in manifest),
        "chunk_count": len(all_chunks),
        "unreadable_or_unsupported": [
            {"path": item["path"], "status": item["status"], "error": item["error"]}
            for item in manifest
            if item["status"] not in {"extracted", "empty"}
        ],
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
