# Changelog

All notable changes to this dataset repository are documented here.

## Unreleased

- Seeded historical NAV data.
- Reorganized committed archive files under `data/Year/YYYY/MM/DD.csv.gz`.
- Published the complete monolithic `historical.csv.gz` archive as a GitHub Release asset.
- Added data-only release packaging automation with private generated-archive import support.

## 0.1.0 - 2026-06-22

- Added public repository structure for compressed mutual fund NAV archive files.
- Added schema documentation and usage examples.
- Added validation script for duplicate rows, missing NAV values, invalid dates, malformed scheme codes, invalid NAV values, and future dates.
- Added GitHub Actions for validation, README statistics updates, daily publishing, and release creation.
