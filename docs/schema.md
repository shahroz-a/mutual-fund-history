# Dataset Schema

The dataset uses a single normalized CSV schema for both historical and latest NAV files.

## Required Header

```text
date,scheme_code,scheme_name,nav
```

Column order is part of the public contract.

## Columns

| Column | Type | Required | Format | Notes |
| --- | --- | --- | --- | --- |
| `date` | date | Yes | `YYYY-MM-DD` | ISO 8601 calendar date for the NAV record. |
| `scheme_code` | string | Yes | Digits only | Stored as text to avoid accidental numeric coercion. |
| `scheme_name` | string | Yes | UTF-8 text | Scheme name as published in the generated dataset. |
| `nav` | decimal | Yes | Positive decimal | Use `.` as decimal separator. No commas or currency symbols. |

## CSV Rules

- Files must be UTF-8 encoded plain CSV.
- Files must include a header row.
- Dates must not be in the future.
- `scheme_code` must be non-empty and numeric.
- `nav` must be non-empty, numeric, finite, and greater than zero.
- The pair `(date, scheme_code)` must be unique within each file.

## Example Rows

```csv
date,scheme_code,scheme_name,nav
2024-01-01,120503,Example Mutual Fund - Growth,123.4567
2024-01-02,120503,Example Mutual Fund - Growth,123.8912
```

## Stability

The schema is intentionally small and stable. Additive fields should be avoided unless there is a strong archival need. Breaking schema changes should be announced in `CHANGELOG.md` and released with clear migration notes.
