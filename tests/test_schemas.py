"""
Tests for Pandera schema validation.
"""
import pandas as pd
import pytest


def test_schema_registry_has_all_tables():
    """SCHEMA_REGISTRY should cover all 7 data tables."""
    from data.schemas import SCHEMA_REGISTRY

    expected = {"billing", "production", "sw_service", "w_access", "s_access",
                "fin_service", "national_accounts"}
    assert set(SCHEMA_REGISTRY.keys()) == expected


def test_valid_countries_title_case():
    """VALID_COUNTRIES should be title-cased."""
    from data.schemas import VALID_COUNTRIES

    for c in VALID_COUNTRIES:
        assert c == c.title(), f"Country '{c}' is not title-cased"


def test_validate_dataframe_valid_billing(sample_billing_df):
    """Valid billing data should pass validation."""
    from data.schemas import validate_dataframe

    result = validate_dataframe("billing", sample_billing_df)
    assert result["valid"] is True
    assert result["row_count"] == 5


def test_validate_dataframe_negative_billed():
    """Negative billed amounts should fail validation."""
    from data.schemas import validate_dataframe

    df = pd.DataFrame({
        "customer_id": [1],
        "date": pd.to_datetime(["2024-01-15"]),
        "consumption_m3": [10.0],
        "billed": [-50.0],  # Invalid: negative
        "paid": [40.0],
        "country": ["Cameroon"],
        "zone": ["Zone A"],
        "source": ["S1"],
    })
    result = validate_dataframe("billing", df)
    assert result["valid"] is False
    assert len(result["errors"]) > 0


def test_validate_dataframe_unknown_table():
    """Unknown table name should pass (no schema to validate against)."""
    from data.schemas import validate_dataframe

    df = pd.DataFrame({"x": [1]})
    result = validate_dataframe("nonexistent_table", df)
    assert result["valid"] is True
    assert result["row_count"] == 1
