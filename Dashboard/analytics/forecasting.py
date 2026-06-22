"""
Time-series forecasting engine for the Water Utility Dashboard.

Uses statsmodels Holt-Winters exponential smoothing to produce forecasts
with 80% and 95% confidence intervals for key water-sector KPIs, falling
back to a simple linear trend when there isn't enough data to fit a model.

(Previously backed by statsforecast/AutoARIMA, which pulled in numba +
llvmlite — heavy to install on Streamlit Cloud. statsmodels is already a
dependency for the decomposition page, so this removes a large, slow chunk
of the dependency tree with no new requirements.)
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Available metrics and how to query them
METRIC_DEFINITIONS: dict[str, dict] = {
    "nrw_pct": {
        "label": "Non-Revenue Water (%)",
        "query": """
            SELECT month AS ds, nrw_pct AS y
            FROM v_nrw_monthly
            WHERE country = '{country}'
            ORDER BY month
        """,
        "freq": "MS",
        "description": "Percentage of produced water lost before reaching customers",
    },
    "collection_efficiency": {
        "label": "Collection Efficiency (%)",
        "query": """
            SELECT month AS ds, collection_efficiency AS y
            FROM v_billing_monthly
            WHERE country = '{country}'
            {zone_filter}
            GROUP BY month
            ORDER BY month
        """,
        "query_agg": """
            SELECT month AS ds,
                   SUM(total_paid) / NULLIF(SUM(total_billed), 0) * 100 AS y
            FROM v_billing_monthly
            WHERE country = '{country}'
            {zone_filter}
            GROUP BY month
            ORDER BY month
        """,
        "freq": "MS",
        "description": "Ratio of revenue collected vs. billed",
    },
    "production_volume": {
        "label": "Production Volume (m³)",
        "query": """
            SELECT month AS ds, total_production_m3 AS y
            FROM v_production_monthly
            WHERE country = '{country}'
            GROUP BY month
            ORDER BY month
        """,
        "query_agg": """
            SELECT month AS ds, SUM(total_production_m3) AS y
            FROM v_production_monthly
            WHERE country = '{country}'
            GROUP BY month
            ORDER BY month
        """,
        "freq": "MS",
        "description": "Total monthly water production across all sources",
    },
    "service_hours": {
        "label": "Avg Service Hours (hrs/day)",
        "query": """
            SELECT month AS ds, avg_service_hours AS y
            FROM v_production_monthly
            WHERE country = '{country}'
            GROUP BY month
            ORDER BY month
        """,
        "query_agg": """
            SELECT month AS ds, AVG(avg_service_hours) AS y
            FROM v_production_monthly
            WHERE country = '{country}'
            GROUP BY month
            ORDER BY month
        """,
        "freq": "MS",
        "description": "Average daily hours of water service per month",
    },
    "water_quality": {
        "label": "Water Quality Compliance (%)",
        "query": """
            SELECT date AS ds, water_quality_rate AS y
            FROM v_service_quality
            WHERE country = '{country}'
            {zone_filter}
            ORDER BY date
        """,
        "query_agg": """
            SELECT date AS ds, AVG(water_quality_rate) AS y
            FROM v_service_quality
            WHERE country = '{country}'
            {zone_filter}
            GROUP BY date
            ORDER BY date
        """,
        "freq": "MS",
        "description": "Composite pass rate for chlorine and E. coli tests",
    },
    "complaint_resolution": {
        "label": "Complaint Resolution Rate (%)",
        "query": """
            SELECT date AS ds, complaint_resolution_rate AS y
            FROM v_service_quality
            WHERE country = '{country}'
            {zone_filter}
            ORDER BY date
        """,
        "query_agg": """
            SELECT date AS ds, AVG(complaint_resolution_rate) AS y
            FROM v_service_quality
            WHERE country = '{country}'
            {zone_filter}
            GROUP BY date
            ORDER BY date
        """,
        "freq": "MS",
        "description": "Percentage of customer complaints resolved",
    },
}


def _prepare_series(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and prepare a monthly time series for modelling."""
    df = df.dropna(subset=["ds", "y"]).copy()
    df["ds"] = pd.to_datetime(df["ds"])
    df["y"] = pd.to_numeric(df["y"], errors="coerce")
    df = df.dropna(subset=["y"])
    # Aggregate duplicates (same month)
    df = df.groupby("ds").agg({"y": "mean"}).reset_index()
    df = df.sort_values("ds").reset_index(drop=True)
    return df[["ds", "y"]]


def forecast_metric(
    metric_name: str,
    country: str,
    zone: Optional[str] = None,
    horizon: int = 12,
) -> dict:
    """
    Produce a forecast for a given metric.

    Args:
        metric_name: Key from METRIC_DEFINITIONS.
        country: Country to filter data for.
        zone: Optional zone filter.
        horizon: Number of periods to forecast.

    Returns:
        Dict with keys:
          - historical: DataFrame with columns [ds, y]
          - forecast: DataFrame with columns [ds, yhat, yhat_lower_80,
            yhat_upper_80, yhat_lower_95, yhat_upper_95]
          - model_used: str name of the winning model
          - metric_info: dict with label, description
          - error: Optional[str] if something went wrong
    """
    from data.database import query as db_query

    defn = METRIC_DEFINITIONS.get(metric_name)
    if defn is None:
        return {"error": f"Unknown metric: {metric_name}"}

    # Build query. When the caller passes country="All" (master users)
    # we drop the country predicate so the model fits on the pooled
    # cross-country series instead of returning zero rows.
    zone_filter = f"AND zone = '{zone}'" if zone and zone != "All" else ""
    is_all_countries = (not country) or country == "All"
    sql_key = "query_agg" if "query_agg" in defn else "query"
    sql = defn[sql_key].format(country=country, zone_filter=zone_filter)
    if is_all_countries:
        sql = sql.replace(f"WHERE country = '{country}'", "WHERE 1 = 1")

    try:
        raw_df = db_query(sql)
    except Exception as exc:
        logger.exception("Failed to query data for %s", metric_name)
        return {"error": f"Data query failed: {exc}"}

    if raw_df.empty or len(raw_df) < 6:
        return {"error": f"Insufficient data for {defn['label']} (need >= 6 observations, got {len(raw_df)})"}

    series_df = _prepare_series(raw_df)
    if len(series_df) < 6:
        return {"error": f"Insufficient clean data points ({len(series_df)})"}

    try:
        return _forecast_holtwinters(series_df, horizon, defn)
    except Exception as exc:
        logger.exception("Forecasting failed for %s", metric_name)
        # Fallback: simple linear trend
        return _linear_fallback(series_df, horizon, defn, str(exc))


def _forecast_holtwinters(series_df: pd.DataFrame, horizon: int, defn: dict) -> dict:
    """Fit a Holt-Winters exponential-smoothing model and forecast.

    Chooses a seasonal model when there are at least two full seasons of
    monthly data, otherwise a trend-only model. Confidence intervals are
    derived from the in-sample residual spread, widening with the forecast
    horizon to reflect growing uncertainty.
    """
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    freq = defn.get("freq", "MS")
    s = series_df.set_index("ds")["y"].astype(float)
    # Regularise to a continuous monthly index so the model sees even spacing.
    s = s.asfreq(freq)
    s = s.interpolate(limit_direction="both").dropna()

    n = len(s)
    if n < 6:
        raise ValueError(f"Insufficient points after regularisation ({n})")

    if n >= 24:
        model = ExponentialSmoothing(
            s, trend="add", seasonal="add", seasonal_periods=12,
            initialization_method="estimated",
        )
        model_used = "Holt-Winters (seasonal)"
    else:
        model = ExponentialSmoothing(
            s, trend="add", seasonal=None, initialization_method="estimated",
        )
        model_used = "Holt-Winters (trend)"

    fit = model.fit(optimized=True)
    point = fit.forecast(horizon)

    # Residual std from in-sample fit drives the prediction interval width.
    resid = pd.Series(fit.resid).dropna()
    std = float(resid.std()) if len(resid) > 1 else float(s.std() or 0.0)
    if not np.isfinite(std) or std == 0.0:
        std = float(abs(s.iloc[-1]) * 0.05) or 1.0

    steps = np.arange(1, horizon + 1)
    band = std * np.sqrt(steps)  # random-walk-style widening with horizon

    future_dates = pd.date_range(
        start=s.index[-1] + pd.DateOffset(months=1), periods=horizon, freq=freq
    )
    yhat = point.to_numpy()

    result_df = pd.DataFrame({
        "ds": future_dates,
        "yhat": yhat,
        "yhat_lower_80": yhat - 1.28 * band,
        "yhat_upper_80": yhat + 1.28 * band,
        "yhat_lower_95": yhat - 1.96 * band,
        "yhat_upper_95": yhat + 1.96 * band,
    })

    return {
        "historical": series_df[["ds", "y"]].copy(),
        "forecast": result_df,
        "model_used": model_used,
        "metric_info": {"label": defn["label"], "description": defn["description"]},
        "error": None,
    }


def _linear_fallback(
    series_df: pd.DataFrame, horizon: int, defn: dict, original_error: str
) -> dict:
    """Simple linear extrapolation fallback when statsforecast fails."""
    df = series_df.copy()
    df["t"] = np.arange(len(df))
    slope, intercept = np.polyfit(df["t"], df["y"], 1)
    residuals = df["y"] - (slope * df["t"] + intercept)
    std_err = residuals.std()

    last_t = df["t"].iloc[-1]
    last_date = df["ds"].iloc[-1]
    future_dates = pd.date_range(start=last_date + pd.DateOffset(months=1), periods=horizon, freq="MS")
    future_t = np.arange(last_t + 1, last_t + 1 + horizon)
    yhat = slope * future_t + intercept

    result_df = pd.DataFrame({
        "ds": future_dates,
        "yhat": yhat,
        "yhat_lower_80": yhat - 1.28 * std_err,
        "yhat_upper_80": yhat + 1.28 * std_err,
        "yhat_lower_95": yhat - 1.96 * std_err,
        "yhat_upper_95": yhat + 1.96 * std_err,
    })

    return {
        "historical": series_df[["ds", "y"]].copy(),
        "forecast": result_df,
        "model_used": f"Linear Trend (fallback: {original_error})",
        "metric_info": {"label": defn["label"], "description": defn["description"]},
        "error": None,
    }


def get_available_metrics() -> list[dict]:
    """Return metadata for all forecastable metrics."""
    return [
        {"key": k, "label": v["label"], "description": v["description"]}
        for k, v in METRIC_DEFINITIONS.items()
    ]
