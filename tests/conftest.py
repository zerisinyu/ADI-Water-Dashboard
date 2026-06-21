"""
Shared fixtures for the ADI Water Dashboard test suite.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

# Ensure Dashboard package is importable
DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "Dashboard"
sys.path.insert(0, str(DASHBOARD_DIR))


@pytest.fixture
def sample_billing_df():
    """Minimal billing DataFrame for testing."""
    return pd.DataFrame({
        "customer_id": [1, 2, 3, 4, 5],
        "date": pd.to_datetime(["2024-01-15", "2024-01-20", "2024-02-10", "2024-02-15", "2024-03-01"]),
        "consumption_m3": [12.0, 18.5, 9.0, 25.0, 14.0],
        "billed": [100.0, 150.0, 80.0, 200.0, 120.0],
        "paid": [95.0, 140.0, 80.0, 180.0, 100.0],
        "country": ["Cameroon", "Cameroon", "Uganda", "Uganda", "Malawi"],
        "zone": ["Zone A", "Zone B", "Zone A", "Zone B", "Zone A"],
        "source": ["Source1", "Source2", "Source1", "Source2", "Source1"],
    })


@pytest.fixture
def sample_production_df():
    """Minimal production DataFrame for testing."""
    return pd.DataFrame({
        "date": pd.to_datetime(["2024-01-15", "2024-01-16", "2024-02-10", "2024-02-11", "2024-03-01"]),
        "source": ["Source1", "Source2", "Source1", "Source2", "Source1"],
        "production_m3": [100.0, 200.0, 120.0, 180.0, 150.0],
        "service_hours": [20.0, 18.0, 22.0, 16.0, 19.0],
        "country": ["Cameroon", "Cameroon", "Uganda", "Uganda", "Malawi"],
    })


@pytest.fixture
def sample_service_df():
    """Minimal sw_service DataFrame for testing."""
    return pd.DataFrame({
        "country": ["Cameroon", "Uganda"],
        "city": ["Douala", "Kampala"],
        "zone": ["Zone A", "Zone A"],
        "month": [1, 1],
        "year": [2024, 2024],
        "w_supplied": [500.0, 600.0],
        "total_consumption": [400.0, 480.0],
        "metered": [350.0, 420.0],
        "ww_capacity": [200.0, 250.0],
        "tests_conducted_chlorine": [50, 60],
        "test_conducted_ecoli": [50, 60],
        "test_passed_chlorine": [48, 57],
        "tests_passed_ecoli": [47, 55],
        "complaints": [20, 30],
        "resolved": [18, 25],
        "complaint_resolution": [4.0, 6.0],
        "sewer_connections": [1000, 1500],
        "public_toilets": [50, 80],
        "workforce": [100, 150],
        "f_workforce": [30, 45],
        "hh_emptied": [200, 300],
        "fs_treated": [100.0, 150.0],
        "fs_reused": [20.0, 30.0],
        "ww_collected": [180.0, 220.0],
        "ww_treated": [160.0, 200.0],
        "ww_reused": [40.0, 50.0],
        "households": [5000, 7000],
    })


@pytest.fixture
def duckdb_connection():
    """Create a fresh in-memory DuckDB connection for testing."""
    import duckdb
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()
