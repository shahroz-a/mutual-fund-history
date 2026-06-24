#!/usr/bin/env python3
"""Generate SHA-256 checksums for public archive files."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def archive_files(data_dir: Path) -> list[Path]:
    files = [
        data_dir / "historical.csv.gz",
        data_dir / "latest.csv",
        data_dir / "latest.csv.gz",
    ]
    files.extend(sorted((data_dir / "Year").glob("*/*/*.csv")))
    files.extend(sorted((data_dir / "Year").glob("*/*/*.csv.gz")))
    return [path for path in files if path.exists()]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate SHA-256 checksum file.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output", default="releases/checksums.sha256")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    data_dir = Path(args.data_dir)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for path in archive_files(data_dir):
        lines.append(f"{digest(path)}  {path.relative_to(data_dir)}")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {output} ({len(lines)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
