# Data Directory

This directory contains the public mutual fund NAV archive files.

## Files

| File | Description |
| --- | --- |
| `latest.csv` | Latest available NAV records. |
| `Year/YYYY/MM/DD.csv` | Date-level historical daily NAV records from inception onward. |

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
mapfile -t ARCHIVE_FILES < <(find data/Year -name '*.csv' | sort)
python3 scripts/validation.py --input data/latest.csv "${ARCHIVE_FILES[@]}"
```

The validator checks schema consistency, duplicate keys, missing NAV values, invalid dates, malformed scheme codes, invalid NAV values, and future dates.
