"""
Governance & Compliance page — regulatory KPIs, service provider tracking,
asset health, workforce training, and compliance scorecards.

Data source: national_accounts table (annual, city-level).
"""
from __future__ import annotations

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from utils import (
    KPI,
    render_kpi_row,
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
    DATA_WATER,
    DATA_SANITATION,
    STATUS_GOOD,
    STATUS_WARNING,
    STATUS_NEUTRAL,
)
from data.database import query


def scene_governance():
    _ensure_pipeline()

    # Load data from DuckDB
    nat_df = filter_df_by_user_access(query("SELECT * FROM national_accounts"), "country")

    if nat_df.empty:
        render_empty_state("📋", "No Governance Data", "National accounts data is not available.")
        return

    # Filters
    filters = render_standardized_filters(
        nat_df, page="quality", key_prefix="gov",
        year_col="year", show_period=False, show_zone=False, show_month=False,
    )
    f_df = apply_standard_filters(nat_df, filters, year_col="year")

    selected_country = filters.get("country", "All")
    selected_year = filters.get("year", nat_df["year"].max())

    render_page_hero(
        title="Governance & Compliance",
        icon="gavel",
        filters={"Country": selected_country, "Year": str(selected_year)},
    )

    if f_df.empty:
        st.info("No data for the selected filters.")
        return

    # ----------------------------------------------------------------
    # KPI Scorecards
    # ----------------------------------------------------------------
    render_section_header("Regulatory Compliance Overview")

    latest = f_df.sort_values("year").iloc[-1] if len(f_df) > 0 else f_df.iloc[0]

    registered_wtps = int(latest.get("registered_wtps", 0))
    inspected_wtps = int(latest.get("inspected_wtps", 0))
    inspection_rate = (inspected_wtps / registered_wtps * 100) if registered_wtps > 0 else 0
    total_providers = int(latest.get("total_service_providers", 0))
    licensed_providers = int(latest.get("licensed_service_providers", 0))
    license_rate = (licensed_providers / total_providers * 100) if total_providers > 0 else 0
    asset_health = float(latest.get("asset_health", 0))
    complaint_res = float(latest.get("complaint_resolution", 0))
    trained_staff = int(latest.get("trained_staff", 0))

    render_kpi_row([
        KPI("WTP inspection rate", f"{inspection_rate:.0f}%",
            delta=f"{inspected_wtps}/{registered_wtps} inspected", delta_kind="neutral",
            icon="verified"),
        KPI("Provider licensing", f"{license_rate:.0f}%",
            delta=f"{licensed_providers}/{total_providers} licensed", delta_kind="neutral",
            icon="badge"),
        KPI("Asset health index", f"{asset_health:.1f}",
            delta="Scale 0–100", delta_kind="neutral", icon="construction"),
        KPI("Complaint resolution", f"{complaint_res:.0f} hrs",
            delta="Avg time to resolve", delta_kind="neutral", icon="schedule"),
    ])

    st.markdown("---")

    # ----------------------------------------------------------------
    # Trends
    # ----------------------------------------------------------------
    tab_providers, tab_assets, tab_training = st.tabs([
        "Service Providers", "Asset Health", "Workforce Training"
    ])

    # Filter by country for trends
    trend_df = nat_df.copy()
    if selected_country and selected_country != "All":
        trend_df = trend_df[trend_df["country"].str.lower() == selected_country.lower()]

    with tab_providers:
        render_section_header("Service Provider Compliance Timeline")

        if not trend_df.empty:
            prov_df = trend_df.groupby("year").agg({
                "total_service_providers": "sum",
                "licensed_service_providers": "sum",
            }).reset_index()

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=prov_df["year"], y=prov_df["total_service_providers"],
                name="Total Providers", marker_color=STATUS_NEUTRAL,
            ))
            fig.add_trace(go.Bar(
                x=prov_df["year"], y=prov_df["licensed_service_providers"],
                name="Licensed Providers", marker_color=STATUS_GOOD,
            ))
            fig.update_layout(barmode="group", xaxis_title="Year", yaxis_title="Count")
            style_bar(fig, title="Total vs Licensed Service Providers", height=340, legend_top=True)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            # WTP Inspections
            wtp_df = trend_df.groupby("year").agg({
                "registered_wtps": "sum", "inspected_wtps": "sum",
            }).reset_index()
            wtp_df["inspection_pct"] = (wtp_df["inspected_wtps"] / wtp_df["registered_wtps"].replace(0, 1) * 100)

            fig2 = go.Figure()
            fig2.add_trace(go.Bar(x=wtp_df["year"], y=wtp_df["registered_wtps"], name="Registered", marker_color=DATA_WATER))
            fig2.add_trace(go.Bar(x=wtp_df["year"], y=wtp_df["inspected_wtps"], name="Inspected", marker_color=STATUS_GOOD))
            fig2.add_trace(go.Scatter(
                x=wtp_df["year"], y=wtp_df["inspection_pct"],
                name="Inspection Rate %", yaxis="y2",
                line=dict(color=STATUS_WARNING, width=2.5, dash="dot"),
            ))
            fig2.update_layout(
                barmode="group",
                yaxis=dict(title="Count"),
                yaxis2=dict(title="%", overlaying="y", side="right", range=[0, 110], showgrid=False),
            )
            style_bar(fig2, title="Water Treatment Plant Inspections", height=340, legend_top=True)
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    with tab_assets:
        render_section_header("Asset Health Trend")

        if not trend_df.empty:
            asset_df = trend_df.groupby("year").agg({"asset_health": "mean"}).reset_index()

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=asset_df["year"], y=asset_df["asset_health"],
                mode="lines+markers", name="Asset Health Index",
                line=dict(color=DATA_WATER, width=2.5),
                fill="tozeroy", fillcolor="rgba(0,113,227,0.10)",
            ))
            fig.add_hline(y=70, line_dash="dash", line_color=STATUS_GOOD, annotation_text="Good threshold (70)")
            fig.update_layout(yaxis=dict(title="Index (0-100)", range=[0, 100]))
            style_fig(fig, title="Asset Health Index Over Time", height=320)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            # Complaint resolution trend
            cr_df = trend_df.groupby("year").agg({"complaint_resolution": "mean"}).reset_index()
            fig2 = px.line(cr_df, x="year", y="complaint_resolution", markers=True)
            fig2.update_traces(line=dict(color=DATA_SANITATION, width=2.5))
            fig2.update_layout(yaxis_title="Hours")
            style_fig(fig2, title="Average Complaint Resolution Time (hours)", height=300)
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    with tab_training:
        render_section_header("Workforce Training Investment")

        if not trend_df.empty:
            train_df = trend_df.groupby("year").agg({
                "trained_staff": "sum",
                "staff_training_budget": "sum",
                "staff_cost": "sum",
            }).reset_index()
            train_df["training_pct_of_staff_cost"] = (
                train_df["staff_training_budget"] / train_df["staff_cost"].replace(0, 1) * 100
            )

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=train_df["year"], y=train_df["trained_staff"],
                name="Trained Staff", marker_color=DATA_WATER,
            ))
            fig.add_trace(go.Scatter(
                x=train_df["year"], y=train_df["training_pct_of_staff_cost"],
                name="Training Budget (% of Staff Cost)", yaxis="y2",
                line=dict(color=STATUS_WARNING, width=2.5),
            ))
            fig.update_layout(
                yaxis=dict(title="Staff Trained"),
                yaxis2=dict(title="Training Budget %", overlaying="y", side="right", showgrid=False),
            )
            style_bar(fig, title="Staff Training Volume & Investment", height=340, legend_top=True)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
