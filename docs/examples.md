# Examples

These examples show how to load, filter, and analyze the mutual fund NAV archive using common local tools.

## Python

Load records with only the Python standard library:

```python
import csv
import gzip
from glob import glob

scheme_code = "120503"
rows = []

for path in glob("data/by_year/*/*.csv.gz"):
    with gzip.open(path, "rt", newline="", encoding="utf-8") as f:
        rows.extend(
            row
            for row in csv.DictReader(f)
            if row["scheme_code"] == scheme_code
        )

rows.sort(key=lambda row: row["date"])
print(rows[:5])
```

Calculate a simple point-to-point return:

```python
from decimal import Decimal

first = Decimal(rows[0]["nav"])
last = Decimal(rows[-1]["nav"])
total_return = (last / first) - Decimal("1")

print(f"{total_return:.2%}")
```

## Pandas

Load the archive:

```python
import pandas as pd
from glob import glob

df = pd.concat(
    pd.read_csv(
        path,
        dtype={"scheme_code": "string", "scheme_name": "string"},
        parse_dates=["date"],
    )
    for path in glob("data/by_year/*/*.csv.gz")
)
```

Filter one scheme and calculate trailing returns:

```python
scheme = (
    df[df["scheme_code"] == "120503"]
    .sort_values("date")
    .copy()
)

scheme["daily_return"] = scheme["nav"].pct_change()
scheme["one_year_return"] = scheme["nav"].pct_change(periods=252)

print(scheme.tail())
```

Find the latest NAV for each scheme:

```python
latest_by_scheme = (
    df.sort_values(["scheme_code", "date"])
    .groupby("scheme_code", as_index=False)
    .tail(1)
)
```

## DuckDB

Query the gzip file directly:

```sql
SELECT date, scheme_code, scheme_name, nav
FROM read_csv(
  'data/by_year/*/*.csv.gz',
  compression = 'gzip',
  header = true
)
WHERE scheme_code = '120503'
ORDER BY date;
```

Calculate returns with SQL:

```sql
WITH nav_history AS (
  SELECT
    CAST(date AS DATE) AS nav_date,
    scheme_code,
    scheme_name,
    CAST(nav AS DOUBLE) AS nav
  FROM read_csv('data/by_year/*/*.csv.gz', compression='gzip', header=true)
  WHERE scheme_code = '120503'
),
ranked AS (
  SELECT
    *,
    FIRST_VALUE(nav) OVER (ORDER BY nav_date) AS first_nav,
    LAST_VALUE(nav) OVER (
      ORDER BY nav_date
      ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    ) AS last_nav
  FROM nav_history
)
SELECT
  MIN(nav_date) AS start_date,
  MAX(nav_date) AS end_date,
  MAX((last_nav / first_nav) - 1) AS total_return
FROM ranked;
```

Create a local DuckDB table:

```sql
CREATE TABLE nav AS
SELECT
  CAST(date AS DATE) AS date,
  scheme_code,
  scheme_name,
  CAST(nav AS DOUBLE) AS nav
FROM read_csv('data/by_year/*/*.csv.gz', compression='gzip', header=true);

CREATE INDEX nav_scheme_date ON nav (scheme_code, date);
```

## SQLite

SQLite cannot read gzip files directly, but the Python standard library can load the compressed CSV into SQLite:

```python
import csv
import gzip
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

for path in glob("data/by_year/*/*.csv.gz"):
    with gzip.open(path, "rt", newline="", encoding="utf-8") as f:
        con.executemany(
            """
            INSERT OR REPLACE INTO nav
            (date, scheme_code, scheme_name, nav)
            VALUES (:date, :scheme_code, :scheme_name, :nav)
            """,
            csv.DictReader(f),
        )

con.execute("CREATE INDEX IF NOT EXISTS nav_scheme_date ON nav (scheme_code, date)")
con.commit()
```

Query latest NAV by scheme:

```sql
SELECT date, scheme_code, scheme_name, nav
FROM nav
WHERE scheme_code = '120503'
ORDER BY date DESC
LIMIT 1;
```

Calculate a point-to-point return:

```sql
WITH first_last AS (
  SELECT
    FIRST_VALUE(nav) OVER (ORDER BY date) AS first_nav,
    FIRST_VALUE(nav) OVER (ORDER BY date DESC) AS last_nav
  FROM nav
  WHERE scheme_code = '120503'
)
SELECT ((last_nav / first_nav) - 1) AS total_return
FROM first_last
LIMIT 1;
```
