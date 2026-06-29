#!/usr/bin/env python3
"""Update daily NAV CSV files from AMFI public text exports."""

from __future__ import annotations

import argparse
import csv
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo


LATEST_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
HISTORY_URL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
CSV_COLUMNS = ["date", "scheme_code", "scheme_name", "nav"]
INDIA_ZONE = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class NavRow:
    nav_date: date
    scheme_code: str
    scheme_name: str
    nav: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.nav_date.isoformat(), self.scheme_code)

    def as_csv_row(self) -> dict[str, str]:
        return {
            "date": self.nav_date.isoformat(),
            "scheme_code": self.scheme_code,
            "scheme_name": self.scheme_name,
            "nav": self.nav,
        }


def parse_nav_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%d-%b-%Y").date()


def format_amfi_date(value: date) -> str:
    return value.strftime("%d-%b-%Y")


def normalize_nav(value: str) -> str | None:
    try:
        parsed = Decimal(value.strip())
    except InvalidOperation:
        return None
    if not parsed.is_finite() or parsed <= 0:
        return None
    return format(parsed, "f")


def decode_response(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


def fetch_text(url: str, *, timeout: int, retries: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "mutual-fund-historical-data"})
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return decode_response(response.read())
        except Exception as exc:  # pragma: no cover - depends on network state
            last_error = exc
            if attempt < retries:
                time.sleep(min(attempt * 2, 10))
    raise RuntimeError(f"Unable to fetch {url}: {last_error}")


def history_url(base_url: str, nav_date: date) -> str:
    query = urllib.parse.urlencode(
        {"frmdt": format_amfi_date(nav_date), "todt": format_amfi_date(nav_date)}
    )
    return f"{base_url}?{query}"


def parse_latest_export(text: str) -> list[NavRow]:
    rows: list[NavRow] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or ";" not in line:
            continue
        parts = [part.strip() for part in line.split(";")]
        if parts[:6] == [
            "Scheme Code",
            "ISIN Div Payout/ ISIN Growth",
            "ISIN Div Reinvestment",
            "Scheme Name",
            "Net Asset Value",
            "Date",
        ]:
            continue
        if len(parts) != 6:
            continue

        scheme_code, _, _, scheme_name, nav, raw_date = parts
        rows.extend(parse_row(scheme_code, scheme_name, nav, raw_date, line_number))
    return rows


def parse_history_export(text: str) -> list[NavRow]:
    rows: list[NavRow] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or ";" not in line:
            continue
        parts = [part.strip() for part in line.split(";")]
        if parts[:8] == [
            "Scheme Code",
            "Scheme Name",
            "ISIN Div Payout/ISIN Growth",
            "ISIN Div Reinvestment",
            "Net Asset Value",
            "Repurchase Price",
            "Sale Price",
            "Date",
        ]:
            continue
        if len(parts) != 8:
            continue

        scheme_code, scheme_name, _, _, nav, _, _, raw_date = parts
        rows.extend(parse_row(scheme_code, scheme_name, nav, raw_date, line_number))
    return rows


def parse_row(
    scheme_code: str,
    scheme_name: str,
    nav: str,
    raw_date: str,
    line_number: int,
) -> list[NavRow]:
    if not scheme_code.isdigit() or not scheme_name or not raw_date:
        return []
    normalized_nav = normalize_nav(nav)
    if normalized_nav is None:
        return []
    try:
        nav_date = parse_nav_date(raw_date)
    except ValueError as exc:
        raise RuntimeError(f"Invalid AMFI date on line {line_number}: {raw_date}") from exc
    return [NavRow(nav_date, scheme_code, scheme_name, normalized_nav)]


def merge_rows(existing: list[NavRow], additions: list[NavRow]) -> list[NavRow]:
    merged: dict[tuple[str, str], NavRow] = {}
    for row in [*existing, *additions]:
        if row.key not in merged:
            merged[row.key] = row
    return sorted(merged.values(), key=row_sort_key)


def row_sort_key(row: NavRow) -> tuple[int, str, str]:
    return (int(row.scheme_code), row.scheme_name, row.nav)


def latest_sort_key(row: NavRow) -> tuple[int, str]:
    return (int(row.scheme_code), row.scheme_name)


def daily_path(data_dir: Path, nav_date: date) -> Path:
    return (
        data_dir
        / "Year"
        / f"{nav_date.year:04d}"
        / f"{nav_date.month:02d}"
        / f"{nav_date.day:02d}.csv"
    )


def parse_archive_date(path: Path, year_root: Path) -> date | None:
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


def newest_archive_date(data_dir: Path) -> date | None:
    year_root = data_dir / "Year"
    if not year_root.is_dir():
        return None
    dates = [
        parsed
        for path in year_root.glob("*/*/*.csv")
        if (parsed := parse_archive_date(path, year_root)) is not None
    ]
    return max(dates, default=None)


def load_latest(path: Path) -> dict[str, NavRow]:
    latest: dict[str, NavRow] = {}
    if not path.is_file():
        return latest
    with path.open("rt", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for line_number, row in enumerate(reader, start=2):
            raw_date = (row.get("date") or "").strip()
            scheme_code = (row.get("scheme_code") or "").strip()
            scheme_name = (row.get("scheme_name") or "").strip()
            nav = (row.get("nav") or "").strip()
            if not (raw_date and scheme_code and scheme_name and nav):
                raise RuntimeError(f"Malformed latest.csv row at line {line_number}")
            latest[scheme_code] = NavRow(date.fromisoformat(raw_date), scheme_code, scheme_name, nav)
    return latest


def update_latest(latest: dict[str, NavRow], rows: list[NavRow]) -> None:
    for row in rows:
        current = latest.get(row.scheme_code)
        if current is None or row.nav_date >= current.nav_date:
            latest[row.scheme_code] = row


def write_rows(path: Path, rows: list[NavRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wt", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row.as_csv_row())


def write_latest(path: Path, latest: dict[str, NavRow]) -> None:
    write_rows(path, sorted(latest.values(), key=latest_sort_key))


def date_range(start: date, end: date) -> list[date]:
    if start > end:
        return []
    days = (end - start).days
    return [start + timedelta(days=offset) for offset in range(days + 1)]


def choose_start_date(data_dir: Path, as_of: date, lookback_days: int, from_date: date | None) -> date:
    if from_date is not None:
        return from_date
    newest = newest_archive_date(data_dir)
    if newest is None:
        return as_of
    catch_up_start = newest + timedelta(days=1)
    refresh_start = as_of - timedelta(days=lookback_days)
    return min(catch_up_start, refresh_start)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update NAV CSV files from AMFI exports.")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--latest-url", default=LATEST_URL)
    parser.add_argument("--history-url", default=HISTORY_URL)
    parser.add_argument("--as-of", default=datetime.now(INDIA_ZONE).date().isoformat())
    parser.add_argument("--from-date", default=None)
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=14,
        help="Refresh this many recent calendar days to recover delayed AMFI history exports.",
    )
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--retries", type=int, default=3)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.lookback_days < 0:
        print("--lookback-days must be zero or greater", file=sys.stderr)
        return 2

    as_of = date.fromisoformat(args.as_of)
    from_date = date.fromisoformat(args.from_date) if args.from_date else None
    start_date = choose_start_date(args.data_dir, as_of, args.lookback_days, from_date)
    if start_date > as_of:
        start_date = as_of

    rows_by_date: dict[date, list[NavRow]] = defaultdict(list)
    fetched_history_dates: list[str] = []
    for nav_date in date_range(start_date, as_of):
        url = history_url(args.history_url, nav_date)
        text = fetch_text(url, timeout=args.timeout, retries=args.retries)
        rows = parse_history_export(text)
        if rows:
            rows_by_date[nav_date].extend(rows)
            fetched_history_dates.append(nav_date.isoformat())

    latest_text = fetch_text(args.latest_url, timeout=args.timeout, retries=args.retries)
    latest_export_rows = parse_latest_export(latest_text)
    for row in latest_export_rows:
        if start_date <= row.nav_date <= as_of:
            rows_by_date[row.nav_date].append(row)

    latest = load_latest(args.data_dir / "latest.csv")
    update_latest(latest, latest_export_rows)

    written_files = 0
    written_rows = 0
    for nav_date in sorted(rows_by_date):
        merged = merge_rows([], rows_by_date[nav_date])
        write_rows(daily_path(args.data_dir, nav_date), merged)
        update_latest(latest, merged)
        written_files += 1
        written_rows += len(merged)

    write_latest(args.data_dir / "latest.csv", latest)

    print(f"AMFI update window: {start_date.isoformat()} to {as_of.isoformat()}")
    print(f"Historical dates with rows: {', '.join(fetched_history_dates) or 'none'}")
    print(f"Daily files written: {written_files}")
    print(f"Daily rows written: {written_rows}")
    print(f"Latest snapshot rows: {len(latest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
