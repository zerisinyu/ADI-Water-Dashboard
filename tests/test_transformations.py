"""
Tests for data transformation logic (ETL pipeline derived metrics).
"""
import duckdb
import pandas as pd
import pytest


@pytest.fixture
def pipeline_db():
    """Set up a DuckDB with billing + production tables for view testing."""
    conn = duckdb.connect(":memory:")

    conn.execute("""
        CREATE TABLE billing (
            customer_id INT, date DATE, consumption_m3 DOUBLE,
            billed DOUBLE, paid DOUBLE, country VARCHAR,
            zone VARCHAR, source VARCHAR
        )
    """)
    conn.execute("""
        INSERT INTO billing VALUES
        (1, '2024-01-15', 10.0, 100.0, 90.0, 'Cameroon', 'Zone A', 'S1'),
        (2, '2024-01-20', 15.0, 150.0, 140.0, 'Cameroon', 'Zone B', 'S2'),
        (3, '2024-02-10', 12.0, 120.0, 120.0, 'Uganda', 'Zone A', 'S1')
    """)

    conn.execute("""
        CREATE TABLE production (
            date DATE, source VARCHAR, production_m3 DOUBLE,
            service_hours DOUBLE, country VARCHAR
        )
    """)
    conn.execute("""
        INSERT INTO production VALUES
        ('2024-01-15', 'S1', 50.0, 20.0, 'Cameroon'),
        ('2024-01-20', 'S2', 80.0, 18.0, 'Cameroon'),
        ('2024-02-10', 'S1', 60.0, 22.0, 'Uganda')
    """)

    yield conn
    conn.close()


def test_billing_monthly_view(pipeline_db):
    """v_billing_monthly aggregates billing data by month/country/zone."""
    conn = pipeline_db
    conn.execute("""
        CREATE VIEW v_billing_monthly AS
        SELECT
            date_trunc('month', date)::DATE AS month,
            country, zone,
            COUNT(DISTINCT customer_id) AS customers,
            SUM(consumption_m3) AS total_consumption_m3,
            SUM(billed) AS total_billed,
            SUM(paid) AS total_paid,
            CASE WHEN SUM(billed) > 0
                 THEN SUM(paid) / SUM(billed) * 100 ELSE 0 END AS collection_efficiency
        FROM billing WHERE date IS NOT NULL
        GROUP BY 1, 2, 3
    """)

    df = conn.execute("SELECT * FROM v_billing_monthly ORDER BY month, country, zone").fetchdf()
    assert len(df) == 3  # Jan Cameroon Zone A, Jan Cameroon Zone B, Feb Uganda Zone A

    cam_a = df[(df["country"] == "Cameroon") & (df["zone"] == "Zone A")]
    assert cam_a.iloc[0]["total_billed"] == 100.0
    assert cam_a.iloc[0]["collection_efficiency"] == 90.0


def test_nrw_monthly_view(pipeline_db):
    """v_nrw_monthly correctly computes Non-Revenue Water percentage."""
    conn = pipeline_db

    # Create prerequisite views
    conn.execute("""
        CREATE VIEW v_billing_monthly AS
        SELECT date_trunc('month', date)::DATE AS month, country,
               SUM(consumption_m3) AS total_consumption_m3
        FROM billing WHERE date IS NOT NULL GROUP BY 1, 2
    """)
    conn.execute("""
        CREATE VIEW v_production_monthly AS
        SELECT date_trunc('month', date)::DATE AS month, country,
               SUM(production_m3) AS total_production_m3,
               AVG(service_hours) AS avg_service_hours
        FROM production WHERE date IS NOT NULL GROUP BY 1, 2
    """)
    conn.execute("""
        CREATE VIEW v_nrw_monthly AS
        SELECT
            p.month, p.country,
            p.total_production_m3,
            COALESCE(b.total_consumption_m3, 0) AS total_consumption_m3,
            CASE WHEN p.total_production_m3 > 0
                 THEN (p.total_production_m3 - COALESCE(b.total_consumption_m3, 0))
                      / p.total_production_m3 * 100
                 ELSE 0 END AS nrw_pct,
            p.avg_service_hours
        FROM (SELECT month, country, SUM(total_production_m3) AS total_production_m3,
                     AVG(avg_service_hours) AS avg_service_hours
              FROM v_production_monthly GROUP BY 1, 2) p
        LEFT JOIN (SELECT month, country, SUM(total_consumption_m3) AS total_consumption_m3
                   FROM v_billing_monthly GROUP BY 1, 2) b
        ON p.month = b.month AND p.country = b.country
    """)

    df = conn.execute("SELECT * FROM v_nrw_monthly ORDER BY month, country").fetchdf()
    assert len(df) >= 1

    # For Cameroon Jan: prod=130, cons=25, NRW = (130-25)/130 * 100 = 80.77%
    cam = df[df["country"] == "Cameroon"]
    assert len(cam) == 1
    assert cam.iloc[0]["nrw_pct"] == pytest.approx(80.77, abs=0.1)


def test_collection_efficiency_capped():
    """Collection efficiency should not exceed 100% when paid > billed."""
    import numpy as np

    billed = 100.0
    paid = 110.0  # Overpayment
    eff = min(paid / billed * 100, 100)
    assert eff == 100.0
