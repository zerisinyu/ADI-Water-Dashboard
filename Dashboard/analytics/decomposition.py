"""
Seasonal decomposition for time-series data.

Breaks a metric into trend, seasonal, and residual components using
classical additive decomposition from statsmodels.
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def decompose_metric(
    metric_name: str,
    country: str,
    zone: Optional[str] = None,
    period: Optional[int] = None,
) -> dict:
    """
    Decompose a time series into trend, seasonal, and residual components.

    Args:
        metric_name: Key from forecasting.METRIC_DEFINITIONS.
        country: Country to filter.
        zone: Optional zone filter.
        period: Seasonal period (auto-detected if None).

    Returns:
        Dict with keys: trend, seasonal, residual, observed (all pd.Series
        indexed by date), or error string.
    """
    from analytics.forecasting import METRIC_DEFINITIONS
    from data.database import query as db_query

    defn = METRIC_DEFINITIONS.get(metric_name)
    if defn is None:
        return {"error": f"Unknown metric: {metric_name}"}

    zone_filter = f"AND zone = '{zone}'" if zone and zone != "All" else ""
    is_all_countries = (not country) or country == "All"
    sql_key = "query_agg" if "query_agg" in defn else "query"
    sql = defn[sql_key].format(country=country, zone_filter=zone_filter)
    if is_all_countries:
        sql = sql.replace(f"WHERE country = '{country}'", "WHERE 1 = 1")

    try:
        raw_df = db_query(sql)
    except Exception as exc:
        return {"error": f"Data query failed: {exc}"}

    if raw_df.empty:
        return {"error": "No data available"}

    df = raw_df.dropna(subset=["ds", "y"]).copy()
    df["ds"] = pd.to_datetime(df["ds"])
    df["y"] = pd.to_numeric(df["y"], errors="coerce")
    df = df.dropna(subset=["y"]).sort_values("ds")
    df = df.groupby("ds").agg({"y": "mean"}).reset_index()
    df = df.set_index("ds")

    # Need at least 2 full cycles for decomposition
    if period is None:
        period = min(12, len(df) // 2)
    if period < 2:
        period = 2
    if len(df) < period * 2:
        return {"error": f"Need at least {period * 2} data points (have {len(df)})"}

    try:
        from statsmodels.tsa.seasonal import seasonal_decompose

        result = seasonal_decompose(df["y"], model="additive", period=period)
        return {
            "observed": result.observed,
            "trend": result.trend,
            "seasonal": result.seasonal,
            "residual": result.resid,
            "period": period,
            "error": None,
        }
    except Exception as exc:
        logger.exception("Decomposition failed for %s", metric_name)
        return {"error": f"Decomposition failed: {exc}"}
