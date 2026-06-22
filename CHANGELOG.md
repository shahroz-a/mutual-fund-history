# Changelog

All notable changes to this dataset repository are documented here.

## Unreleased

- Seeded historical NAV data.
- Added committed monthly CSV archives under `data/by_year/YYYY/MM.csv.gz`.
- Published the complete monolithic `historical.csv.gz` archive as a GitHub Release asset.
- Added data-only release packaging automation.

## 0.1.0 - 2026-06-22

- Added public repository structure for compressed mutual fund NAV archive files.
- Added schema documentation and usage examples.
- Added validation script for duplicate rows, missing NAV values, invalid dates, malformed scheme codes, invalid NAV values, and future dates.
- Added GitHub Actions for validation, README statistics updates, daily publishing, and release creation.
