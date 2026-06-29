#!/usr/bin/env python3
"""Fail when the published NAV dataset is stale or internally inconsistent."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path


def parse_iso_date(value: str, *, source: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise RuntimeError(f"Invalid date in {source}: {value}") from exc


def latest_csv_date(path: Path) -> date:
    if not path.is_file():
        raise RuntimeError(f"Missing latest snapshot: {path}")

    max_date: date | None = None
    with path.open("rt", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "date" not in (reader.fieldnames or []):
            raise RuntimeError(f"{path} does not contain a date column")
        for line_number, row in enumerate(reader, start=2):
            raw_date = (row.get("date") or "").strip()
            if not raw_date:
                raise RuntimeError(f"Missing date in {path} line {line_number}")
            parsed = parse_iso_date(raw_date, source=f"{path} line {line_number}")
            max_date = parsed if max_date is None else max(max_date, parsed)

    if max_date is None:
        raise RuntimeError(f"{path} does not contain any NAV rows")
    return max_date


def daily_path_for(data_dir: Path, nav_date: date) -> Path:
    return (
        data_dir
        / "Year"
        / f"{nav_date.year:04d}"
        / f"{nav_date.month:02d}"
        / f"{nav_date.day:02d}.csv"
    )


def date_from_daily_path(path: Path, year_root: Path) -> date | None:
    try:
        relative = path.relative_to(year_root)
    except ValueError:
        return None

    parts = relative.parts
    if len(parts) != 3:
        return None
    year, month, filename = parts
    if not filename.endswith(".csv"):
        return None
    day = filename.removesuffix(".csv")
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        return None
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def newest_daily_date(data_dir: Path) -> date:
    year_root = data_dir / "Year"
    if not year_root.is_dir():
        raise RuntimeError(f"Missing historical archive directory: {year_root}")

    dates = [
        parsed
        for path in year_root.glob("*/*/*.csv")
        if (parsed := date_from_daily_path(path, year_root)) is not None
    ]
    if not dates:
        raise RuntimeError(f"No daily CSV files found under {year_root}")
    return max(dates)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check published NAV freshness.")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=1,
        help="Maximum allowed age of the latest NAV date relative to --as-of.",
    )
    parser.add_argument(
        "--as-of",
        default=date.today().isoformat(),
        help="Freshness reference date in YYYY-MM-DD format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.max_age_days < 0:
        print("--max-age-days must be zero or greater", file=sys.stderr)
        return 2

    try:
        as_of = parse_iso_date(args.as_of, source="--as-of")
        latest_date = latest_csv_date(args.data_dir / "latest.csv")
        archive_date = newest_daily_date(args.data_dir)
    except RuntimeError as exc:
        print(f"Freshness check failed: {exc}", file=sys.stderr)
        return 1

    expected_daily_path = daily_path_for(args.data_dir, latest_date)
    if not expected_daily_path.is_file():
        print(
            "Freshness check failed: "
            f"latest.csv has {latest_date.isoformat()}, but {expected_daily_path} is missing.",
            file=sys.stderr,
        )
        return 1

    if archive_date != latest_date:
        print(
            "Freshness check failed: "
            f"latest.csv max date is {latest_date.isoformat()}, "
            f"but newest daily file is {archive_date.isoformat()}.",
            file=sys.stderr,
        )
        return 1

    age_days = (as_of - latest_date).days
    if age_days < 0:
        print(
            "Freshness check failed: "
            f"latest NAV date {latest_date.isoformat()} is after {as_of.isoformat()}.",
            file=sys.stderr,
        )
        return 1
    if age_days > args.max_age_days:
        print(
            "Freshness check failed: "
            f"latest NAV date is {latest_date.isoformat()}, "
            f"{age_days} days behind {as_of.isoformat()} "
            f"(allowed: {args.max_age_days}).",
            file=sys.stderr,
        )
        return 1

    print(
        "Freshness check passed: "
        f"latest NAV date {latest_date.isoformat()}, "
        f"daily file {expected_daily_path}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
