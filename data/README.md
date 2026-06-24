# Data Directory

This directory contains the public mutual fund NAV archive files.

## Files

| File | Description |
| --- | --- |
| `latest.csv` | Browser-visible latest available NAV records. |
| `Year/YYYY/MM/DD.csv` | Browser-visible daily NAV files for the latest archive year and future updates. |
| `Year/YYYY/MM/DD.csv.gz` | Compressed date-level historical daily NAV records for the complete archive. |
| `historical.csv.gz` | Complete monolithic historical daily NAV records. Too large for normal Git storage; published as a release asset. |
| `latest.csv.gz` | Compressed latest snapshot generated for GitHub Releases. |

All CSV files use this required header:

```text
date,scheme_code,scheme_name,nav
```

## Publication Model

Generated dataset files are published here. Collection methods, private automation, private endpoints, and operational update systems are intentionally not included in this public repository.

Do not add:

- internal automation secrets
- private endpoints
- credentials, cookies, or tokens
- APIs, websites, dashboards, or analytics apps

## Validation

Run:

```bash
mapfile -t ARCHIVE_FILES < <(find data/Year -name '*.csv.gz' | sort)
python3 scripts/validation.py --input data/latest.csv "${ARCHIVE_FILES[@]}"
```

The validator checks schema consistency, duplicate keys, missing NAV values, invalid dates, malformed scheme codes, invalid NAV values, and future dates.
