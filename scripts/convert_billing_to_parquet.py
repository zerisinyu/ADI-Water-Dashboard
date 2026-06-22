"""
Convert Data/billing.csv -> Data/billing.parquet (pre-typed, ZSTD-compressed).

The raw billing CSV is ~54 MB / 694k rows and was being parsed into in-memory
DuckDB on every cold start, which dominated the app's wake-up time. Storing it
as pre-typed Parquet shrinks it to ~14 MB and makes the load a straight
columnar read (no per-row casting), cutting cold-start time significantly.

The transforms below mirror exactly what the old CSV `load_sql` in
data/database.py did (date parsing, country title-casing, header-row filter),
so the resulting table is byte-for-byte equivalent to the previous behaviour.

Usage (from repo root):
    python scripts/convert_billing_to_parquet.py
"""
from __future__ import annotations

from pathlib import Path

import duckdb

DATA_DIR = Path(__file__).resolve().parents[1] / "Data"
SRC = DATA_DIR / "billing.csv"
DST = DATA_DIR / "billing.parquet"


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Source not found: {SRC}")

    con = duckdb.connect()
    con.execute(
        f"""
        COPY (
            SELECT
                CAST(customer_id AS INTEGER)        AS customer_id,
                strptime(date, '%m/%d/%Y')::DATE    AS date,
                CAST(consumption_m3 AS DOUBLE)      AS consumption_m3,
                CAST(billed AS DOUBLE)              AS billed,
                CAST(paid AS DOUBLE)               AS paid,
                CONCAT(UPPER(SUBSTR(TRIM(country), 1, 1)),
                       LOWER(SUBSTR(TRIM(country), 2))) AS country,
                TRIM(zone)                          AS zone,
                TRIM(source)                        AS source
            FROM read_csv_auto('{SRC}', header=true, all_varchar=true, ignore_errors=true)
            WHERE customer_id != 'customer_id'
        ) TO '{DST}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )
    rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{DST}')").fetchone()[0]
    print(f"Wrote {DST} ({rows:,} rows, {DST.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
