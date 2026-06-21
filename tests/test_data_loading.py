"""
Tests for the DuckDB data layer and ETL pipeline.
"""
import os
from pathlib import Path

import pandas as pd
import pytest


def test_table_definitions_complete():
    """All 7 expected tables are defined."""
    from data.database import TABLE_DEFINITIONS

    expected = {"billing", "production", "sw_service", "w_access", "s_access", "fin_service", "national_accounts"}
    assert set(TABLE_DEFINITIONS.keys()) == expected


def test_each_table_has_required_keys():
    """Each table definition has file, ddl, and load_sql."""
    from data.database import TABLE_DEFINITIONS

    for name, cfg in TABLE_DEFINITIONS.items():
        assert "file" in cfg, f"{name} missing 'file'"
        assert "ddl" in cfg, f"{name} missing 'ddl'"
        assert "load_sql" in cfg, f"{name} missing 'load_sql'"


def test_get_connection_returns_duckdb():
    """get_connection returns a DuckDB connection object."""
    import data.database as db

    # Reset module state for isolated test
    old_conn = db._conn
    db._conn = None
    try:
        conn = db.get_connection()
        assert conn is not None
        result = conn.execute("SELECT 1 AS x").fetchone()
        assert result[0] == 1
    finally:
        db._conn = old_conn


def test_query_returns_dataframe():
    """query() should return a pandas DataFrame."""
    from data.database import get_connection

    conn = get_connection()
    conn.execute("CREATE TABLE IF NOT EXISTS _test_q (id INT, name VARCHAR)")
    conn.execute("DELETE FROM _test_q")
    conn.execute("INSERT INTO _test_q VALUES (1, 'alice'), (2, 'bob')")

    from data.database import query
    df = query("SELECT * FROM _test_q ORDER BY id")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df.columns) == ["id", "name"]

    conn.execute("DROP TABLE _test_q")


def test_get_table_schemas_contains_ddl():
    """get_table_schemas() should contain CREATE TABLE statements."""
    from data.database import get_table_schemas

    schemas = get_table_schemas()
    assert "CREATE TABLE" in schemas
    assert "billing" in schemas
    assert "production" in schemas


def test_data_dir_exists():
    """DATA_DIR should point to an existing directory."""
    from data.database import DATA_DIR

    assert DATA_DIR.exists(), f"DATA_DIR {DATA_DIR} does not exist"
    assert DATA_DIR.is_dir()


def test_csv_files_exist():
    """All referenced CSV files should exist in the Data directory."""
    from data.database import TABLE_DEFINITIONS, DATA_DIR

    for name, cfg in TABLE_DEFINITIONS.items():
        csv_path = DATA_DIR / cfg["file"]
        assert csv_path.exists(), f"Missing CSV for {name}: {csv_path}"
