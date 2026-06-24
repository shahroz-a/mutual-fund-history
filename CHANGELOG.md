# Changelog

All notable changes to this dataset repository are documented here.

## Unreleased

- Converted the full historical archive to plain CSV files under `data/Year/YYYY/MM/DD.csv` from inception onward.
- Removed old non-CSV archive files from the public data archive.
- Updated validation, checksum, release, and daily publish workflows for CSV-only data.
- Seeded historical NAV data.
- Added data-only release packaging automation with private generated-archive import support.

## 0.1.0 - 2026-06-22

- Added public repository structure for mutual fund NAV archive files.
- Added schema documentation and usage examples.
- Added validation script for duplicate rows, missing NAV values, invalid dates, malformed scheme codes, invalid NAV values, and future dates.
- Added GitHub Actions for validation, README statistics updates, daily publishing, and release creation.
