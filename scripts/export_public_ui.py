#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shutil
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE = str(SCRIPT_DIR.parent)
DEFAULT_TARGET = str(SCRIPT_DIR.parent.parent / "AI4Math-Evolving")

DEFAULT_EXCLUDES = [
    ".git",
    ".env",
    ".env.*",
    "opencode.json",
    "node_modules",
    "dist",
    ".run_logs",
    ".run_pids",
    ".archives",
    ".tools",
    ".DS_Store",
    ".ruff_cache",
    "__pycache__",
    "*.pyc",
    "*.tgz",
    "*.tar.gz",
    "migration_artifact_*",
    "server_data",
]

DEFAULT_INCLUDES = [
    "README.md",
    "ATTRIBUTIONS.md",
    "index.html",
    "package.json",
    "package-lock.json",
    "postcss.config.mjs",
    "vite.config.ts",
    ".gitignore",
    ".env.example",
    "opencode.example.json",
    "src",
    "backend",
    "guidelines",
    "docs",
    "examples",
    "tests",
    "scripts/export_public_ui.py",
    "scripts/smoke_ui_repo.sh",
    "start_all.sh",
    "stop_all.sh",
]


def matches_any(path: str, patterns: list[str]) -> bool:
    parts = Path(path).parts
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
        if any(fnmatch.fnmatch(part, pattern) for part in parts):
            return True
    return False


def copy_item(src_root: Path, dst_root: Path, rel: str, excludes: list[str]) -> None:
    src = src_root / rel
    dst = dst_root / rel
    if not src.exists():
        return
    if matches_any(rel, excludes):
        return
    if src.is_dir():
        for root, dirs, files in os.walk(src):
            root_path = Path(root)
            dirs[:] = [
                d
                for d in dirs
                if not matches_any((root_path / d).relative_to(src_root).as_posix(), excludes)
            ]
            for file_name in files:
                file_rel = (root_path / file_name).relative_to(src_root).as_posix()
                if matches_any(file_rel, excludes):
                    continue
                target = dst_root / file_rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_root / file_rel, target)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    target = Path(args.target).resolve()
    if not source.is_dir():
        raise SystemExit(f"source not found: {source}")
    if target == source or source in target.parents:
        raise SystemExit("target must not be inside source")

    manifest = {
        "source": str(source),
        "target": str(target),
        "includes": DEFAULT_INCLUDES,
        "excludes": DEFAULT_EXCLUDES,
    }
    if args.dry_run:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for rel in DEFAULT_INCLUDES:
        copy_item(source, target, rel, DEFAULT_EXCLUDES)

    print(json.dumps({"ok": True, "target": str(target)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
