"""
Sector Environment page — national budget allocation, cross-country
budget comparison, water resource stress, and budget efficiency.

Data source: national_accounts table (annual, city-level).
"""
from __future__ import annotations

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from utils import (
    render_page_hero,
    render_section_header,
    render_standardized_filters,
    apply_standard_filters,
    filter_df_by_user_access,
    render_empty_state,
    _ensure_pipeline,
)
from charts import (
    style_fig,
    style_bar,
    colorway,
    DATA_WATER,
    DATA_SANITATION,
    STATUS_NEUTRAL,
    GRID,
)
from data.database import query


def scene_sector():
    _ensure_pipeline()

    nat_df = filter_df_by_user_access(query("SELECT * FROM national_accounts"), "country")

    if nat_df.empty:
        render_empty_state("🏛️", "No Sector Data", "National accounts data is not available.")
        return

    # Filters
    filters = render_standardized_filters(
        nat_df, page="finance", key_prefix="sec",
        year_col="year", show_period=False, show_zone=False, show_month=False,
    )
    f_df = apply_standard_filters(nat_df, filters, year_col="year")

    selected_country = filters.get("country", "All")
    selected_year = filters.get("year", nat_df["year"].max())

    render_page_hero(
        title="Sector Environment",
        icon="account_balance",
        filters={"Country": selected_country, "Year": str(selected_year)},
    )

    if f_df.empty:
        st.info("No data for the selected filters.")
        return

    # ----------------------------------------------------------------
    # KPI Scorecards
    # ----------------------------------------------------------------
    render_section_header("National Budget Overview")

    latest = f_df.sort_values("year").iloc[-1]
    budget = float(latest.get("budget_allocated", 0))
    san_alloc = float(latest.get("san_allocation", 0))
    wat_alloc = float(latest.get("wat_allocation", 0))
    water_res = float(latest.get("water_resources", 0))
    wash_total = san_alloc + wat_alloc
    wash_pct = (wash_total / budget * 100) if budget > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total WASH Budget", f"{budget/1e9:.1f}B")
    c2.metric("Water Allocation", f"{wat_alloc/1e9:.1f}B")
    c3.metric("Sanitation Allocation", f"{san_alloc/1e9:.1f}B")
    c4.metric("WASH as % of Budget", f"{wash_pct:.1f}%")

    st.markdown("---")

    tab_budget, tab_compare, tab_resources = st.tabs([
        "Budget Allocation", "Cross-Country Comparison", "Water Resources"
    ])

    # ----------------------------------------------------------------
    # Tab 1: Budget Allocation Trends
    # ----------------------------------------------------------------
    with tab_budget:
        render_section_header("National Budget Allocation Trend")

        trend_df = nat_df.copy()
        if selected_country and selected_country != "All":
            trend_df = trend_df[trend_df["country"].str.lower() == selected_country.lower()]

        if not trend_df.empty:
            budget_df = trend_df.groupby("year").agg({
                "budget_allocated": "sum",
                "san_allocation": "sum",
                "wat_allocation": "sum",
            }).reset_index()
            budget_df["other"] = budget_df["budget_allocated"] - budget_df["san_allocation"] - budget_df["wat_allocation"]
            budget_df["other"] = budget_df["other"].clip(lower=0)

            fig = go.Figure()
            fig.add_trace(go.Bar(x=budget_df["year"], y=budget_df["wat_allocation"] / 1e9, name="Water", marker_color=DATA_WATER))
            fig.add_trace(go.Bar(x=budget_df["year"], y=budget_df["san_allocation"] / 1e9, name="Sanitation", marker_color=DATA_SANITATION))
            fig.add_trace(go.Bar(x=budget_df["year"], y=budget_df["other"] / 1e9, name="Other", marker_color="#d9dadd"))
            fig.update_layout(barmode="stack", yaxis_title="Budget (Billions)")
            style_bar(fig, title="National Budget Allocation (Billions)", height=360, legend_top=True)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            # WASH percentage trend
            budget_df["wash_pct"] = (
                (budget_df["wat_allocation"] + budget_df["san_allocation"])
                / budget_df["budget_allocated"].replace(0, 1) * 100
            )
            fig2 = px.line(budget_df, x="year", y="wash_pct", markers=True)
            fig2.update_traces(line=dict(color=DATA_WATER, width=2.5))
            fig2.update_layout(yaxis=dict(title="%", range=[0, max(20, budget_df["wash_pct"].max() + 5)]))
            style_fig(fig2, title="WASH Spending as % of Total Budget", height=300)
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    # ----------------------------------------------------------------
    # Tab 2: Cross-Country Comparison
    # ----------------------------------------------------------------
    with tab_compare:
        render_section_header("Cross-Country Budget Comparison")

        year_val = int(selected_year) if selected_year else nat_df["year"].max()
        compare_df = nat_df[nat_df["year"] == year_val].copy()

        if not compare_df.empty:
            compare_df["wash_total"] = compare_df["wat_allocation"] + compare_df["san_allocation"]
            compare_df["wash_pct"] = (compare_df["wash_total"] / compare_df["budget_allocated"].replace(0, 1) * 100)

            # Two related cross-country charts side-by-side — halves each chart's
            # width so the 4-country bars read tight instead of ballooning.
            cc1, cc2 = st.columns(2)
            with cc1:
                fig = px.bar(
                    compare_df, x="country", y=["wat_allocation", "san_allocation"],
                    barmode="group",
                    labels={"value": "Amount", "variable": "Sector"},
                    color_discrete_map={"wat_allocation": DATA_WATER, "san_allocation": DATA_SANITATION},
                )
                fig.update_layout(yaxis_title="Allocation Amount")
                style_bar(fig, title=f"Water vs Sanitation by Country ({year_val})", height=360, legend_top=True)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            with cc2:
                # Single metric → single color (not a rainbow per country).
                fig2 = px.bar(compare_df, x="country", y="wash_pct")
                fig2.update_traces(marker_color=DATA_WATER)
                fig2.update_layout(yaxis_title="WASH %", showlegend=False)
                style_bar(fig2, title=f"WASH % of National Budget ({year_val})", height=360)
                st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    # ----------------------------------------------------------------
    # Tab 3: Water Resources
    # ----------------------------------------------------------------
    with tab_resources:
        render_section_header("Water Resources Availability")

        trend_df = nat_df.copy()
        if selected_country and selected_country != "All":
            trend_df = trend_df[trend_df["country"].str.lower() == selected_country.lower()]

        if not trend_df.empty and "water_resources" in trend_df.columns:
            res_df = trend_df.groupby(["year", "country"]).agg({"water_resources": "sum"}).reset_index()

            fig = px.line(
                res_df, x="year", y="water_resources", color="country",
                markers=True, color_discrete_sequence=colorway(),
            )
            fig.update_traces(line=dict(width=2.5))
            fig.update_layout(yaxis_title="Water Resources (m³)")
            style_fig(fig, title="Water Resources Availability Over Time", height=340, legend_top=True)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            # Staff cost vs training budget
            staff_df = trend_df.groupby(["year", "country"]).agg({
                "staff_cost": "sum", "staff_training_budget": "sum",
            }).reset_index()
            staff_df["training_ratio"] = (
                staff_df["staff_training_budget"] / staff_df["staff_cost"].replace(0, 1) * 100
            )

            fig2 = px.bar(
                staff_df, x="year", y="training_ratio", color="country",
                barmode="group", color_discrete_sequence=colorway(),
            )
            fig2.update_layout(yaxis_title="Training %")
            style_bar(fig2, title="Training Investment (% of Staff Cost)", height=340, legend_top=True)
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
