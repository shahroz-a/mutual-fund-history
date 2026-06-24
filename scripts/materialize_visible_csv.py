#!/usr/bin/env python3
"""Materialize browser-visible CSV files from compressed public dataset files.

The repository keeps the full historical archive compressed for size. This script
creates plain CSV entry points that GitHub can render in the browser without
including any private collection or update logic.
"""

from __future__ import annotations

import argparse
import gzip
import shutil
import sys
from pathlib import Path


def copy_gzip_to_csv(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(source, "rb") as src, target.open("wb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)


def materialize_latest(data_dir: Path) -> Path:
    latest_csv = data_dir / "latest.csv"
    latest_gz = data_dir / "latest.csv.gz"
    if latest_gz.exists():
        copy_gzip_to_csv(latest_gz, latest_csv)
    elif not latest_csv.exists():
        raise RuntimeError(f"Missing latest dataset file: {latest_csv} or {latest_gz}")
    return latest_csv


def latest_archive_year(data_dir: Path) -> str:
    years = sorted(path.name for path in (data_dir / "Year").iterdir() if path.is_dir())
    if not years:
        raise RuntimeError(f"No archive years found in {data_dir / 'Year'}")
    return years[-1]


def materialize_year(data_dir: Path, year: str) -> int:
    year_dir = data_dir / "Year" / year
    if not year_dir.is_dir():
        raise RuntimeError(f"Archive year does not exist: {year_dir}")

    copied = 0
    for source in sorted(year_dir.glob("*/*.csv.gz")):
        copy_gzip_to_csv(source, source.with_suffix(""))
        copied += 1
    return copied


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create browser-visible CSV files.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument(
        "--year",
        default="latest",
        help="Archive year to materialize, or 'latest' for the newest available year.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    data_dir = Path(args.data_dir)
    materialize_latest(data_dir)
    year = latest_archive_year(data_dir) if args.year == "latest" else args.year
    count = materialize_year(data_dir, year)
    print(f"Materialized data/latest.csv and {count} browser-visible daily CSV files for {year}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
