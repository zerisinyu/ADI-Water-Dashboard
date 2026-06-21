"""
Tests for the forecasting module.
"""
import pandas as pd
import numpy as np
import pytest


def test_metric_definitions_exist():
    """All expected forecastable metrics should be defined."""
    from analytics.forecasting import METRIC_DEFINITIONS

    expected = {"nrw_pct", "collection_efficiency", "production_volume",
                "service_hours", "water_quality", "complaint_resolution"}
    assert set(METRIC_DEFINITIONS.keys()) == expected


def test_metric_definitions_have_required_keys():
    """Each metric definition should have label, query, and freq."""
    from analytics.forecasting import METRIC_DEFINITIONS

    for name, defn in METRIC_DEFINITIONS.items():
        assert "label" in defn, f"{name} missing 'label'"
        assert "query" in defn, f"{name} missing 'query'"
        assert "freq" in defn, f"{name} missing 'freq'"
        assert "description" in defn, f"{name} missing 'description'"


def test_linear_fallback_produces_forecast():
    """The linear trend fallback should produce a valid forecast result."""
    from analytics.forecasting import _linear_fallback, METRIC_DEFINITIONS

    dates = pd.date_range("2023-01-01", periods=24, freq="MS")
    values = np.linspace(30, 50, 24) + np.random.normal(0, 1, 24)
    hist_df = pd.DataFrame({"ds": dates, "y": values})

    defn = list(METRIC_DEFINITIONS.values())[0]
    result = _linear_fallback(hist_df, horizon=6, defn=defn, original_error="test")

    assert isinstance(result, dict)
    assert result["error"] is None
    forecast = result["forecast"]
    assert isinstance(forecast, pd.DataFrame)
    assert len(forecast) == 6
    assert "ds" in forecast.columns
    assert "yhat" in forecast.columns
    assert "yhat_lower_80" in forecast.columns
    assert "yhat_upper_95" in forecast.columns

    # Forecast dates should be after historical dates
    assert forecast["ds"].min() > hist_df["ds"].max()


def test_linear_fallback_confidence_intervals_ordered():
    """Confidence intervals should be nested: lower_95 < lower_80 < yhat < upper_80 < upper_95."""
    from analytics.forecasting import _linear_fallback, METRIC_DEFINITIONS

    dates = pd.date_range("2023-01-01", periods=24, freq="MS")
    values = np.linspace(30, 50, 24)
    hist_df = pd.DataFrame({"ds": dates, "y": values})

    defn = list(METRIC_DEFINITIONS.values())[0]
    result = _linear_fallback(hist_df, horizon=6, defn=defn, original_error="test")
    forecast = result["forecast"]

    for _, row in forecast.iterrows():
        assert row["yhat_lower_95"] <= row["yhat_lower_80"]
        assert row["yhat_lower_80"] <= row["yhat"]
        assert row["yhat"] <= row["yhat_upper_80"]
        assert row["yhat_upper_80"] <= row["yhat_upper_95"]


def test_get_available_metrics():
    """get_available_metrics should return all defined metrics."""
    from analytics.forecasting import get_available_metrics

    metrics = get_available_metrics()
    assert isinstance(metrics, list)
    assert len(metrics) == 6
    for m in metrics:
        assert "key" in m
        assert "label" in m
