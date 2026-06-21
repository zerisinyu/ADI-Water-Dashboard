"""
Statistical anomaly detection for water utility metrics.

Provides three detection methods:
  - Z-score: for normally distributed metrics (collection efficiency)
  - IQR: for skewed metrics (NRW, service hours)
  - Isolation Forest: for multivariate anomaly detection across zones
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Anomaly:
    """A detected anomaly with context."""
    metric: str
    zone: str
    country: str
    value: float
    expected_range: tuple[float, float]
    severity: Literal["critical", "warning", "info"]
    method: str
    explanation: str
    date: Optional[str] = None


def detect_zscore(
    series: pd.Series,
    threshold: float = 2.5,
    metric_name: str = "metric",
    zone: str = "unknown",
    country: str = "unknown",
) -> list[Anomaly]:
    """
    Detect anomalies using Z-score method.
    Best for normally distributed metrics (e.g., collection efficiency).
    """
    clean = series.dropna()
    if len(clean) < 5:
        return []

    mean = clean.mean()
    std = clean.std()
    if std == 0:
        return []

    anomalies = []
    z_scores = (clean - mean) / std

    for idx, z in z_scores.items():
        if abs(z) >= threshold:
            value = clean[idx]
            severity = "critical" if abs(z) >= 3.5 else "warning"
            direction = "above" if z > 0 else "below"
            anomalies.append(Anomaly(
                metric=metric_name,
                zone=zone,
                country=country,
                value=float(value),
                expected_range=(float(mean - 2 * std), float(mean + 2 * std)),
                severity=severity,
                method="z-score",
                explanation=(
                    f"{metric_name} is {abs(z):.1f} std devs {direction} the mean "
                    f"({value:.1f} vs expected {mean:.1f} +/- {2*std:.1f})"
                ),
                date=str(idx) if not isinstance(idx, int) else None,
            ))

    return anomalies


def detect_iqr(
    series: pd.Series,
    factor: float = 1.5,
    metric_name: str = "metric",
    zone: str = "unknown",
    country: str = "unknown",
) -> list[Anomaly]:
    """
    Detect anomalies using IQR method.
    Best for skewed metrics (e.g., NRW, service hours, complaints).
    """
    clean = series.dropna()
    if len(clean) < 5:
        return []

    q1 = clean.quantile(0.25)
    q3 = clean.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return []

    lower_bound = q1 - factor * iqr
    upper_bound = q3 + factor * iqr

    anomalies = []
    for idx, value in clean.items():
        if value < lower_bound or value > upper_bound:
            distance = max(abs(value - lower_bound), abs(value - upper_bound)) / iqr
            severity = "critical" if distance > 3 else "warning" if distance > 2 else "info"
            direction = "above" if value > upper_bound else "below"
            anomalies.append(Anomaly(
                metric=metric_name,
                zone=zone,
                country=country,
                value=float(value),
                expected_range=(float(lower_bound), float(upper_bound)),
                severity=severity,
                method="iqr",
                explanation=(
                    f"{metric_name} is {direction} the expected range "
                    f"({value:.1f} vs [{lower_bound:.1f}, {upper_bound:.1f}])"
                ),
                date=str(idx) if not isinstance(idx, int) else None,
            ))

    return anomalies


def detect_isolation_forest(
    df: pd.DataFrame,
    metric_cols: list[str],
    zone_col: str = "zone",
    country_col: str = "country",
    contamination: float = 0.1,
) -> list[Anomaly]:
    """
    Detect multivariate anomalies using Isolation Forest.
    Identifies zones that are anomalous across multiple metrics simultaneously.
    """
    if df.empty or len(df) < 10:
        return []

    available_cols = [c for c in metric_cols if c in df.columns]
    if len(available_cols) < 2:
        return []

    try:
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler

        work_df = df.dropna(subset=available_cols).copy()
        if len(work_df) < 10:
            return []

        X = work_df[available_cols].values
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        clf = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
        predictions = clf.fit_predict(X_scaled)
        scores = clf.decision_function(X_scaled)

        anomalies = []
        for i, (pred, score) in enumerate(zip(predictions, scores)):
            if pred == -1:  # anomaly
                row = work_df.iloc[i]
                zone = row.get(zone_col, "unknown")
                country = row.get(country_col, "unknown")

                # Find which metrics deviate most
                row_scaled = X_scaled[i]
                deviating = sorted(
                    zip(available_cols, row_scaled),
                    key=lambda x: abs(x[1]),
                    reverse=True,
                )[:3]

                desc_parts = []
                for col, z in deviating:
                    val = row[col]
                    direction = "high" if z > 0 else "low"
                    desc_parts.append(f"{col}={val:.1f} ({direction})")

                severity = "critical" if score < -0.3 else "warning" if score < -0.1 else "info"
                anomalies.append(Anomaly(
                    metric="multivariate",
                    zone=str(zone),
                    country=str(country),
                    value=float(score),
                    expected_range=(-1.0, 1.0),
                    severity=severity,
                    method="isolation_forest",
                    explanation=f"Zone {zone} is anomalous: {', '.join(desc_parts)}",
                ))

        return anomalies
    except ImportError:
        logger.warning("scikit-learn not available for Isolation Forest")
        return []
    except Exception as exc:
        logger.exception("Isolation Forest detection failed")
        return []


def run_full_detection(
    billing_df: pd.DataFrame,
    production_df: pd.DataFrame,
    service_df: pd.DataFrame,
) -> list[Anomaly]:
    """
    Run all anomaly detection methods on the latest data.
    Returns a combined, severity-sorted list of anomalies.
    """
    all_anomalies: list[Anomaly] = []

    # 1. Z-score on collection efficiency (normally distributed)
    if not billing_df.empty and "paid" in billing_df.columns and "billed" in billing_df.columns:
        monthly = billing_df.groupby(billing_df["date"].dt.to_period("M")).agg(
            {"billed": "sum", "paid": "sum"}
        )
        coll_eff = (monthly["paid"] / monthly["billed"].replace(0, np.nan) * 100).dropna()
        country = billing_df["country"].mode().iloc[0] if not billing_df["country"].mode().empty else "Unknown"
        all_anomalies.extend(detect_zscore(coll_eff, metric_name="Collection Efficiency", country=country))

    # 2. IQR on NRW (typically skewed)
    if not production_df.empty and "production_m3" in production_df.columns:
        if not billing_df.empty:
            prod_monthly = production_df.groupby(production_df["date"].dt.to_period("M")).agg(
                {"production_m3": "sum"}
            )
            cons_monthly = billing_df.groupby(billing_df["date"].dt.to_period("M")).agg(
                {"consumption_m3": "sum"}
            )
            merged = prod_monthly.join(cons_monthly, how="inner")
            nrw = ((merged["production_m3"] - merged["consumption_m3"]) / merged["production_m3"].replace(0, np.nan) * 100).dropna()
            country = production_df["country"].mode().iloc[0] if not production_df["country"].mode().empty else "Unknown"
            all_anomalies.extend(detect_iqr(nrw, metric_name="Non-Revenue Water", country=country))

    # 3. IQR on service hours
    if not production_df.empty and "service_hours" in production_df.columns:
        country = production_df["country"].mode().iloc[0] if not production_df["country"].mode().empty else "Unknown"
        all_anomalies.extend(detect_iqr(
            production_df["service_hours"].dropna(),
            metric_name="Service Hours",
            country=country,
        ))

    # 4. Isolation Forest on zone-level service data
    if not service_df.empty:
        metric_cols = [c for c in ["water_quality_rate", "complaint_resolution_rate", "nrw_rate", "sewer_coverage_rate"]
                       if c in service_df.columns]
        if metric_cols and "zone" in service_df.columns:
            latest = service_df.sort_values("date").groupby("zone").last().reset_index()
            all_anomalies.extend(detect_isolation_forest(latest, metric_cols))

    # Sort by severity
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    all_anomalies.sort(key=lambda a: severity_order.get(a.severity, 3))

    return all_anomalies
