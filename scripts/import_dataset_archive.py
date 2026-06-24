#!/usr/bin/env python3
"""Import generated public dataset files from a private archive package.

The archive is expected to contain latest.csv or latest.csv.gz and a Year/
directory, either at its root or under a data/ directory. This script
intentionally does not know or expose any collection source; it only imports
already-generated dataset files.
"""

from __future__ import annotations

import argparse
import gzip
import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path


REQUIRED_TREE = "Year"
LATEST_NAMES = ("latest.csv.gz", "latest.csv")


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def safe_extract_tar(archive: Path, target: Path) -> None:
    target = target.resolve()
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            member_path = (target / member.name).resolve()
            if not is_relative_to(member_path, target):
                raise RuntimeError(f"Unsafe archive path: {member.name}")
            if member.issym() or member.islnk():
                raise RuntimeError(f"Archive links are not allowed: {member.name}")
        tar.extractall(target)


def safe_extract_zip(archive: Path, target: Path) -> None:
    target = target.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            member_path = (target / member.filename).resolve()
            if not is_relative_to(member_path, target):
                raise RuntimeError(f"Unsafe archive path: {member.filename}")
            mode = member.external_attr >> 16
            if mode & 0o120000:
                raise RuntimeError(f"Archive symlinks are not allowed: {member.filename}")
        zf.extractall(target)


def extract_archive(archive: Path, target: Path) -> None:
    if zipfile.is_zipfile(archive):
        safe_extract_zip(archive, target)
        return
    if tarfile.is_tarfile(archive):
        safe_extract_tar(archive, target)
        return
    raise RuntimeError("Archive must be a tar/tar.gz/tgz or zip file.")


def candidate_roots(root: Path) -> list[Path]:
    candidates = [root]
    candidates.extend(path for path in root.iterdir() if path.is_dir())
    candidates.extend(path / "data" for path in list(candidates) if (path / "data").is_dir())
    return candidates


def has_latest(candidate: Path) -> bool:
    return any((candidate / name).is_file() for name in LATEST_NAMES)


def find_payload(root: Path) -> Path:
    for candidate in candidate_roots(root):
        if has_latest(candidate) and (candidate / REQUIRED_TREE).is_dir():
            return candidate
    raise RuntimeError("Archive must contain latest.csv or latest.csv.gz and Year/.")


def is_valid_daily_path(path: Path) -> bool:
    parts = path.parts
    if len(parts) != 3:
        return False
    year, month, filename = parts
    if not (year.isdigit() and len(year) == 4):
        return False
    if not (month.isdigit() and len(month) == 2 and 1 <= int(month) <= 12):
        return False
    if filename.endswith(".csv.gz"):
        day = filename.removesuffix(".csv.gz")
    elif filename.endswith(".csv"):
        day = filename.removesuffix(".csv")
    else:
        return False
    return day.isdigit() and len(day) == 2 and 1 <= int(day) <= 31


def gzip_csv(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = target.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=6, mtime=0)
    try:
        with source.open("rb") as src:
            shutil.copyfileobj(src, gz, length=1024 * 1024)
    finally:
        gz.close()
        raw.close()


def gunzip_csv(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(source, "rb") as src, target.open("wb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)


def import_latest(payload: Path, data_dir: Path) -> None:
    latest_gz = payload / "latest.csv.gz"
    latest_csv = payload / "latest.csv"
    if latest_gz.is_file():
        shutil.copy2(latest_gz, data_dir / "latest.csv.gz")
        gunzip_csv(latest_gz, data_dir / "latest.csv")
        return
    if latest_csv.is_file():
        shutil.copy2(latest_csv, data_dir / "latest.csv")
        gzip_csv(latest_csv, data_dir / "latest.csv.gz")
        return
    raise RuntimeError("Archive does not contain latest.csv or latest.csv.gz.")


def import_payload(payload: Path, data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    import_latest(payload, data_dir)

    source_tree = payload / REQUIRED_TREE
    target_tree = data_dir / REQUIRED_TREE
    copied = 0
    seen_daily: set[Path] = set()
    for source_file in sorted(source_tree.rglob("*.csv*")):
        relative = source_file.relative_to(source_tree)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if not is_valid_daily_path(relative):
            raise RuntimeError(f"Unexpected dataset file path: {REQUIRED_TREE}/{relative}")

        if source_file.name.endswith(".csv.gz"):
            plain_relative = relative.with_suffix("")
            if plain_relative in seen_daily:
                continue
            target_file = target_tree / relative
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target_file)
            copied += 1
            seen_daily.add(plain_relative)
        elif source_file.name.endswith(".csv"):
            if relative in seen_daily:
                continue
            target_file = target_tree / relative
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, target_file)
            gzip_csv(source_file, target_file.with_suffix(target_file.suffix + ".gz"))
            copied += 1
            seen_daily.add(relative)

    if copied == 0:
        raise RuntimeError("Archive Year/ directory does not contain daily CSV files.")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import generated dataset archive files.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    archive = args.archive
    if not archive.is_file():
        raise RuntimeError(f"Archive does not exist: {archive}")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        extract_archive(archive, root)
        payload = find_payload(root)
        import_payload(payload, args.data_dir)
    print(f"Imported generated dataset archive into {args.data_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
