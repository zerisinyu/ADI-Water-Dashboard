"""
What-if scenario modeling for water utility decision support.

Enables stakeholders to project the impact of operational changes
(NRW reduction, tariff changes, coverage expansion) on key KPIs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class ScenarioResult:
    """Outcome of a single what-if scenario."""
    name: str
    description: str
    baseline: dict[str, float]
    projected: dict[str, float]
    impact: dict[str, float]  # absolute change
    impact_pct: dict[str, float]  # percentage change


def simulate_nrw_reduction(
    billing_df: pd.DataFrame,
    production_df: pd.DataFrame,
    reduction_pct: float = 10.0,
) -> Optional[ScenarioResult]:
    """
    Model the impact of reducing Non-Revenue Water by a given percentage.

    A lower NRW means more produced water reaches billable customers,
    directly increasing potential revenue and reducing waste.
    """
    if billing_df.empty or production_df.empty:
        return None

    total_production = production_df["production_m3"].sum()
    total_consumption = billing_df["consumption_m3"].sum()
    total_billed = billing_df["billed"].sum()
    total_paid = billing_df["paid"].sum()

    if total_production <= 0:
        return None

    current_nrw_pct = (total_production - total_consumption) / total_production * 100
    current_nrw_m3 = total_production - total_consumption

    # Project new values
    nrw_saved_m3 = current_nrw_m3 * (reduction_pct / 100)
    new_consumption = total_consumption + nrw_saved_m3
    new_nrw_pct = (total_production - new_consumption) / total_production * 100

    # Revenue impact: additional billable water * average tariff
    avg_tariff = total_billed / max(total_consumption, 1)
    additional_revenue = nrw_saved_m3 * avg_tariff
    coll_rate = total_paid / max(total_billed, 1)
    additional_collected = additional_revenue * coll_rate

    return ScenarioResult(
        name=f"Reduce NRW by {reduction_pct:.0f}%",
        description=(
            f"Reducing non-revenue water from {current_nrw_pct:.1f}% to {new_nrw_pct:.1f}% "
            f"recovers {nrw_saved_m3:,.0f} m³ of billable water."
        ),
        baseline={
            "NRW (%)": round(current_nrw_pct, 1),
            "Water Lost (m³)": round(current_nrw_m3, 0),
            "Total Revenue": round(total_paid, 0),
        },
        projected={
            "NRW (%)": round(new_nrw_pct, 1),
            "Water Lost (m³)": round(current_nrw_m3 - nrw_saved_m3, 0),
            "Total Revenue": round(total_paid + additional_collected, 0),
        },
        impact={
            "NRW (%)": round(new_nrw_pct - current_nrw_pct, 1),
            "Water Recovered (m³)": round(nrw_saved_m3, 0),
            "Additional Revenue": round(additional_collected, 0),
        },
        impact_pct={
            "NRW Change": round(-reduction_pct, 1),
            "Revenue Change (%)": round(additional_collected / max(total_paid, 1) * 100, 1),
        },
    )


def simulate_tariff_change(
    billing_df: pd.DataFrame,
    change_pct: float = 5.0,
    elasticity: float = -0.3,
) -> Optional[ScenarioResult]:
    """
    Model the impact of a tariff change on revenue and demand.

    Uses a simple price elasticity of demand model:
    % change in demand = elasticity * % change in price.
    Default elasticity of -0.3 is typical for urban water in Sub-Saharan Africa.
    """
    if billing_df.empty:
        return None

    total_consumption = billing_df["consumption_m3"].sum()
    total_billed = billing_df["billed"].sum()
    total_paid = billing_df["paid"].sum()
    coll_rate = total_paid / max(total_billed, 1)

    # Demand response
    demand_change_pct = elasticity * change_pct
    new_consumption = total_consumption * (1 + demand_change_pct / 100)

    # Revenue impact
    avg_tariff = total_billed / max(total_consumption, 1)
    new_tariff = avg_tariff * (1 + change_pct / 100)
    new_billed = new_consumption * new_tariff
    new_collected = new_billed * coll_rate

    return ScenarioResult(
        name=f"{'Increase' if change_pct > 0 else 'Decrease'} tariff by {abs(change_pct):.0f}%",
        description=(
            f"A {change_pct:+.0f}% tariff change with elasticity {elasticity} "
            f"leads to {demand_change_pct:+.1f}% change in demand."
        ),
        baseline={
            "Avg Tariff": round(avg_tariff, 2),
            "Consumption (m³)": round(total_consumption, 0),
            "Revenue Collected": round(total_paid, 0),
        },
        projected={
            "Avg Tariff": round(new_tariff, 2),
            "Consumption (m³)": round(new_consumption, 0),
            "Revenue Collected": round(new_collected, 0),
        },
        impact={
            "Tariff Change": round(new_tariff - avg_tariff, 2),
            "Demand Change (m³)": round(new_consumption - total_consumption, 0),
            "Revenue Change": round(new_collected - total_paid, 0),
        },
        impact_pct={
            "Demand Change (%)": round(demand_change_pct, 1),
            "Revenue Change (%)": round((new_collected - total_paid) / max(total_paid, 1) * 100, 1),
        },
    )


def simulate_coverage_expansion(
    billing_df: pd.DataFrame,
    production_df: pd.DataFrame,
    new_connections: int = 1000,
    avg_consumption_m3: float = 15.0,
) -> Optional[ScenarioResult]:
    """
    Model the impact of expanding service coverage by adding new connections.

    Projects additional demand, revenue, and production requirements.
    """
    if billing_df.empty:
        return None

    total_consumption = billing_df["consumption_m3"].sum()
    total_billed = billing_df["billed"].sum()
    total_paid = billing_df["paid"].sum()
    total_production = production_df["production_m3"].sum() if not production_df.empty else 0
    n_customers = billing_df["customer_id"].nunique() if "customer_id" in billing_df.columns else len(billing_df)
    months = billing_df["date"].dt.to_period("M").nunique() if "date" in billing_df.columns else 1

    avg_tariff = total_billed / max(total_consumption, 1)
    coll_rate = total_paid / max(total_billed, 1)

    # Additional demand from new connections (per month * total months)
    additional_demand = new_connections * avg_consumption_m3 * months
    additional_revenue = additional_demand * avg_tariff * coll_rate

    # Production capacity check
    capacity_pct = (total_consumption + additional_demand) / max(total_production, 1) * 100

    return ScenarioResult(
        name=f"Add {new_connections:,} new connections",
        description=(
            f"Adding {new_connections:,} new connections at {avg_consumption_m3:.0f} m³/month "
            f"each increases demand by {additional_demand:,.0f} m³ over the period."
        ),
        baseline={
            "Customers": n_customers,
            "Total Consumption (m³)": round(total_consumption, 0),
            "Revenue Collected": round(total_paid, 0),
            "Production Utilisation (%)": round(total_consumption / max(total_production, 1) * 100, 1),
        },
        projected={
            "Customers": n_customers + new_connections,
            "Total Consumption (m³)": round(total_consumption + additional_demand, 0),
            "Revenue Collected": round(total_paid + additional_revenue, 0),
            "Production Utilisation (%)": round(capacity_pct, 1),
        },
        impact={
            "New Customers": new_connections,
            "Additional Demand (m³)": round(additional_demand, 0),
            "Additional Revenue": round(additional_revenue, 0),
        },
        impact_pct={
            "Customer Growth (%)": round(new_connections / max(n_customers, 1) * 100, 1),
            "Revenue Growth (%)": round(additional_revenue / max(total_paid, 1) * 100, 1),
            "Capacity Impact (%)": round(capacity_pct - total_consumption / max(total_production, 1) * 100, 1),
        },
    )
