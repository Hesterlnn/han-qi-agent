#!/usr/bin/env python3
"""Build the uploadable, single-file Han Qi knowledge bundle."""

from __future__ import annotations

import argparse
from pathlib import Path


SOURCE_FILES = [
    "mode-contract.md",
    "core-persona-model.md",
    "life-and-office-cards.md",
    "jiayou-chronology-1056-1063.md",
    "relationship-cards.md",
    "voice-and-dialogue-guide.md",
    "key-passages.md",
    "scenario-library.md",
    "research-mode.md",
    "bibliography-and-provenance.md",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Output Markdown path")
    parser.add_argument("--force", action="store_true", help="Replace an existing output")
    args = parser.parse_args()

    skill_root = Path(__file__).resolve().parent.parent
    reference_dir = skill_root / "references"
    output = args.output or (
        skill_root / "assets" / "universal-chat" / "韩琦智能体-通用知识包.md"
    )
    output = output.resolve()

    missing = [name for name in SOURCE_FILES if not (reference_dir / name).is_file()]
    if missing:
        raise SystemExit(f"Missing source files: {', '.join(missing)}")
    if output.exists() and not args.force:
        raise SystemExit(f"Output already exists: {output}. Pass --force to replace it.")

    sections = [
        "# 韩琦智能体－通用知识包\n",
        "> 本文件由公开包内的结构化人物资料合并生成，供普通聊天框上传。\n"
        "> 它允许同人演绎，但不允许把生成内容冒充史料。\n",
    ]
    for name in SOURCE_FILES:
        source = reference_dir / name
        sections.append(f"\n---\n\n<!-- bundled-from: {name} -->\n\n")
        sections.append(source.read_text(encoding="utf-8").strip())
        sections.append("\n")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(sections), encoding="utf-8", newline="\n")
    print(f"Built {output} ({output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
