#!/usr/bin/env python3
"""Build the three public Han Qi Agent release archives."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path, PurePosixPath


API_APP_FILES = (
    ".env.example",
    ".gitignore",
    "corpus.py",
    "folder_picker.py",
    "index.html",
    "requirements.txt",
    "server.py",
    "启动本地聊天.md",
)
UNIVERSAL_CHAT_FILES = (
    "启动提示词.md",
    "新手使用卡.md",
    "韩琦智能体-通用知识包.md",
)


def normalized_version(value: str) -> str:
    version = value.strip()
    if version[:1].casefold() == "v":
        version = version[1:]
    if not version or any(part == "" or not part.isdigit() for part in version.split(".")):
        raise ValueError("version must contain dot-separated numbers, for example 1.1")
    return version


def require_files(root: Path, relative_paths: list[Path]) -> None:
    missing = [str(path) for path in relative_paths if not (root / path).is_file()]
    if missing:
        raise FileNotFoundError(f"missing release files: {', '.join(missing)}")


def directory_files(root: Path, relative_dir: str, pattern: str = "*") -> list[Path]:
    directory = root / relative_dir
    return sorted(
        path.relative_to(root)
        for path in directory.rglob(pattern)
        if path.is_file() and "__pycache__" not in path.parts
    )


def write_archive(root: Path, output: Path, entries: list[tuple[Path, PurePosixPath]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, destination in entries:
            archive.write(root / source, destination.as_posix())
    print(f"Built {output} ({output.stat().st_size} bytes, {len(entries)} files)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Release version, for example 1.1")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    version = normalized_version(args.version)
    root = Path(__file__).resolve().parent.parent
    output_dir = args.output_dir.resolve()
    guide_docx = Path(f"韩琦智能体 V{version} 使用说明.docx")
    shared_root = [Path("使用说明.md"), guide_docx, Path("LICENSE")]
    universal = [Path("assets/universal-chat") / name for name in UNIVERSAL_CHAT_FILES]
    api_app = [Path("assets/api-app") / name for name in API_APP_FILES]
    api_support = [
        Path("assets/provider-config/providers.example.json"),
        Path("assets/knowledge-base/系统提示词.md"),
        *universal,
    ]

    complete = [
        Path("LICENSE"),
        Path("README.md"),
        Path("SKILL.md"),
        *directory_files(root, "agents"),
        *api_app,
        *api_support,
        *directory_files(root, "references"),
        *directory_files(root, "scripts", "*.py"),
        Path("使用说明.md"),
        guide_docx,
    ]
    require_files(root, list(dict.fromkeys([*shared_root, *universal, *api_app, *api_support, *complete])))

    chat_entries = [(path, PurePosixPath(path.name)) for path in [*universal, *shared_root]]
    api_entries: list[tuple[Path, PurePosixPath]] = []
    for path in [*api_app, *api_support, *shared_root]:
        if path.parts[:2] == ("assets", "api-app"):
            destination = PurePosixPath("api-app", *path.parts[2:])
        elif path.parts[:2] == ("assets", "provider-config"):
            destination = PurePosixPath("provider-config", *path.parts[2:])
        elif path.parts[:2] == ("assets", "knowledge-base"):
            destination = PurePosixPath("knowledge-base", *path.parts[2:])
        elif path.parts[:2] == ("assets", "universal-chat"):
            destination = PurePosixPath("universal-chat", *path.parts[2:])
        else:
            destination = PurePosixPath(path.name)
        api_entries.append((path, destination))
    complete_entries = [
        (path, PurePosixPath("han-qi-agent", *path.parts)) for path in dict.fromkeys(complete)
    ]

    write_archive(root, output_dir / f"han-qi-chat-pack-v{version}.zip", chat_entries)
    write_archive(root, output_dir / f"han-qi-api-chat-v{version}.zip", api_entries)
    write_archive(root, output_dir / f"han-qi-agent-public-v{version}.zip", complete_entries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
