# mutual-fund-historical-data

Historical daily NAV data for Indian mutual funds. Open-source archive with complete past and continuously updated NAV history.

`mutual-fund-historical-data` is a public dataset repository for historical mutual fund NAV data in India. It is an open-source initiative by [Creget](https://creget.com) for developers, researchers, analysts, and data teams who need downloadable Indian mutual fund NAV history.

This repository focuses only on storing and publishing normalized NAV archive files. Collection methods, update systems, private automation, and operational details are intentionally not exposed in the public repository.

## Overview

This repository publishes historical mutual fund NAV data as plain CSV files from inception onward. The archive targets common discovery and research needs around:

- historical mutual fund nav data
- india mutual fund nav history
- daily mutual fund nav
- mutual fund historical data
- amfi nav history
- mutual fund nav archive
- indian mutual fund dataset

The repository is intentionally simple: browse the files on GitHub, download the CSV data, validate the schema, and query NAV history using standard tools.

## Open Source By Creget

This archive is maintained as an open-source initiative by [Creget](https://creget.com) to make Indian mutual fund NAV history easier to access for public research, data analysis, and software development.

## Dataset Coverage

The dataset is organized as plain CSV files:

- `data/latest.csv`: latest available NAV snapshot.
- `data/Year/YYYY/MM/DD.csv`: date-level historical daily NAV records from inception onward.
- GitHub Releases: published metadata, checksums, validation reports, and the latest snapshot.

<!-- DATASET_STATS_START -->
| Metric | Value |
| --- | --- |
| Historical rows | 36,458,251 |
| Latest rows | 37,360 |
| Unique scheme codes | 37,360 |
| Date range | 2006-04-01 to 2026-06-21 |
| Latest NAV date | 2026-06-21 |
| Last validation | 2026-06-26T17:22:22+00:00 |
| Validation status | passed |
<!-- DATASET_STATS_END -->

## Update Frequency

The repository runs a daily scheduled publish job at 21:00 IST, after Indian market close. Generated dataset files are imported from a private generated-data archive when configured, then validated, checksummed, and published.

Every update should:

1. Import generated NAV archive files from private automation when configured.
2. Validate `data/latest.csv` and `data/Year/YYYY/MM/DD.csv`.
3. Generate validation reports.
4. Generate SHA-256 checksums.
5. Create a GitHub Release containing `latest.csv`, checksums, and validation reports.
6. Update the README statistics block.

## File Format

Files are plain CSV files using UTF-8 text and a header row.

Required column order:

```text
date,scheme_code,scheme_name,nav
```

Formatting rules:

- `date`: ISO 8601 calendar date, `YYYY-MM-DD`.
- `scheme_code`: numeric mutual fund scheme identifier stored as text in CSV.
- `scheme_name`: scheme name as text.
- `nav`: positive decimal NAV value using `.` as the decimal separator.

See [docs/schema.md](docs/schema.md) for the full schema.

## Download Instructions

Download CSV files directly from the repository:

```bash
curl -L -o latest.csv https://raw.githubusercontent.com/shahroz-a/mutual-fund-historical-data/mutual-fund-historical-data/data/latest.csv
curl -L -o 2026-06-21.csv https://raw.githubusercontent.com/shahroz-a/mutual-fund-historical-data/mutual-fund-historical-data/data/Year/2026/06/21.csv
```

Download the latest snapshot and metadata from the latest GitHub Release:

```bash
curl -L -o latest.csv https://github.com/shahroz-a/mutual-fund-historical-data/releases/latest/download/latest.csv
curl -L -o checksums.sha256 https://github.com/shahroz-a/mutual-fund-historical-data/releases/latest/download/checksums.sha256
shasum -a 256 -c checksums.sha256 --ignore-missing
```

## GitHub Data Access

This repository does not run a hosted API server. For lightweight API-like access, you can use GitHub-hosted CSV files directly:

```text
https://raw.githubusercontent.com/shahroz-a/mutual-fund-historical-data/mutual-fund-historical-data/data/latest.csv
https://raw.githubusercontent.com/shahroz-a/mutual-fund-historical-data/mutual-fund-historical-data/data/Year/2026/06/21.csv
https://github.com/shahroz-a/mutual-fund-historical-data/releases/latest/download/latest.csv
```

Applications can also use the GitHub Contents API or Release Assets API, subject to GitHub rate limits.

## Schema

| Column | Type | Required | Description |
| --- | --- | --- | --- |
| `date` | date | Yes | NAV date in ISO format, `YYYY-MM-DD`. |
| `scheme_code` | string | Yes | Numeric Indian mutual fund scheme code. |
| `scheme_name` | string | Yes | Scheme name. |
| `nav` | decimal | Yes | Positive net asset value. |

## Sample Queries

Python standard library:

```python
import csv

with open("data/Year/2026/06/21.csv", newline="", encoding="utf-8") as f:
    rows = csv.DictReader(f)
    scheme_rows = [row for row in rows if row["scheme_code"] == "120503"]

print(scheme_rows[:5])
```

Pandas:

```python
from glob import glob
import pandas as pd

df = pd.concat(
    pd.read_csv(path, parse_dates=["date"])
    for path in glob("data/Year/*/*/*.csv")
)
scheme = df[df["scheme_code"].astype(str) == "120503"].sort_values("date")
scheme["one_year_return"] = scheme["nav"].pct_change(periods=252)
```

DuckDB:

```sql
SELECT date, scheme_code, scheme_name, nav
FROM read_csv('data/Year/*/*/*.csv', header=true)
WHERE scheme_code = '120503'
ORDER BY date;
```

SQLite:

```bash
python3 - <<'PY'
import csv
import sqlite3
from glob import glob

con = sqlite3.connect("mutual_fund_nav.db")
con.execute("""
CREATE TABLE IF NOT EXISTS nav (
  date TEXT NOT NULL,
  scheme_code TEXT NOT NULL,
  scheme_name TEXT NOT NULL,
  nav REAL NOT NULL,
  PRIMARY KEY (date, scheme_code)
)
""")

for path in glob("data/Year/*/*/*.csv"):
    with open(path, newline="", encoding="utf-8") as f:
        con.executemany(
            "INSERT OR REPLACE INTO nav VALUES (:date, :scheme_code, :scheme_name, :nav)",
            csv.DictReader(f),
        )

con.commit()
PY
```

More examples are available in [docs/examples.md](docs/examples.md).

## Use Cases

- Backtesting mutual fund strategies using historical NAV data.
- Researching India mutual fund NAV history across schemes and time periods.
- Building local datasets for portfolio analysis and financial research.
- Studying long-term scheme behavior, drawdowns, and point-to-point returns.
- Powering internal tools that need reproducible daily NAV archives.
- Teaching data analysis with a real Indian mutual fund dataset.
- Creating offline mirrors of public mutual fund historical data.

## FAQ

### Is this an API?

No hosted API is provided. The archive is published as downloadable files, and GitHub raw/release URLs can be used for simple file-based access.

### Does this repository expose collection methods?

No. This public repository intentionally does not disclose collection methods, private automation, private endpoints, or operational update systems.

### Does this repository expose an API or website?

No. This repository only publishes CSV dataset files, checksums, and validation reports.

### What files should I use?

Use `data/latest.csv` for the latest snapshot and `data/Year/YYYY/MM/DD.csv` for complete date-specific history from inception onward.

### How do I verify downloads?

Use the `checksums.sha256` file attached to each GitHub Release:

```bash
shasum -a 256 -c checksums.sha256 --ignore-missing
```

### Can I contribute data corrections?

Yes. See [CONTRIBUTING.md](CONTRIBUTING.md). Contributions should be limited to dataset corrections, documentation, validation improvements, and repository metadata.

## License

This repository is released under the MIT License. See [LICENSE](LICENSE).
