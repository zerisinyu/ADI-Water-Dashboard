"""
DuckDB-backed analytical data layer for the Water Utility Dashboard.

Replaces raw pd.read_csv() calls with an in-process columnar database that
supports SQL queries, type enforcement, and incremental reloading.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "Data"


def _default_db_path() -> str:
    """Persist the DuckDB to a gitignored on-disk file by default so the tables
    and derived views survive process restarts / Streamlit's `runOnSave` module
    reloads — turning cold rebuilds into a fast warm open. Falls back to
    in-memory if the cache directory can't be created. Override with DUCKDB_PATH.
    """
    env = os.environ.get("DUCKDB_PATH")
    if env:
        return env
    try:
        cache_dir = DATA_DIR / ".cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return str(cache_dir / "dashboard.duckdb")
    except Exception:
        return ":memory:"


_DB_PATH = _default_db_path()

# Views the ETL pipeline (data/pipeline.py) materialises. Used to detect a warm
# persistent DB so the pipeline can be skipped.
EXPECTED_VIEWS = (
    "v_billing_monthly",
    "v_production_monthly",
    "v_nrw_monthly",
    "v_service_quality",
    "v_financial_monthly",
)

_conn: Optional[duckdb.DuckDBPyConnection] = None
_initialized: bool = False

# CSV-to-table mapping with column type overrides
TABLE_DEFINITIONS: dict[str, dict] = {
    "billing": {
        # Stored as pre-typed Parquet instead of a 54 MB CSV. DuckDB reads it
        # ~4x smaller and far faster, which is the biggest lever on cold-start
        # and wake-up time. The CSV-era transforms (date parsing, country
        # title-casing, header-row filtering) were applied once at conversion
        # time, so the load here is a straight columnar read.
        # Regenerate via scripts/convert_billing_to_parquet.py if data changes.
        "file": "billing.parquet",
        "ddl": """
            CREATE TABLE IF NOT EXISTS billing (
                customer_id   INTEGER,
                date          DATE,
                consumption_m3 DOUBLE,
                billed        DOUBLE,
                paid          DOUBLE,
                country       VARCHAR,
                zone          VARCHAR,
                source        VARCHAR
            )
        """,
        "load_sql": """
            INSERT INTO billing
            SELECT customer_id, date, consumption_m3, billed, paid, country, zone, source
            FROM read_parquet('{path}')
        """,
    },
    "production": {
        "file": "production.csv",
        "ddl": """
            CREATE TABLE IF NOT EXISTS production (
                date          DATE,
                source        VARCHAR,
                production_m3 DOUBLE,
                service_hours DOUBLE,
                country       VARCHAR
            )
        """,
        "load_sql": """
            INSERT INTO production
            SELECT
                strptime(TRIM(date_YYMMDD), '%Y/%m/%d')::DATE,
                TRIM(source),
                CAST(production_m3 AS DOUBLE),
                CAST(service_hours AS DOUBLE),
                CONCAT(UPPER(SUBSTR(TRIM(country), 1, 1)), LOWER(SUBSTR(TRIM(country), 2)))
            FROM read_csv_auto('{path}', header=true, all_varchar=true, ignore_errors=true)
        """,
    },
    "sw_service": {
        "file": "sw_service.csv",
        "ddl": """
            CREATE TABLE IF NOT EXISTS sw_service (
                country       VARCHAR,
                city          VARCHAR,
                zone          VARCHAR,
                month         INTEGER,
                year          INTEGER,
                date_label    VARCHAR,
                w_supplied    DOUBLE,
                total_consumption DOUBLE,
                metered       DOUBLE,
                ww_capacity   DOUBLE,
                tests_chlorine INTEGER,
                tests_ecoli    INTEGER,
                tests_conducted_chlorine INTEGER,
                test_conducted_ecoli INTEGER,
                test_passed_chlorine INTEGER,
                tests_passed_ecoli INTEGER,
                complaints    INTEGER,
                resolved      INTEGER,
                complaint_resolution DOUBLE,
                sewer_connections INTEGER,
                public_toilets INTEGER,
                workforce     INTEGER,
                f_workforce   INTEGER,
                hh_emptied    INTEGER,
                fs_treated    DOUBLE,
                fs_reused     DOUBLE,
                ww_collected  DOUBLE,
                ww_treated    DOUBLE,
                ww_reused     DOUBLE,
                households    INTEGER
            )
        """,
        "load_sql": """
            INSERT INTO sw_service
            SELECT
                CONCAT(UPPER(SUBSTR(TRIM(country), 1, 1)), LOWER(SUBSTR(TRIM(country), 2))),
                TRIM(city),
                TRIM(zone),
                CAST(month AS INTEGER),
                CAST(year AS INTEGER),
                TRIM(date),
                CAST(w_supplied AS DOUBLE),
                CAST(total_consumption AS DOUBLE),
                CAST(metered AS DOUBLE),
                CAST(ww_capacity AS DOUBLE),
                CAST(tests_chlorine AS INTEGER),
                CAST(tests_ecoli AS INTEGER),
                CAST(tests_conducted_chlorine AS INTEGER),
                CAST(test_conducted_ecoli AS INTEGER),
                CAST(test_passed_chlorine AS INTEGER),
                CAST(tests_passed_ecoli AS INTEGER),
                CAST(complaints AS INTEGER),
                CAST(resolved AS INTEGER),
                CAST(complaint_resolution AS DOUBLE),
                CAST(sewer_connections AS INTEGER),
                CAST(public_toilets AS INTEGER),
                CAST(workforce AS INTEGER),
                CAST(f_workforce AS INTEGER),
                CAST(hh_emptied AS INTEGER),
                CAST(fs_treated AS DOUBLE),
                CAST(fs_reused AS DOUBLE),
                CAST(ww_collected AS DOUBLE),
                CAST(ww_treated AS DOUBLE),
                CAST(ww_reused AS DOUBLE),
                CAST(households AS INTEGER)
            FROM read_csv_auto('{path}', header=true, all_varchar=true, ignore_errors=true)
        """,
    },
    "w_access": {
        "file": "w_access.csv",
        "ddl": """
            CREATE TABLE IF NOT EXISTS w_access (
                country       VARCHAR,
                zone          VARCHAR,
                year          INTEGER,
                w_safely_managed DOUBLE,
                w_safely_managed_pct DOUBLE,
                w_basic       DOUBLE,
                w_basic_pct   DOUBLE,
                w_limited     DOUBLE,
                w_limited_pct DOUBLE,
                w_unimproved  DOUBLE,
                w_unimproved_pct DOUBLE,
                surface_water DOUBLE,
                surface_water_pct DOUBLE,
                w_other_pct   DOUBLE,
                popn_total    DOUBLE,
                households    INTEGER,
                municipal_coverage DOUBLE,
                type          VARCHAR
            )
        """,
        "load_sql": """
            INSERT INTO w_access
            SELECT
                CONCAT(UPPER(SUBSTR(TRIM(country), 1, 1)), LOWER(SUBSTR(TRIM(country), 2))),
                TRIM(zone),
                CAST(year AS INTEGER),
                CAST(w_safely_managed AS DOUBLE),
                CAST(w_safely_managed_pct AS DOUBLE),
                CAST(w_basic AS DOUBLE),
                CAST(w_basic_pct AS DOUBLE),
                CAST(w_limited AS DOUBLE),
                CAST(w_limited_pct AS DOUBLE),
                CAST(w_unimproved AS DOUBLE),
                CAST(w_unimproved_pct AS DOUBLE),
                CAST(surface_water AS DOUBLE),
                CAST(surface_water_pct AS DOUBLE),
                CAST(w_other_pct AS DOUBLE),
                CAST(popn_total AS DOUBLE),
                CAST(households AS INTEGER),
                CAST(municipal_coverage AS DOUBLE),
                TRIM(type)
            FROM read_csv_auto('{path}', header=true, all_varchar=true, ignore_errors=true)
        """,
    },
    "s_access": {
        "file": "s_access.csv",
        "ddl": """
            CREATE TABLE IF NOT EXISTS s_access (
                country       VARCHAR,
                zone          VARCHAR,
                year          INTEGER,
                s_safely_managed DOUBLE,
                s_safely_managed_pct DOUBLE,
                s_basic       DOUBLE,
                s_basic_pct   DOUBLE,
                s_limited     DOUBLE,
                s_limited_pct DOUBLE,
                s_unimproved  DOUBLE,
                s_unimproved_pct DOUBLE,
                open_def      DOUBLE,
                open_def_pct  DOUBLE,
                s_other_pct   DOUBLE,
                popn_total    DOUBLE,
                households    INTEGER,
                type          VARCHAR
            )
        """,
        "load_sql": """
            INSERT INTO s_access
            SELECT
                CONCAT(UPPER(SUBSTR(TRIM(country), 1, 1)), LOWER(SUBSTR(TRIM(country), 2))),
                TRIM(zone),
                CAST(year AS INTEGER),
                CAST(s_safely_managed AS DOUBLE),
                CAST(s_safely_managed_pct AS DOUBLE),
                CAST(s_basic AS DOUBLE),
                CAST(s_basic_pct AS DOUBLE),
                CAST(s_limited AS DOUBLE),
                CAST(s_limited_pct AS DOUBLE),
                CAST(s_unimproved AS DOUBLE),
                CAST(s_unimproved_pct AS DOUBLE),
                CAST(open_def AS DOUBLE),
                CAST(open_def_pct AS DOUBLE),
                CAST(s_other_pct AS DOUBLE),
                CAST(popn_total AS DOUBLE),
                CAST(households AS INTEGER),
                TRIM(type)
            FROM read_csv_auto('{path}', header=true, all_varchar=true, ignore_errors=true)
        """,
    },
    "fin_service": {
        "file": "all_fin_service.csv",
        "ddl": """
            CREATE TABLE IF NOT EXISTS fin_service (
                country       VARCHAR,
                city          VARCHAR,
                date          DATE,
                date_label    VARCHAR,
                sewer_length  DOUBLE,
                complaints    INTEGER,
                resolved      INTEGER,
                blocks        INTEGER,
                sewer_billed  DOUBLE,
                sewer_revenue DOUBLE,
                opex          DOUBLE,
                san_staff     INTEGER,
                w_staff       INTEGER,
                propoor_popn  DOUBLE
            )
        """,
        "load_sql": """
            INSERT INTO fin_service
            SELECT
                CONCAT(UPPER(SUBSTR(TRIM(country), 1, 1)), LOWER(SUBSTR(TRIM(country), 2))),
                TRIM(city),
                strptime(TRIM(date_MMYY), '%b/%y')::DATE,
                TRIM(date_MMYY),
                CAST(sewer_length AS DOUBLE),
                CAST(complaints AS INTEGER),
                CAST(resolved AS INTEGER),
                CAST(blocks AS INTEGER),
                CAST(sewer_billed AS DOUBLE),
                CAST(sewer_revenue AS DOUBLE),
                CAST(opex AS DOUBLE),
                CAST(san_staff AS INTEGER),
                CAST(w_staff AS INTEGER),
                CAST(propoor_popn AS DOUBLE)
            FROM read_csv_auto('{path}', header=true, all_varchar=true, ignore_errors=true)
        """,
    },
    "national_accounts": {
        "file": "all_nationalacc.csv",
        "ddl": """
            CREATE TABLE IF NOT EXISTS national_accounts (
                country       VARCHAR,
                city          VARCHAR,
                year          INTEGER,
                budget_allocated DOUBLE,
                san_allocation DOUBLE,
                wat_allocation DOUBLE,
                staff_cost    DOUBLE,
                water_resources DOUBLE,
                trained_staff INTEGER,
                complaint_resolution DOUBLE,
                registered_wtps INTEGER,
                inspected_wtps INTEGER,
                total_service_providers INTEGER,
                licensed_service_providers INTEGER,
                asset_health  DOUBLE,
                staff_training_budget DOUBLE
            )
        """,
        "load_sql": """
            INSERT INTO national_accounts
            SELECT
                CONCAT(UPPER(SUBSTR(TRIM(country), 1, 1)), LOWER(SUBSTR(TRIM(country), 2))),
                TRIM(city),
                CAST(date_YY AS INTEGER),
                CAST(budget_allocated AS DOUBLE),
                CAST(san_allocation AS DOUBLE),
                CAST(wat_allocation AS DOUBLE),
                CAST(staff_cost AS DOUBLE),
                CAST(water_resources AS DOUBLE),
                CAST(trained_staff AS INTEGER),
                CAST(complaint_resolution AS DOUBLE),
                CAST(registered_wtps AS INTEGER),
                CAST(inspected_wtps AS INTEGER),
                CAST(total_service_providers AS INTEGER),
                CAST(licensed_service_providers AS INTEGER),
                CAST(asset_health AS DOUBLE),
                CAST(staff_training_budget AS DOUBLE)
            FROM read_csv_auto('{path}', header=true, all_varchar=true, ignore_errors=true)
        """,
    },
}

# Track file modification times for incremental reloading
_file_mtimes: dict[str, float] = {}


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return the singleton DuckDB connection, creating it on first call.

    If the on-disk path can't be opened (read-only FS, lock, corrupt file) we
    fall back to an in-memory DB so the app still works.
    """
    global _conn, _DB_PATH
    if _conn is None:
        try:
            _conn = duckdb.connect(_DB_PATH)
            logger.info("DuckDB connection opened (%s)", _DB_PATH)
        except Exception:
            logger.warning("Could not open DuckDB at %s — using in-memory", _DB_PATH)
            _DB_PATH = ":memory:"
            _conn = duckdb.connect(_DB_PATH)
    return _conn


def _db_build_time() -> float:
    """mtime of the persisted DB file (0 for in-memory / missing)."""
    if _DB_PATH == ":memory:":
        return 0.0
    p = Path(_DB_PATH)
    return p.stat().st_mtime if p.exists() else 0.0


def _relation_exists(conn: duckdb.DuckDBPyConnection, name: str) -> bool:
    """True if a table or view by this name exists and is queryable."""
    try:
        conn.execute(f"SELECT 1 FROM {name} LIMIT 1")
        return True
    except Exception:
        return False


def is_warm_and_fresh() -> bool:
    """True when a persistent DB already holds every source table AND every
    derived view, and no source file is newer than the DB — i.e. the ETL
    pipeline (extract + validate + transform) can be skipped entirely.
    Always False for in-memory so cold starts behave exactly as before.
    """
    if _DB_PATH == ":memory:":
        return False
    try:
        conn = get_connection()
        db_time = _db_build_time()
        if db_time == 0.0:
            return False
        for table_name, cfg in TABLE_DEFINITIONS.items():
            if not _relation_exists(conn, table_name):
                return False
            src = DATA_DIR / cfg["file"]
            if src.exists() and src.stat().st_mtime > db_time:
                return False  # source changed since the DB was built
        return all(_relation_exists(conn, v) for v in EXPECTED_VIEWS)
    except Exception:
        return False


def _file_changed(table_name: str) -> bool:
    """Check if the source CSV has been modified since last load."""
    cfg = TABLE_DEFINITIONS[table_name]
    path = DATA_DIR / cfg["file"]
    if not path.exists():
        return False
    current_mtime = path.stat().st_mtime
    last_mtime = _file_mtimes.get(table_name, 0.0)
    return current_mtime > last_mtime


def _load_table(conn: duckdb.DuckDBPyConnection, table_name: str) -> int:
    """Load (or reload) a single table from its CSV source. Returns row count."""
    cfg = TABLE_DEFINITIONS[table_name]
    path = DATA_DIR / cfg["file"]
    if not path.exists():
        logger.warning("Source file missing: %s", path)
        return 0

    conn.execute(f"DROP TABLE IF EXISTS {table_name}")
    conn.execute(cfg["ddl"])

    load_sql = cfg["load_sql"].format(path=str(path))
    conn.execute(load_sql)

    row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    _file_mtimes[table_name] = path.stat().st_mtime
    logger.info("Loaded %s: %d rows from %s", table_name, row_count, cfg["file"])
    return row_count


def init_database(force: bool = False) -> dict[str, int]:
    """
    Initialise all tables from CSV sources.

    Args:
        force: If True, reload all tables regardless of file modification time.

    Returns:
        Dict mapping table name -> row count for each loaded table.
    """
    global _initialized
    conn = get_connection()
    counts: dict[str, int] = {}
    db_time = _db_build_time()

    for table_name, cfg in TABLE_DEFINITIONS.items():
        src = DATA_DIR / cfg["file"]
        src_mtime = src.stat().st_mtime if src.exists() else 0.0
        # Reload only when forced, the table is absent (cold / in-memory), or the
        # source file is newer than both the persisted DB and this process's last
        # load — so a warm on-disk DB reuses its tables instead of re-ingesting.
        stale = src_mtime > max(db_time, _file_mtimes.get(table_name, 0.0))
        if force or not _relation_exists(conn, table_name) or stale:
            try:
                counts[table_name] = _load_table(conn, table_name)
            except Exception:
                logger.exception("Failed to load table %s", table_name)
                counts[table_name] = 0
        else:
            counts[table_name] = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            _file_mtimes[table_name] = src_mtime

    _initialized = True
    return counts


def query(sql: str, params: Optional[list] = None) -> pd.DataFrame:
    """
    Execute a read-only SQL query and return a DataFrame.

    The database is auto-initialised on first query.
    """
    if not _initialized:
        init_database()
    conn = get_connection()
    if params:
        return conn.execute(sql, params).fetchdf()
    return conn.execute(sql).fetchdf()


def get_table_schemas() -> str:
    """Return DDL for all tables, useful for text-to-SQL prompts."""
    parts = []
    for name, cfg in TABLE_DEFINITIONS.items():
        parts.append(cfg["ddl"].strip())
    return "\n\n".join(parts)


def get_table_stats() -> list[dict]:
    """Return row counts and column counts for all loaded tables."""
    if not _initialized:
        init_database()
    conn = get_connection()
    stats = []
    for table_name in TABLE_DEFINITIONS:
        try:
            row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            col_count = len(conn.execute(f"DESCRIBE {table_name}").fetchdf())
            stats.append({"table": table_name, "rows": row_count, "columns": col_count})
        except Exception:
            stats.append({"table": table_name, "rows": 0, "columns": 0})
    return stats
