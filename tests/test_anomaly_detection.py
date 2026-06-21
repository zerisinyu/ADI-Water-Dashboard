"""
Tests for the statistical anomaly detection module.
"""
import pandas as pd
import numpy as np
import pytest


def test_detect_zscore_finds_outliers():
    """Z-score detection should flag values > threshold std devs from mean."""
    from analytics.anomaly_detection import detect_zscore

    # Normal data with one obvious outlier
    values = [50.0] * 10 + [99.0]
    series = pd.Series(values)

    anomalies = detect_zscore(series, threshold=2.0, metric_name="test_metric")
    assert len(anomalies) >= 1
    assert any(a.value == 99.0 for a in anomalies)


def test_detect_iqr_finds_outliers():
    """IQR detection should flag values outside Q1-1.5*IQR, Q3+1.5*IQR."""
    from analytics.anomaly_detection import detect_iqr

    values = [30, 32, 31, 33, 30, 34, 32, 31, 33, 30, 80, 5]
    series = pd.Series(values, dtype=float)

    anomalies = detect_iqr(series, metric_name="test_metric")
    assert len(anomalies) >= 1  # At least the extreme value (80) should be flagged


def test_anomaly_dataclass_fields():
    """Anomaly dataclass should have all required fields."""
    from analytics.anomaly_detection import Anomaly

    a = Anomaly(
        metric="nrw",
        zone="Zone A",
        country="Cameroon",
        value=55.0,
        expected_range=(20.0, 40.0),
        severity="critical",
        method="zscore",
        explanation="NRW is 55%, significantly above expected range (20-40%)",
    )
    assert a.metric == "nrw"
    assert a.severity == "critical"
    assert a.method == "zscore"


def test_detect_zscore_empty_series():
    """Z-score on empty Series should return empty list."""
    from analytics.anomaly_detection import detect_zscore

    series = pd.Series([], dtype=float)
    anomalies = detect_zscore(series, metric_name="test_metric")
    assert anomalies == []


def test_detect_zscore_uniform_data():
    """Z-score on uniform data (zero std) should return empty list."""
    from analytics.anomaly_detection import detect_zscore

    series = pd.Series([50.0, 50.0, 50.0, 50.0, 50.0])
    anomalies = detect_zscore(series, metric_name="test_metric")
    assert anomalies == []
