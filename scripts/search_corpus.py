#!/usr/bin/env python3
"""Rank prepared corpus chunks with a dependency-free lexical BM25 search."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


ASCII_WORD = re.compile(r"[A-Za-z0-9_]+")
CJK_RUN = re.compile(r"[\u3400-\u9fff]+")


def tokenize(text: str) -> list[str]:
    tokens = [item.lower() for item in ASCII_WORD.findall(text)]
    for run in CJK_RUN.findall(text):
        tokens.extend(run)
        tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
    return tokens


def load_chunks(path: Path) -> list[dict]:
    chunks: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSON at {path}:{line_number}: {exc}") from exc
            if isinstance(item.get("text"), str):
                chunks.append(item)
    return chunks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("query")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--max-display-chars", type=int, default=1400)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    chunk_file = args.prepared.expanduser().resolve() / "chunks.jsonl"
    if not chunk_file.is_file():
        raise SystemExit(f"Missing prepared chunks: {chunk_file}")
    chunks = load_chunks(chunk_file)
    if not chunks:
        raise SystemExit("Prepared corpus contains no searchable chunks")

    query_tokens = tokenize(args.query)
    if not query_tokens:
        raise SystemExit("Query has no searchable tokens")

    tokenized = [tokenize(item["text"]) for item in chunks]
    document_frequency: Counter[str] = Counter()
    for terms in tokenized:
        document_frequency.update(set(terms))
    average_length = sum(len(terms) for terms in tokenized) / len(tokenized)
    query_counts = Counter(query_tokens)
    k1, b = 1.5, 0.75
    ranked: list[tuple[float, dict]] = []

    for item, terms in zip(chunks, tokenized):
        frequencies = Counter(terms)
        score = 0.0
        length_norm = 1 - b + b * len(terms) / max(average_length, 1)
        for term, query_weight in query_counts.items():
            tf = frequencies.get(term, 0)
            if not tf:
                continue
            df = document_frequency[term]
            inverse = math.log(1 + (len(chunks) - df + 0.5) / (df + 0.5))
            score += query_weight * inverse * (tf * (k1 + 1)) / (tf + k1 * length_norm)
        if args.query in item["text"]:
            score += 5.0
        if score:
            ranked.append((score, item))

    ranked.sort(key=lambda pair: pair[0], reverse=True)
    results = []
    for score, item in ranked[: max(1, args.top)]:
        result = dict(item)
        result["score"] = round(score, 4)
        if len(result["text"]) > args.max_display_chars:
            result["text"] = result["text"][: args.max_display_chars] + "…"
        results.append(result)

    if args.as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for result in results:
            print(
                f"[{result['path']} | {result['locator']} | chunk {result['chunk']} | "
                f"source {result['source_id']} | score {result['score']}]"
            )
            print(result["text"])
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
