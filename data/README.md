# Data Directory

This directory contains the public mutual fund NAV archive files.

## Files

| File | Description |
| --- | --- |
| `historical.csv.gz` | Complete monolithic historical daily NAV records. Too large for normal Git storage; published as a release asset. |
| `latest.csv.gz` | Latest available NAV records. |
| `Year/YYYY/MM/DD.csv.gz` | Date-level historical daily NAV records committed to the repository. |

All CSV files are gzip-compressed with this required header:

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
python3 scripts/validation.py --input data/latest.csv.gz data/Year/*/*/*.csv.gz
```

The validator checks schema consistency, duplicate keys, missing NAV values, invalid dates, malformed scheme codes, invalid NAV values, and future dates.
