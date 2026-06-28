"""
Canonical metric definitions for the Water Utility Dashboard.

This is the single semantic layer for the dashboard. Every headline KPI is
defined exactly once here — formula, unit, frequency, granularity, and the
underlying variables — so that the Executive, Finance, Production and Service
pages can never disagree on what (for example) "collection efficiency" means.

Two things live here:

1. ``METRIC_REGISTRY`` — metadata for each KPI, aligned to the AUDC Data
   Dictionary and to sector frameworks (IBNET, IWA water balance, JMP/SDG 6).
2. Pure helper functions that compute each KPI from already-filtered
   DataFrames. They are defensive (safe division, empty frames) and unit-aware.

Design rules:
- Percentages are returned on a 0–100 scale.
- Functions never raise on empty/missing data; they return ``None`` (or 0.0
  where a numeric default is unambiguous) so callers can render a data-gap state.
- "Collection efficiency" and "NRW" combine water + sewer / production + billing
  consistently everywhere they are used.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Metric metadata registry (aligned to AUDC dictionary + sector frameworks)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MetricDef:
    key: str
    label: str
    unit: str                 # "%", "m³", "l/c/d", "hrs/day", "ratio", "currency"
    frequency: str            # cadence the data actually supports
    granularity: str          # "zone", "city", "country", "source"
    direction: str            # "higher_is_better" | "lower_is_better"
    formula: str              # human-readable canonical formula
    variables: tuple          # source columns used
    framework: str = ""       # external benchmark reference


METRIC_REGISTRY: dict[str, MetricDef] = {
    "nrw": MetricDef(
        key="nrw", label="Non-revenue water", unit="%",
        frequency="Monthly", granularity="country", direction="lower_is_better",
        formula="(Volume produced − Volume billed/consumed) ÷ Volume produced × 100",
        variables=("production.production_m3", "billing.consumption_m3"),
        framework="IWA water balance; IBNET (target <25%)",
    ),
    "collection_efficiency": MetricDef(
        key="collection_efficiency", label="Collection efficiency", unit="%",
        frequency="Monthly", granularity="city", direction="higher_is_better",
        formula="(Water paid + Sewer revenue) ÷ (Water billed + Sewer billed) × 100",
        variables=("billing.paid", "billing.billed",
                   "fin_service.sewer_revenue", "fin_service.sewer_billed"),
        framework="IBNET (target ≥85%)",
    ),
    "cost_coverage": MetricDef(
        key="cost_coverage", label="O&M cost coverage", unit="%",
        frequency="Monthly", granularity="city", direction="higher_is_better",
        formula="Total revenue ÷ Operating expenditure × 100",
        variables=("billing.paid", "fin_service.sewer_revenue", "fin_service.opex"),
        framework="IBNET operating cost coverage ratio (target >100%)",
    ),
    "per_capita_consumption": MetricDef(
        key="per_capita_consumption", label="Consumption per capita", unit="l/c/d",
        frequency="Monthly", granularity="zone", direction="higher_is_better",
        formula="Total water consumed (litres) ÷ Population served ÷ days in period",
        variables=("billing.consumption_m3", "w_access.popn_total"),
        framework="JMP service level; ~50–100 l/c/d basic-to-adequate",
    ),
    "water_reuse": MetricDef(
        key="water_reuse", label="Water recycled / reused", unit="%",
        frequency="Monthly", granularity="city", direction="higher_is_better",
        formula="Volume of wastewater reused ÷ Total water supplied × 100",
        variables=("sw_service.ww_reused", "sw_service.w_supplied"),
        framework="SDG 6.3 / circular-economy output",
    ),
    "water_stress": MetricDef(
        key="water_stress", label="Level of water stress", unit="ratio",
        frequency="Annual", granularity="country", direction="lower_is_better",
        formula="Freshwater withdrawals ÷ Total renewable resources",
        variables=("national_accounts.water_resources",),
        framework="SDG 6.4.2 (water stress)",
    ),
    "women_decision_making": MetricDef(
        key="women_decision_making", label="Women in decision-making", unit="%",
        frequency="Quarterly", granularity="city", direction="higher_is_better",
        formula="Women in decision-making positions ÷ Total decision workforce × 100",
        variables=("sw_service.f_workforce", "sw_service.workforce"),
        framework="SDG 6.b / 5.5 gender equity",
    ),
    "service_continuity": MetricDef(
        key="service_continuity", label="Service continuity", unit="hrs/day",
        frequency="Daily", granularity="source", direction="higher_is_better",
        formula="Average hours of supply per day",
        variables=("production.service_hours",),
        framework="IBNET hours of service (24×7 gold standard)",
    ),
    "water_quality_compliance": MetricDef(
        key="water_quality_compliance", label="Water quality compliance", unit="%",
        frequency="Monthly", granularity="zone", direction="higher_is_better",
        formula="Mean of chlorine and E.coli samples passed ÷ samples tested × 100",
        variables=("sw_service.test_passed_chlorine", "sw_service.tests_conducted_chlorine",
                   "sw_service.tests_passed_ecoli", "sw_service.test_conducted_ecoli"),
        framework="WHO drinking-water quality",
    ),
}


def metric_tooltip(key: str) -> Optional[str]:
    """Build a one-line helper string (formula · frequency · benchmark) for a
    metric, suitable for an `ⓘ` tooltip on a KPI card. Returns ``None`` when the
    key is unknown so callers can omit the helper gracefully."""
    m = METRIC_REGISTRY.get(key)
    if m is None:
        return None
    parts = [f"Formula: {m.formula}"]
    unit = m.unit if m.unit not in ("", "ratio") else None
    if unit:
        parts.append(f"Unit: {unit}")
    parts.append(f"Raw data: {m.frequency.lower()}")
    if m.framework:
        parts.append(f"Benchmark: {m.framework}")
    return "  •  ".join(parts)


# ---------------------------------------------------------------------------
# Small numeric helpers
# ---------------------------------------------------------------------------

def _safe_ratio(numerator: float, denominator: float, scale: float = 100.0) -> Optional[float]:
    """numerator/denominator*scale, or None when the denominator is non-positive."""
    try:
        if denominator is None or denominator <= 0 or pd.isna(denominator):
            return None
        if numerator is None or pd.isna(numerator):
            return None
        return float(numerator) / float(denominator) * scale
    except (TypeError, ValueError):
        return None


def _col_sum(df: Optional[pd.DataFrame], col: str) -> float:
    if df is None or df.empty or col not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[col], errors="coerce").sum())


# ---------------------------------------------------------------------------
# Canonical KPI functions — these are the ONLY definitions pages should call.
# ---------------------------------------------------------------------------

def non_revenue_water(production_df: pd.DataFrame, billing_df: pd.DataFrame) -> Optional[float]:
    """NRW % = (produced − consumed) / produced × 100, using real billing volume."""
    produced = _col_sum(production_df, "production_m3")
    consumed = _col_sum(billing_df, "consumption_m3")
    return _safe_ratio(produced - consumed, produced)


def collection_efficiency(billing_df: pd.DataFrame, fin_df: pd.DataFrame) -> Optional[float]:
    """Combined water + sewer cash collection efficiency, %."""
    paid = _col_sum(billing_df, "paid") + _col_sum(fin_df, "sewer_revenue")
    billed = _col_sum(billing_df, "billed") + _col_sum(fin_df, "sewer_billed")
    return _safe_ratio(paid, billed)


def cost_coverage(billing_df: pd.DataFrame, fin_df: pd.DataFrame) -> Optional[float]:
    """O&M cost coverage % = total revenue / opex × 100 (>100% = cost-recovering)."""
    revenue = _col_sum(billing_df, "paid") + _col_sum(fin_df, "sewer_revenue")
    opex = _col_sum(fin_df, "opex")
    return _safe_ratio(revenue, opex)


def per_capita_consumption(
    consumption_m3: float, population: float, days: int = 30
) -> Optional[float]:
    """Litres/capita/day. consumption_m3 and population are totals for the period."""
    if population is None or population <= 0 or days <= 0:
        return None
    litres = float(consumption_m3) * 1000.0
    return litres / float(population) / float(days)


def water_reuse_pct(service_df: pd.DataFrame) -> Optional[float]:
    """% of supplied water that is reused after treatment."""
    reused = _col_sum(service_df, "ww_reused")
    supplied = _col_sum(service_df, "w_supplied")
    return _safe_ratio(reused, supplied)


def wastewater_treatment_pct(service_df: pd.DataFrame) -> Optional[float]:
    """% of collected wastewater that is treated."""
    treated = _col_sum(service_df, "ww_treated")
    collected = _col_sum(service_df, "ww_collected")
    return _safe_ratio(treated, collected)


def women_in_decision_making(service_df: pd.DataFrame) -> Optional[float]:
    """% women in the (sanitation) decision-making workforce."""
    women = _col_sum(service_df, "f_workforce")
    total = _col_sum(service_df, "workforce")
    return _safe_ratio(women, total)


def water_stress_ratio(withdrawals: float, renewable_resources: float) -> Optional[float]:
    """SDG 6.4.2 water stress = withdrawals / renewable resources (unitless ratio)."""
    return _safe_ratio(withdrawals, renewable_resources, scale=1.0)


def water_quality_compliance(service_df: pd.DataFrame) -> Optional[float]:
    """Mean compliance across chlorine and E.coli sampling, %."""
    if service_df is None or service_df.empty:
        return None
    chl_pass = _col_sum(service_df, "test_passed_chlorine")
    chl_done = _col_sum(service_df, "tests_conducted_chlorine")
    eco_pass = _col_sum(service_df, "tests_passed_ecoli")
    eco_done = _col_sum(service_df, "test_conducted_ecoli")
    chl = _safe_ratio(chl_pass, chl_done)
    eco = _safe_ratio(eco_pass, eco_done)
    vals = [v for v in (chl, eco) if v is not None]
    return sum(vals) / len(vals) if vals else None


def population_weighted_mean(
    df: pd.DataFrame, value_col: str, weight_col: str = "popn_total"
) -> Optional[float]:
    """
    Population-weighted mean of ``value_col`` — the correct way to roll up
    coverage/access percentages across zones of different sizes.
    """
    if df is None or df.empty or value_col not in df.columns or weight_col not in df.columns:
        return None
    v = pd.to_numeric(df[value_col], errors="coerce")
    w = pd.to_numeric(df[weight_col], errors="coerce")
    mask = v.notna() & w.notna() & (w > 0)
    if not mask.any():
        return None
    total_w = w[mask].sum()
    if total_w <= 0:
        return None
    return float((v[mask] * w[mask]).sum() / total_w)
