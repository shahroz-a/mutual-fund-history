#!/usr/bin/env python3
"""Build release archives from public daily CSV chunks."""

from __future__ import annotations

import argparse
import gzip
import io
import sys
from pathlib import Path


HEADER = "date,scheme_code,scheme_name,nav\n"


def daily_files(data_dir: Path) -> list[Path]:
    return sorted((data_dir / "Year").glob("*/*/*.csv.gz"))


def build_historical(data_dir: Path, output: Path) -> int:
    files = daily_files(data_dir)
    if not files:
        raise RuntimeError(f"No daily archive files found in {data_dir / 'Year'}")

    output.parent.mkdir(parents=True, exist_ok=True)
    raw = output.open("wb")
    gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=6, mtime=0)
    text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
    rows = 0
    try:
        text.write(HEADER)
        for path in files:
            with gzip.open(path, "rt", newline="", encoding="utf-8") as f:
                header = f.readline()
                if header != HEADER:
                    raise RuntimeError(f"Unexpected header in {path}: {header!r}")
                for line in f:
                    text.write(line)
                    rows += 1
    finally:
        text.close()
        raw.close()
    print(f"Wrote {output} from {len(files)} daily files ({rows:,} rows)")
    return rows


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build release archives from public data chunks.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--historical-output", default="data/historical.csv.gz")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    build_historical(Path(args.data_dir), Path(args.historical_output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
