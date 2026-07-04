"""
Forecasting & Scenarios page — showcases time-series forecasting,
seasonal decomposition, and what-if scenario modeling.
"""
from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from utils import (
    render_page_hero,
    render_section_header,
    render_empty_state,
    render_standardized_filters,
    render_kpi_row,
    KPI,
    filter_df_by_user_access,
    validate_selected_country,
    _ensure_pipeline,
)
from data.database import query
from analytics.forecasting import forecast_metric, get_available_metrics
from charts import (
    style_fig,
    DATA_WATER,
    STATUS_GOOD,
    STATUS_CRITICAL,
    TEXT_PRIMARY,
)
from analytics.decomposition import decompose_metric
from analytics.scenarios import (
    simulate_nrw_reduction,
    simulate_tariff_change,
    simulate_coverage_expansion,
)


def _render_forecast_chart(result: dict) -> None:
    """Render a Plotly chart with historical data, forecast, and confidence bands."""
    hist = result["historical"]
    fcast = result["forecast"]
    info = result["metric_info"]

    fig = go.Figure()

    # Historical
    fig.add_trace(go.Scatter(
        x=hist["ds"], y=hist["y"],
        name="Historical", mode="lines+markers",
        line=dict(color=TEXT_PRIMARY, width=2),
        marker=dict(size=4),
    ))

    # Forecast line
    fig.add_trace(go.Scatter(
        x=fcast["ds"], y=fcast["yhat"],
        name="Forecast", mode="lines+markers",
        line=dict(color=DATA_WATER, width=2, dash="dash"),
        marker=dict(size=4),
    ))

    # 95% confidence band
    fig.add_trace(go.Scatter(
        x=pd.concat([fcast["ds"], fcast["ds"][::-1]]),
        y=pd.concat([fcast["yhat_upper_95"], fcast["yhat_lower_95"][::-1]]),
        fill="toself", fillcolor="rgba(0,113,227,0.08)",
        line=dict(color="rgba(0,0,0,0)"),
        name="95% CI", showlegend=True,
    ))

    # 80% confidence band
    fig.add_trace(go.Scatter(
        x=pd.concat([fcast["ds"], fcast["ds"][::-1]]),
        y=pd.concat([fcast["yhat_upper_80"], fcast["yhat_lower_80"][::-1]]),
        fill="toself", fillcolor="rgba(0,113,227,0.16)",
        line=dict(color="rgba(0,0,0,0)"),
        name="80% CI", showlegend=True,
    ))

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title=info["label"],
        legend=dict(orientation="h", y=-0.15),
        hovermode="x unified",
    )
    style_fig(fig, title=f"{info['label']} — Forecast", height=400)

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_decomposition_chart(result: dict, label: str) -> None:
    """Render seasonal decomposition as 4 stacked subplots."""
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        subplot_titles=["Observed", "Trend", "Seasonal", "Residual"],
        vertical_spacing=0.06,
    )

    components = [
        ("observed", TEXT_PRIMARY),
        ("trend", DATA_WATER),
        ("seasonal", STATUS_GOOD),
        ("residual", STATUS_CRITICAL),
    ]

    for i, (key, color) in enumerate(components, 1):
        series = result.get(key)
        if series is not None:
            fig.add_trace(go.Scatter(
                x=series.index, y=series.values,
                mode="lines", line=dict(color=color, width=1.5),
                name=key.title(), showlegend=False,
            ), row=i, col=1)

    fig.update_layout(
        height=500,
        title_text=f"{label} — Seasonal Decomposition (period={result.get('period', '?')})",
    )
    style_fig(fig, height=500)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_scenario_card(result) -> None:
    """Render a what-if scenario result using the design-system card."""
    st.markdown(
        '<div class="card card--quiet" style="margin-bottom: 16px;">'
        f'<div style="font-weight: 600; font-size: var(--text-h3); color: var(--text-primary);">{result.name}</div>'
        f'<div style="color: var(--text-secondary); font-size: var(--text-caption); margin-top: 4px;">{result.description}</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    col_base, col_proj, col_impact = st.columns(3)

    with col_base:
        st.markdown("**Baseline**")
        for k, v in result.baseline.items():
            formatted = f"{v:,.0f}" if isinstance(v, (int, float)) and abs(v) > 100 else f"{v}"
            st.metric(k, formatted, help=f"Current {k.lower()} before the scenario is applied.")

    with col_proj:
        st.markdown("**Projected**")
        for k, v in result.projected.items():
            formatted = f"{v:,.0f}" if isinstance(v, (int, float)) and abs(v) > 100 else f"{v}"
            st.metric(k, formatted, help=f"Projected {k.lower()} after applying the scenario levers.")

    with col_impact:
        st.markdown("**Impact**")
        for k, v in result.impact_pct.items():
            delta_str = f"{v:+.1f}%"
            st.metric(k, delta_str, help=f"Percentage change in {k.lower()} from baseline to projected.")


@st.cache_data
def _load_corr_frame(country: str) -> pd.DataFrame:
    """Monthly metric frame (from the DuckDB views) for the correlation explorer."""
    _ensure_pipeline()
    where, params = "", []
    if country and country != "All":
        where = " WHERE LOWER(country) = ?"
        params = [country.lower()]
    b = query(
        f"SELECT month, "
        f"CASE WHEN SUM(total_billed) > 0 THEN SUM(total_paid) / SUM(total_billed) * 100 ELSE NULL END AS collection_eff, "
        f"SUM(total_consumption_m3) AS consumption "
        f"FROM v_billing_monthly{where} GROUP BY month", params)
    n = query(
        f"SELECT month, SUM(total_production_m3) AS production, "
        f"CASE WHEN SUM(total_production_m3) > 0 THEN "
        f"(SUM(total_production_m3) - SUM(total_consumption_m3)) / SUM(total_production_m3) * 100 ELSE NULL END AS nrw_pct, "
        f"AVG(avg_service_hours) AS service_hours FROM v_nrw_monthly{where} GROUP BY month", params)
    q = query(
        f"SELECT date_trunc('month', date)::DATE AS month, AVG(water_quality_rate) AS water_quality "
        f"FROM v_service_quality{where}{' AND' if where else ' WHERE'} water_quality_rate IS NOT NULL GROUP BY 1", params)
    fdf = query(
        f"SELECT date_trunc('month', date)::DATE AS month, AVG(cost_recovery_pct) AS cost_recovery, "
        f"SUM(opex) AS opex FROM v_financial_monthly{where} GROUP BY 1", params)
    return (
        b.merge(n, on="month", how="outer")
         .merge(q, on="month", how="outer")
         .merge(fdf, on="month", how="outer")
         .sort_values("month")
    )


def scene_forecasting():
    """Main entry point for the Forecasting & Scenarios page."""
    _ensure_pipeline()

    # Interactive Country / Zone selectors so users choose what to predict,
    # rendered inline with the title (Home-style header).
    try:
        _opts = filter_df_by_user_access(
            query("SELECT DISTINCT country, zone FROM billing"), "country"
        )
    except Exception:
        _opts = pd.DataFrame(columns=["country", "zone"])

    _filters = render_standardized_filters(
        df=_opts,
        page="forecasting",
        key_prefix="fc_filter",
        country_col="country",
        zone_col="zone",
        show_period=False,
        show_zone=True,
        show_year=False,
        show_month=False,
        auto_month=False,
        title="Insights & forecasting",
        icon="insights",
    )
    selected_country = _filters["country"]
    selected_zone = _filters["zone"]

    st.markdown("<div class='filter-row-gap'></div>", unsafe_allow_html=True)
    tab_forecast, tab_decomp, tab_scenarios, tab_corr = st.tabs([
        "Time-series forecast",
        "Seasonal decomposition",
        "What-if scenarios",
        "Metric correlations",
    ])

    # ----------------------------------------------------------------
    # Tab 1: Forecasting
    # ----------------------------------------------------------------
    with tab_forecast:
        render_section_header(
            "Select metric & horizon",
            eyebrow="Forecast configuration",
            icon="tune",
        )

        metrics = get_available_metrics()
        metric_labels = {m["key"]: m["label"] for m in metrics}

        c1, c2 = st.columns([3, 1])
        with c1:
            selected_metric = st.selectbox(
                "Metric to Forecast",
                options=list(metric_labels.keys()),
                format_func=lambda k: metric_labels[k],
                key="fc_metric",
            )
        with c2:
            horizon = st.slider("Forecast Horizon (months)", 3, 24, 12, key="fc_horizon")

        if st.button("Run Forecast", type="primary", key="fc_run"):
            with st.spinner("Fitting a Holt-Winters exponential-smoothing model..."):
                result = forecast_metric(
                    selected_metric,
                    country=selected_country,
                    zone=selected_zone if selected_zone != "All" else None,
                    horizon=horizon,
                )

            if result.get("error"):
                st.warning(result["error"])
            else:
                _render_forecast_chart(result)

                # Forecast summary cards — icons + ⓘ tooltips on each metric.
                try:
                    _hist, _fc = result["historical"], result["forecast"]
                    _label = result["metric_info"].get("label", selected_metric)
                    _latest = float(_hist["y"].iloc[-1])
                    _end = float(_fc["yhat"].iloc[-1])
                    _chg = ((_end - _latest) / _latest * 100) if _latest else 0.0
                    _lo = float(_fc["yhat_lower_95"].iloc[-1])
                    _hi = float(_fc["yhat_upper_95"].iloc[-1])
                    render_kpi_row([
                        KPI(label="Latest actual", value=f"{_latest:,.1f}", icon="history",
                            help=f"Most recent observed value of {_label.lower()}."),
                        KPI(label=f"Forecast · +{horizon}m", value=f"{_end:,.1f}",
                            delta=f"{_chg:+.1f}% vs latest",
                            delta_kind=("positive" if _chg >= 0 else "negative"),
                            icon="trending_up",
                            help=f"Model projection for {_label.lower()} at the end of the {horizon}-month horizon."),
                        KPI(label="95% interval", value=f"{_lo:,.0f} – {_hi:,.0f}", icon="expand",
                            help="Range the actual value is expected to fall within, at 95% confidence, at horizon end."),
                        KPI(label="Model", value=str(result["model_used"]), icon="model_training",
                            help="Holt-Winters exponential smoothing (seasonal with 24+ months of history, "
                                 "trend-only otherwise), falling back to a linear trend when there isn't "
                                 "enough clean data to fit either."),
                    ])
                except Exception:
                    pass

                st.markdown(
                    '<div class="card card--quiet" style="margin-top: 8px;">'
                    f'<strong>Model:</strong> {result["model_used"]} '
                    f'&nbsp;·&nbsp; <strong>Historical points:</strong> {len(result["historical"])} '
                    f'&nbsp;·&nbsp; <strong>Forecast periods:</strong> {len(result["forecast"])}'
                    '</div>',
                    unsafe_allow_html=True,
                )

                # Export forecast data
                with st.expander("View Forecast Data"):
                    st.dataframe(result["forecast"], use_container_width=True)
                    csv = result["forecast"].to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "Download Forecast CSV", data=csv,
                        file_name=f"forecast_{selected_metric}_{selected_country}.csv",
                        mime="text/csv",
                    )

    # ----------------------------------------------------------------
    # Tab 2: Decomposition
    # ----------------------------------------------------------------
    with tab_decomp:
        render_section_header(
            "Seasonal decomposition",
            eyebrow="Trend · seasonal · residual",
            icon="show_chart",
        )
        st.markdown(
            "Break a time series into **trend**, **seasonal**, and **residual** "
            "components to understand underlying patterns."
        )

        c1, c2 = st.columns([3, 1])
        with c1:
            decomp_metric = st.selectbox(
                "Metric to Decompose",
                options=list(metric_labels.keys()),
                format_func=lambda k: metric_labels[k],
                key="decomp_metric",
            )
        with c2:
            period = st.number_input("Seasonal Period", min_value=2, max_value=24, value=12, key="decomp_period")

        if st.button("Decompose", type="primary", key="decomp_run"):
            with st.spinner("Running seasonal decomposition..."):
                result = decompose_metric(
                    decomp_metric,
                    country=selected_country,
                    zone=selected_zone if selected_zone != "All" else None,
                    period=int(period),
                )

            if result.get("error"):
                st.warning(result["error"])
            else:
                _render_decomposition_chart(result, metric_labels.get(decomp_metric, decomp_metric))

    # ----------------------------------------------------------------
    # Tab 3: What-If Scenarios
    # ----------------------------------------------------------------
    with tab_scenarios:
        render_section_header(
            "What-if scenario modeling",
            eyebrow="Operational levers",
            icon="science",
        )
        st.markdown(
            "Explore the impact of operational changes on key utility KPIs. "
            "Adjust the sliders and click **Run Scenario** to see projected outcomes."
        )

        # Load data for scenarios
        billing_df = filter_df_by_user_access(query("SELECT * FROM billing"), "country")
        prod_df = filter_df_by_user_access(query("SELECT * FROM production"), "country")

        # Filter by country
        if selected_country and selected_country != "All":
            billing_df = billing_df[billing_df["country"].str.lower() == selected_country.lower()]
            prod_df = prod_df[prod_df["country"].str.lower() == selected_country.lower()]

        scenario_type = st.radio(
            "Scenario Type",
            ["NRW Reduction", "Tariff Change", "Coverage Expansion"],
            horizontal=True,
            key="scenario_type",
        )

        if scenario_type == "NRW Reduction":
            reduction = st.slider(
                "NRW Reduction (%)", 5, 50, 10,
                help="How much of current non-revenue water to recover",
                key="nrw_slider",
            )
            if st.button("Run Scenario", type="primary", key="sc_nrw"):
                result = simulate_nrw_reduction(billing_df, prod_df, reduction)
                if result:
                    _render_scenario_card(result)
                else:
                    st.warning("Insufficient data for NRW scenario")

        elif scenario_type == "Tariff Change":
            c1, c2 = st.columns(2)
            with c1:
                tariff_change = st.slider("Tariff Change (%)", -20, 30, 5, key="tariff_slider")
            with c2:
                elasticity = st.slider(
                    "Price Elasticity", -0.8, 0.0, -0.3, step=0.05,
                    help="Typical range for urban water: -0.2 to -0.5",
                    key="elasticity_slider",
                )
            if st.button("Run Scenario", type="primary", key="sc_tariff"):
                result = simulate_tariff_change(billing_df, tariff_change, elasticity)
                if result:
                    _render_scenario_card(result)
                else:
                    st.warning("Insufficient data for tariff scenario")

        elif scenario_type == "Coverage Expansion":
            c1, c2 = st.columns(2)
            with c1:
                new_conn = st.slider("New Connections", 100, 10000, 1000, step=100, key="conn_slider")
            with c2:
                avg_cons = st.slider(
                    "Avg Monthly Consumption (m³)", 5.0, 50.0, 15.0, step=1.0,
                    key="cons_slider",
                )
            if st.button("Run Scenario", type="primary", key="sc_expand"):
                result = simulate_coverage_expansion(billing_df, prod_df, new_conn, avg_cons)
                if result:
                    _render_scenario_card(result)
                else:
                    st.warning("Insufficient data for expansion scenario")

    # ----------------------------------------------------------------
    # Tab 4: Metric correlations
    # ----------------------------------------------------------------
    with tab_corr:
        render_section_header(
            "How metrics move together",
            eyebrow="Correlation explorer",
            icon="scatter_plot",
        )
        corr_df = _load_corr_frame(selected_country)
        metric_cols = [c for c in corr_df.columns if c != "month"]
        data = corr_df[metric_cols].dropna(how="all")
        if len(data) < 4 or data.shape[1] < 2:
            render_empty_state(
                "Not enough monthly data to compute correlations for this selection.",
                icon="scatter_plot",
            )
        else:
            labels = {
                "collection_eff": "Collection eff.", "consumption": "Consumption",
                "production": "Production", "nrw_pct": "NRW", "service_hours": "Service hours",
                "water_quality": "Water quality", "cost_recovery": "Cost recovery", "opex": "Opex",
            }
            corr = data.corr(numeric_only=True)
            disp = [labels.get(c, c) for c in corr.columns]
            fig_c = go.Figure(go.Heatmap(
                z=corr.values, x=disp, y=disp,
                zmin=-1, zmax=1,
                colorscale=[[0, STATUS_CRITICAL], [0.5, "#f1f4f7"], [1, DATA_WATER]],
                text=[[f"{v:.2f}" for v in row] for row in corr.values],
                texttemplate="%{text}", textfont=dict(size=10),
                hovertemplate="%{y} vs %{x}: %{z:.2f}<extra></extra>",
                colorbar=dict(title="r"),
            ))
            style_fig(fig_c, height=460)
            fig_c.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_c, use_container_width=True)
            st.caption("Pearson correlation of monthly metrics. +1 = move together, −1 = move oppositely.")

            # Scatter drill-down for a chosen pair.
            sc1, sc2 = st.columns(2)
            with sc1:
                x_m = st.selectbox("X metric", corr.columns, format_func=lambda c: labels.get(c, c), key="corr_x")
            with sc2:
                y_default = 1 if len(corr.columns) > 1 else 0
                y_m = st.selectbox("Y metric", corr.columns, index=y_default,
                                   format_func=lambda c: labels.get(c, c), key="corr_y")
            pair = data[[x_m, y_m]].dropna()
            if not pair.empty:
                fig_s = go.Figure(go.Scatter(
                    x=pair[x_m], y=pair[y_m], mode="markers",
                    marker=dict(color=DATA_WATER, size=9, opacity=0.75),
                    hovertemplate=f"{labels.get(x_m, x_m)}: %{{x:.1f}}<br>{labels.get(y_m, y_m)}: %{{y:.1f}}<extra></extra>",
                ))
                fig_s.update_layout(xaxis_title=labels.get(x_m, x_m), yaxis_title=labels.get(y_m, y_m))
                style_fig(fig_s, height=360)
                st.plotly_chart(fig_s, use_container_width=True)
