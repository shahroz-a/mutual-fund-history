# Contributing

Thank you for helping improve `mutual-fund-historical-data`.

This repository is a public archive for generated Indian mutual fund NAV data. Contributions should keep the repository simple, reliable, and focused on downloadable dataset files.

## Accepted Contributions

- Dataset corrections to `data/latest.csv`, `data/Year/YYYY/MM/DD.csv`, or `data/Year/YYYY/MM/DD.csv.gz`.
- Validation improvements in `scripts/validation.py`.
- Documentation improvements in `README.md`, `data/README.md`, or `docs/`.
- Release metadata and checksum workflow improvements.

## Not Accepted

Do not submit:

- private or undocumented collection details
- scraping logic for private or undocumented endpoints
- private ingestion logic
- private ETL pipelines
- private endpoint references
- private automation logic
- secrets, tokens, cookies, credentials, or internal URLs
- APIs, websites, dashboards, analytics apps, or hosted services

Private collection methods must not be included in this public repository.

## Data Format

Dataset files must use this header:

```text
date,scheme_code,scheme_name,nav
```

Before opening a pull request, run:

```bash
mapfile -t ARCHIVE_FILES < <(find data/Year -name '*.csv.gz' | sort)
python3 scripts/validation.py --input data/latest.csv "${ARCHIVE_FILES[@]}"
```

## Pull Request Checklist

- The repository remains dataset-only.
- No private collection, scraping, ETL, endpoint, credential, or internal automation details are included.
- CSV files validate successfully.
- Documentation is updated if the public schema or release process changes.
- Large changes include a short explanation of what changed in the dataset.

## Reporting Data Issues

When reporting a data issue, include:

- `scheme_code`
- `scheme_name`, if known
- affected `date` or date range
- expected value
- observed value

Do not include private endpoints or private collection details.
