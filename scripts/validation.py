#!/usr/bin/env python3
"""Validate public mutual fund NAV archive files."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


REQUIRED_COLUMNS = ["date", "scheme_code", "scheme_name", "nav"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SCHEME_CODE_RE = re.compile(r"^\d{1,12}$")
NAV_RE = re.compile(r"^\d+(?:\.\d+)?$")
STATS_START = "<!-- DATASET_STATS_START -->"
STATS_END = "<!-- DATASET_STATS_END -->"


@dataclass
class IssueBucket:
    count: int = 0
    examples: list[dict[str, Any]] = field(default_factory=list)

    def add(self, example: dict[str, Any], max_examples: int) -> None:
        self.count += 1
        if len(self.examples) < max_examples:
            self.examples.append(example)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", newline="", encoding="utf-8")
    return path.open("rt", newline="", encoding="utf-8")


def add_issue(
    issues: dict[str, IssueBucket],
    kind: str,
    *,
    path: Path,
    line: int | None = None,
    message: str,
    value: Any = None,
    max_examples: int,
) -> None:
    example: dict[str, Any] = {"file": str(path), "message": message}
    if line is not None:
        example["line"] = line
    if value is not None:
        example["value"] = value
    issues[kind].add(example, max_examples)


def parse_nav(value: str) -> Decimal | None:
    if not NAV_RE.match(value):
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        return None
    if not parsed.is_finite() or parsed <= 0:
        return None
    return parsed


def validate_file(path: Path, as_of: date, max_examples: int) -> dict[str, Any]:
    issues: dict[str, IssueBucket] = defaultdict(IssueBucket)
    warnings: dict[str, IssueBucket] = defaultdict(IssueBucket)
    seen_keys: set[tuple[str, str]] = set()
    seen_rows: set[tuple[str, str, str, str]] = set()
    unique_scheme_codes: set[str] = set()
    min_date: date | None = None
    max_date: date | None = None
    row_count = 0
    invalid_rows = 0

    file_report: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "sha256": sha256_file(path) if path.exists() else None,
        "rows": 0,
        "valid_rows": 0,
        "invalid_rows": 0,
        "unique_scheme_codes": 0,
        "date_min": None,
        "date_max": None,
        "issues": {},
        "warnings": {},
    }

    if not path.exists():
        add_issue(
            issues,
            "missing_file",
            path=path,
            message="Dataset file does not exist.",
            max_examples=max_examples,
        )
        file_report["issues"] = serialize_buckets(issues)
        return file_report

    try:
        with open_text(path) as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != REQUIRED_COLUMNS:
                add_issue(
                    issues,
                    "schema_mismatch",
                    path=path,
                    line=1,
                    message="CSV header does not match required column order.",
                    value={"expected": REQUIRED_COLUMNS, "actual": reader.fieldnames},
                    max_examples=max_examples,
                )

            for row in reader:
                row_count += 1
                row_has_error = False
                line = reader.line_num

                if None in row:
                    row_has_error = True
                    add_issue(
                        issues,
                        "malformed_csv_row",
                        path=path,
                        line=line,
                        message="CSV row has more fields than the header.",
                        value=row.get(None),
                        max_examples=max_examples,
                    )

                values = {column: (row.get(column) or "") for column in REQUIRED_COLUMNS}

                for column, raw_value in values.items():
                    if raw_value != raw_value.strip():
                        row_has_error = True
                        add_issue(
                            issues,
                            "inconsistent_whitespace",
                            path=path,
                            line=line,
                            message=f"{column} has leading or trailing whitespace.",
                            value=raw_value,
                            max_examples=max_examples,
                        )
                    values[column] = raw_value.strip()

                parsed_date: date | None = None
                date_value = values["date"]
                if not date_value:
                    row_has_error = True
                    add_issue(
                        issues,
                        "missing_date",
                        path=path,
                        line=line,
                        message="date is required.",
                        max_examples=max_examples,
                    )
                elif not DATE_RE.match(date_value):
                    row_has_error = True
                    add_issue(
                        issues,
                        "invalid_date",
                        path=path,
                        line=line,
                        message="date must use YYYY-MM-DD format.",
                        value=date_value,
                        max_examples=max_examples,
                    )
                else:
                    try:
                        parsed_date = date.fromisoformat(date_value)
                    except ValueError:
                        row_has_error = True
                        add_issue(
                            issues,
                            "invalid_date",
                            path=path,
                            line=line,
                            message="date is not a valid calendar date.",
                            value=date_value,
                            max_examples=max_examples,
                        )
                    else:
                        if parsed_date.isoformat() != date_value:
                            row_has_error = True
                            add_issue(
                                issues,
                                "invalid_date",
                                path=path,
                                line=line,
                                message="date is not normalized ISO format.",
                                value=date_value,
                                max_examples=max_examples,
                            )
                        if parsed_date > as_of:
                            row_has_error = True
                            add_issue(
                                issues,
                                "future_date",
                                path=path,
                                line=line,
                                message=f"date is after validation date {as_of.isoformat()}.",
                                value=date_value,
                                max_examples=max_examples,
                            )

                scheme_code = values["scheme_code"]
                if not scheme_code:
                    row_has_error = True
                    add_issue(
                        issues,
                        "missing_scheme_code",
                        path=path,
                        line=line,
                        message="scheme_code is required.",
                        max_examples=max_examples,
                    )
                elif not SCHEME_CODE_RE.match(scheme_code):
                    row_has_error = True
                    add_issue(
                        issues,
                        "malformed_scheme_code",
                        path=path,
                        line=line,
                        message="scheme_code must contain 1 to 12 digits.",
                        value=scheme_code,
                        max_examples=max_examples,
                    )

                scheme_name = values["scheme_name"]
                if not scheme_name:
                    row_has_error = True
                    add_issue(
                        issues,
                        "missing_scheme_name",
                        path=path,
                        line=line,
                        message="scheme_name is required.",
                        max_examples=max_examples,
                    )

                nav_value = values["nav"]
                if not nav_value:
                    row_has_error = True
                    add_issue(
                        issues,
                        "missing_nav",
                        path=path,
                        line=line,
                        message="nav is required.",
                        max_examples=max_examples,
                    )
                elif parse_nav(nav_value) is None:
                    row_has_error = True
                    add_issue(
                        issues,
                        "invalid_nav",
                        path=path,
                        line=line,
                        message="nav must be a positive decimal without commas or symbols.",
                        value=nav_value,
                        max_examples=max_examples,
                    )

                if parsed_date is not None and SCHEME_CODE_RE.match(scheme_code):
                    key = (date_value, scheme_code)
                    if key in seen_keys:
                        row_has_error = True
                        add_issue(
                            issues,
                            "duplicate_date_scheme_code",
                            path=path,
                            line=line,
                            message="Duplicate (date, scheme_code) key.",
                            value={"date": date_value, "scheme_code": scheme_code},
                            max_examples=max_examples,
                        )
                    else:
                        seen_keys.add(key)

                exact_row = tuple(values[column] for column in REQUIRED_COLUMNS)
                if exact_row in seen_rows:
                    row_has_error = True
                    add_issue(
                        issues,
                        "duplicate_row",
                        path=path,
                        line=line,
                        message="Duplicate row.",
                        value=dict(zip(REQUIRED_COLUMNS, exact_row)),
                        max_examples=max_examples,
                    )
                else:
                    seen_rows.add(exact_row)

                if parsed_date is not None:
                    min_date = parsed_date if min_date is None else min(min_date, parsed_date)
                    max_date = parsed_date if max_date is None else max(max_date, parsed_date)
                if SCHEME_CODE_RE.match(scheme_code):
                    unique_scheme_codes.add(scheme_code)
                if row_has_error:
                    invalid_rows += 1

    except (gzip.BadGzipFile, EOFError) as exc:
        add_issue(
            issues,
            "invalid_gzip",
            path=path,
            message=f"File is not a readable gzip archive: {exc}",
            max_examples=max_examples,
        )
    except UnicodeDecodeError as exc:
        add_issue(
            issues,
            "invalid_encoding",
            path=path,
            message=f"File is not valid UTF-8: {exc}",
            max_examples=max_examples,
        )
    except csv.Error as exc:
        add_issue(
            issues,
            "invalid_csv",
            path=path,
            message=f"CSV parser error: {exc}",
            max_examples=max_examples,
        )

    if row_count == 0 and not issues:
        add_issue(
            warnings,
            "empty_dataset",
            path=path,
            message="Dataset contains a header but no data rows.",
            max_examples=max_examples,
        )

    file_report.update(
        {
            "rows": row_count,
            "valid_rows": max(row_count - invalid_rows, 0),
            "invalid_rows": invalid_rows,
            "unique_scheme_codes": len(unique_scheme_codes),
            "date_min": min_date.isoformat() if min_date else None,
            "date_max": max_date.isoformat() if max_date else None,
            "issues": serialize_buckets(issues),
            "warnings": serialize_buckets(warnings),
        }
    )
    return file_report


def serialize_buckets(buckets: dict[str, IssueBucket]) -> dict[str, Any]:
    return {
        kind: {"count": bucket.count, "examples": bucket.examples}
        for kind, bucket in sorted(buckets.items())
    }


def merge_buckets(files: Iterable[dict[str, Any]], key: str) -> dict[str, Any]:
    merged: dict[str, IssueBucket] = defaultdict(IssueBucket)
    for file_report in files:
        for kind, payload in file_report.get(key, {}).items():
            bucket = merged[kind]
            bucket.count += int(payload.get("count", 0))
            remaining = 50 - len(bucket.examples)
            if remaining > 0:
                bucket.examples.extend(payload.get("examples", [])[:remaining])
    return serialize_buckets(merged)


def build_report(paths: list[Path], as_of: date, max_examples: int) -> dict[str, Any]:
    file_reports = [validate_file(path, as_of, max_examples) for path in paths]
    issues = merge_buckets(file_reports, "issues")
    warnings = merge_buckets(file_reports, "warnings")
    total_rows = sum(int(file_report["rows"]) for file_report in file_reports)
    invalid_rows = sum(int(file_report["invalid_rows"]) for file_report in file_reports)

    historical = next(
        (item for item in file_reports if Path(item["path"]).name == "historical.csv.gz"),
        None,
    )
    compressed_archive_chunks = [
        item
        for item in file_reports
        if "Year" in Path(item["path"]).parts and Path(item["path"]).name.endswith(".csv.gz")
    ]
    visible_archive_chunks = [
        item
        for item in file_reports
        if "Year" in Path(item["path"]).parts and Path(item["path"]).name.endswith(".csv")
    ]
    archive_chunks = compressed_archive_chunks or visible_archive_chunks
    latest = next(
        (item for item in file_reports if Path(item["path"]).name == "latest.csv"),
        None,
    ) or next(
        (item for item in file_reports if Path(item["path"]).name == "latest.csv.gz"),
        None,
    )
    archive_reports = [historical] if historical else archive_chunks
    archive_reports = [item for item in archive_reports if item]
    date_min = min((item["date_min"] for item in archive_reports if item["date_min"]), default=None)
    date_max = max((item["date_max"] for item in archive_reports if item["date_max"]), default=None)
    historical_rows = (
        int(historical["rows"])
        if historical
        else sum(int(item["rows"]) for item in archive_chunks)
    )
    unique_scheme_codes = (
        int(latest["unique_scheme_codes"])
        if latest
        else max((int(item["unique_scheme_codes"]) for item in archive_chunks), default=0)
    )

    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "as_of": as_of.isoformat(),
        "status": "failed" if issues else "passed",
        "summary": {
            "files": len(file_reports),
            "rows": total_rows,
            "valid_rows": max(total_rows - invalid_rows, 0),
            "invalid_rows": invalid_rows,
            "historical_rows": historical_rows,
            "latest_rows": latest["rows"] if latest else 0,
            "unique_scheme_codes": unique_scheme_codes,
            "date_min": date_min,
            "date_max": date_max,
        },
        "files": file_reports,
        "issues": issues,
        "warnings": warnings,
    }
    return report


def write_json_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = report["summary"]
    lines = [
        "# Dataset Validation Report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Validation date: `{report['as_of']}`",
        f"- Status: `{report['status']}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Files | {summary['files']} |",
        f"| Total rows | {summary['rows']} |",
        f"| Valid rows | {summary['valid_rows']} |",
        f"| Invalid rows | {summary['invalid_rows']} |",
        f"| Historical rows | {summary['historical_rows']} |",
        f"| Latest rows | {summary['latest_rows']} |",
        f"| Unique scheme codes | {summary['unique_scheme_codes']} |",
        f"| Date range | {format_date_range(summary['date_min'], summary['date_max'])} |",
        "",
        "## Files",
        "",
        "| File | Rows | Invalid | Unique schemes | Date range | SHA-256 |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]

    for file_report in report["files"]:
        digest = file_report["sha256"] or ""
        lines.append(
            "| {path} | {rows} | {invalid} | {schemes} | {date_range} | `{sha}` |".format(
                path=file_report["path"],
                rows=file_report["rows"],
                invalid=file_report["invalid_rows"],
                schemes=file_report["unique_scheme_codes"],
                date_range=format_date_range(file_report["date_min"], file_report["date_max"]),
                sha=digest,
            )
        )

    lines.extend(["", "## Issues", ""])
    append_bucket_markdown(lines, report["issues"])
    lines.extend(["", "## Warnings", ""])
    append_bucket_markdown(lines, report["warnings"])

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def append_bucket_markdown(lines: list[str], buckets: dict[str, Any]) -> None:
    if not buckets:
        lines.append("None.")
        return
    for kind, payload in buckets.items():
        lines.append(f"### `{kind}`")
        lines.append("")
        lines.append(f"Count: {payload['count']}")
        examples = payload.get("examples", [])
        if examples:
            lines.append("")
            lines.append("Examples:")
            lines.append("")
            for example in examples[:10]:
                lines.append(f"- `{json.dumps(example, sort_keys=True)}`")
        lines.append("")


def format_date_range(start: str | None, end: str | None) -> str:
    if start and end:
        return f"{start} to {end}"
    return "Not available"


def build_stats_block(report: dict[str, Any]) -> str:
    summary = report["summary"]
    generated_at = report["generated_at"]
    return "\n".join(
        [
            STATS_START,
            "| Metric | Value |",
            "| --- | --- |",
            f"| Historical rows | {summary['historical_rows']:,} |",
            f"| Latest rows | {summary['latest_rows']:,} |",
            f"| Unique scheme codes | {summary['unique_scheme_codes']:,} |",
            f"| Date range | {format_date_range(summary['date_min'], summary['date_max'])} |",
            f"| Latest NAV date | {summary['date_max'] or 'Not available'} |",
            f"| Last validation | {generated_at} |",
            f"| Validation status | {report['status']} |",
            STATS_END,
        ]
    )


def update_readme_stats(report: dict[str, Any], readme_path: Path) -> None:
    content = readme_path.read_text(encoding="utf-8")
    start = content.find(STATS_START)
    end = content.find(STATS_END)
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"README stats markers not found in {readme_path}")
    end += len(STATS_END)
    updated = content[:start] + build_stats_block(report) + content[end:]
    readme_path.write_text(updated, encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate mutual fund NAV archive files.")
    parser.add_argument(
        "--input",
        nargs="+",
        default=["data/historical.csv.gz", "data/latest.csv"],
        help="CSV or CSV.GZ files to validate.",
    )
    parser.add_argument(
        "--report-json",
        default="releases/validation-report.json",
        help="Path for JSON validation report.",
    )
    parser.add_argument(
        "--report-md",
        default="releases/validation-report.md",
        help="Path for Markdown validation report.",
    )
    parser.add_argument(
        "--update-readme",
        default=None,
        help="Update README dataset statistics in place.",
    )
    parser.add_argument(
        "--as-of",
        default=date.today().isoformat(),
        help="Validation date used for future-date checks, in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=25,
        help="Maximum examples to retain per issue type.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        as_of = date.fromisoformat(args.as_of)
    except ValueError:
        print(f"Invalid --as-of date: {args.as_of}", file=sys.stderr)
        return 2

    report = build_report([Path(path) for path in args.input], as_of, args.max_examples)
    write_json_report(report, Path(args.report_json))
    write_markdown_report(report, Path(args.report_md))

    if args.update_readme:
        update_readme_stats(report, Path(args.update_readme))

    print(f"Validation status: {report['status']}")
    print(f"Rows checked: {report['summary']['rows']}")
    print(f"Issues: {sum(item['count'] for item in report['issues'].values())}")
    print(f"Warnings: {sum(item['count'] for item in report['warnings'].values())}")

    return 1 if report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
