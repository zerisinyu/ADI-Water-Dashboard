"""
Documentation scene, a reference guide to the dashboard for first-time users.

Covers what each page shows, how the headline figures are calculated, how
the forecasting models work, and how the MajiBot assistant is configured.
"""
import streamlit as st

from utils import render_page_header, render_section_header


def scene_docs() -> None:
    render_page_header(
        "Documentation",
        eyebrow="User guide",
        subtitle="A field guide to the dashboard, its numbers, and the assistant.",
        icon="menu_book",
    )

    tab_start, tab_pages, tab_metrics, tab_forecast, tab_ai, tab_data = st.tabs([
        "Getting started",
        "The pages",
        "How the numbers work",
        "Forecasting",
        "MajiBot and AI",
        "Data and pipeline",
    ])

    # ------------------------------------------------------------------
    with tab_start:
        render_section_header("What the dashboard covers", icon="lightbulb")
        st.markdown(
            "The dashboard tracks four areas for a water and sanitation "
            "utility, one page each:\n\n"
            "- **Access and coverage**: who is reached by water and sanitation services, and to what standard.\n"
            "- **Service quality**: water quality compliance, continuity of supply, complaint handling.\n"
            "- **Financial health**: billing, collection, cost recovery, debt.\n"
            "- **Production**: output, service hours, and losses at the source level.\n\n"
            "A Home page summarizes all four with one headline metric each, plus "
            "a short list of current risks and wins. An Insights and Forecasting "
            "page adds projection and correlation tools on top of the same data."
        )

        render_section_header("Roles and access", icon="badge")
        st.markdown(
            "Access is role-based. Four roles exist:\n\n"
            "| Role | Scope | Can manage users |\n"
            "|---|---|---|\n"
            "| Master user | All countries | Yes, all non-master accounts |\n"
            "| Country administrator | One assigned country | Yes, lower-access accounts in the same country |\n"
            "| Data analyst | One assigned country | No |\n"
            "| Viewer | One assigned country | No |\n\n"
            "Anyone other than a master user sees a locked country indicator in "
            "the filter row instead of a country selector."
        )

        render_section_header("Filters", icon="tune")
        st.markdown(
            "Each page opens with its title and primary filters on one row: "
            "period, country, and zone or city, depending on the page. Year and "
            "month, where applicable, sit on a second row below. A selection "
            "carries over as the reader moves between pages, using shared "
            "session state rather than per-page state, so a country or year "
            "picked once does not need re-picking on the next page."
        )

        render_section_header("Missing data", icon="info")
        st.markdown(
            "Several measures are not in the current dataset: per-plant "
            "treatment capacity and efficiency, faecal-sludge-treatment "
            "utilization, national freshwater withdrawal figures, and some "
            "finance breakdowns (aged-debt buckets, capital expenditure, tariff "
            "bands). Rather than estimate these, the affected panels show a "
            "short data-gap notice, and each page ends with a **Data quality "
            "and alerts** section listing what is missing there."
        )

    # ------------------------------------------------------------------
    with tab_pages:
        render_section_header("Home", icon="dashboard")
        st.markdown(
            "One card per pillar (service coverage, financial health, "
            "operational efficiency, service quality), each a clickable link to "
            "its full page. Below that: a Top wins list, a Top risks list, and "
            "a MajiBot to-do list generated from the same threshold checks. A "
            "trends section covers the last twelve months, and, for master "
            "users, a cross-country benchmark radar (cross-zone instead, once "
            "a single country is selected)."
        )

        render_section_header("Access and Coverage", icon="map")
        st.markdown(
            "Water and sanitation coverage rates, metered connections, the "
            "JMP service ladder (safely managed / basic / limited / "
            "unimproved / surface water), and public toilet provision, broken "
            "down by zone."
        )

        render_section_header("Service Quality", icon="verified")
        st.markdown(
            "Water quality compliance (chlorine and E. coli sample pass "
            "rates), complaint resolution, network performance, asset health, "
            "and workforce metrics. A toggle switches the metric set between "
            "water, sanitation, or both."
        )

        render_section_header("Financial Health", icon="payments")
        st.markdown(
            "Billing, collection efficiency, cost recovery, debt, and "
            "staffing costs, at city and monthly granularity. A few charts "
            "run over several years rather than one, so a year filter does "
            "not flatten a multi-year trend."
        )

        render_section_header("Production", icon="factory")
        st.markdown(
            "Daily output, service hours, capacity utilization, and "
            "non-revenue water, measured per source (an intake or treatment "
            "works) rather than per zone. This page filters by source, not "
            "zone: a single source typically feeds several billing zones, so "
            "a zone filter here cannot be attributed without splitting a "
            "shared total. Trends and forecasting sit above the Infrastructure "
            "and Source-analysis tabs, since they apply regardless of which "
            "tab is open."
        )

        render_section_header("Insights and Forecasting", icon="insights")
        st.markdown(
            "Four tabs: a time-series forecast for a chosen metric, a "
            "seasonal decomposition, a what-if scenario tool for a small set "
            "of operational levers, and a metric-correlation explorer. "
            "Country and zone selectors at the top scope the input data."
        )

        render_section_header("Admin Settings", icon="settings")
        st.markdown(
            "User management (add, remove, change password), alert "
            "thresholds, data-quality checks, data lineage, and the layout of "
            "the Home page's briefing cards. Restricted to master users and "
            "country administrators. Account changes made here are "
            "session-scoped in this build: they apply for the current session "
            "and are not written back to the secrets file."
        )

    # ------------------------------------------------------------------
    with tab_metrics:
        render_section_header("Metric definitions", icon="calculate")
        st.markdown(
            "The metrics below share a single registry, so a given name means "
            "the same thing everywhere it appears. An ⓘ marker beside each "
            "metric on its page shows the same definition in place."
        )
        st.markdown(
            "| Metric | Formula |\n"
            "|---|---|\n"
            "| Non-revenue water (NRW) | (volume produced − volume billed) ÷ volume produced × 100 |\n"
            "| Collection efficiency | (water paid + sewer revenue) ÷ (water billed + sewer billed) × 100 |\n"
            "| O&M cost coverage | total revenue ÷ operating expenditure × 100 |\n"
            "| Consumption per capita | litres consumed ÷ population served ÷ days in period |\n"
            "| Water quality compliance | mean of chlorine and E. coli sample pass rates |\n"
            "| Service continuity | average hours of supply per day (target: 24) |\n"
            "| Water recycled or reused | volume of wastewater reused ÷ total water supplied × 100 |\n"
            "| Women in decision-making | women in decision-making posts ÷ total decision-making workforce × 100 |\n"
        )

        render_section_header("Composite scores", icon="functions")
        st.markdown(
            "The Home page's four pillar cards are composite indices on a "
            "0-100 scale:\n\n"
            "- **Financial health** = 0.4 × collection efficiency + 0.4 × O&M cost coverage (capped at 120, then rescaled to 100) + 0.2 × budget utilization.\n"
            "- **Operational efficiency** = average of (100 − NRW), capacity utilization, and (service hours ÷ 24 × 100).\n"
            "- **Service quality** = average of water-quality compliance, complaint resolution rate, and asset health.\n"
            "- **Service coverage** = average of water and sanitation safely-managed coverage, population-weighted.\n\n"
            "All four are computed monthly, with the exception of service "
            "coverage, which draws on the latest annual JMP access data."
        )

    # ------------------------------------------------------------------
    with tab_forecast:
        render_section_header("Time-series forecast", icon="trending_up")
        st.markdown(
            "Projects a selected metric forward 3 to 24 months using Holt-"
            "Winters exponential smoothing (statsmodels). With 24 or more "
            "months of history the model fits a seasonal component (12-month "
            "period); with less, it fits trend only. If the model cannot fit "
            "at all, the tab falls back to a linear-trend extrapolation. A "
            "minimum of 6 clean monthly observations is required; below that, "
            "the tab reports insufficient data instead of forecasting.\n\n"
            "The 80% and 95% shaded bands are not a model-derived statistical "
            "confidence interval. They are built from the standard deviation "
            "of the model's in-sample residuals, widened proportionally to "
            "the square root of the number of steps ahead, a random-walk-style "
            "widening, then scaled by the standard normal multipliers 1.28 "
            "and 1.96 for the 80% and 95% bands respectively. They indicate a "
            "plausible range under this heuristic, not a formal statistical "
            "guarantee.\n\n"
            "Summary cards report the latest actual value, the projected "
            "value at the chosen horizon, the percentage change, and which "
            "model variant produced the result."
        )

        render_section_header("Seasonal decomposition", icon="show_chart")
        st.markdown(
            "Splits a monthly series into trend, seasonal, and residual "
            "components using an additive decomposition "
            "(`statsmodels.tsa.seasonal.seasonal_decompose`), against a "
            "12-month period."
        )

        render_section_header("What-if scenarios", icon="science")
        st.markdown(
            "Not a predictive model. Each scenario applies a percentage lever "
            "(for example, a 10% cut in non-revenue water, or a tariff "
            "change) directly to the current period's totals and propagates "
            "the arithmetic consequence: less non-revenue water becomes more "
            "billable volume, which becomes more revenue at the prevailing "
            "tariff and collection rate. Output is a baseline, a projected "
            "value, and the percentage impact, useful for order-of-magnitude "
            "discussion rather than budget-grade planning."
        )

        render_section_header("Metric correlations", icon="hub")
        st.markdown(
            "Computes the Pearson correlation coefficient between two "
            "monthly metrics over the selected history, from −1 to 1. A high "
            "correlation does not establish causation; two metrics can move "
            "together because of a shared external driver, such as season, "
            "rather than one directly affecting the other."
        )

    # ------------------------------------------------------------------
    with tab_ai:
        render_section_header("What MajiBot does", icon="auto_awesome")
        st.markdown(
            "MajiBot is a chat assistant scoped to the current dashboard "
            "data. It answers questions about the metrics in view, drafts a "
            "board-brief summary, and generates a to-do list from the same "
            "threshold checks used on the Home page. It does not write to "
            "the underlying data or take any action outside the chat panel."
        )

        render_section_header("Bring your own key", icon="key")
        st.markdown(
            "AI features require an API key, entered on the Settings page. "
            "Supported providers: Gemini, GLM, Grok, OpenAI, DeepSeek, and "
            "OpenRouter. The dashboard uses whichever configured provider has "
            "a resolvable key, defaulting to Gemini if none is set. Without a "
            "key, MajiBot's chat and the AI-drafted brief and to-do list are "
            "unavailable, and the dashboard falls back to rule-based "
            "equivalents, so no feature depends on a key to remain usable."
        )

        render_section_header("How responses are grounded", icon="fact_check")
        st.markdown(
            "Generated text (the board brief, the to-do list) is produced "
            "from a fixed set of computed facts, passed to the model as "
            "grounding context with an explicit instruction to reuse those "
            "numbers rather than invent new ones. This constrains the model "
            "to the dashboard's own figures, but a generated summary should "
            "still be checked against the underlying chart or table before "
            "being acted on."
        )

    # ------------------------------------------------------------------
    with tab_data:
        render_section_header("Stack", icon="build")
        st.markdown(
            "- **Interface:** Streamlit\n"
            "- **Analytical storage:** DuckDB, embedded (no separate database server)\n"
            "- **Data wrangling:** pandas\n"
            "- **Charts:** Plotly\n"
            "- **Forecasting and decomposition:** statsmodels\n"
        )

        render_section_header("Pipeline", icon="database")
        st.markdown(
            "Seven source CSVs (`billing.csv`, `production.csv`, "
            "`sw_service.csv`, `w_access.csv`, `s_access.csv`, "
            "`all_fin_service.csv`, `all_nationalacc.csv`) are loaded into "
            "matching DuckDB tables on first run. A pipeline step then "
            "builds five derived, monthly-aggregated views (`v_billing_"
            "monthly`, `v_production_monthly`, `v_nrw_monthly`, `v_service_"
            "quality`, `v_financial_monthly`) on top of the raw tables. Pages "
            "read from these views rather than re-aggregating raw rows on "
            "every rerun; Streamlit's own caching sits on top of that, so a "
            "repeat visit with unchanged filters skips redundant computation."
        )
        try:
            from data.lineage import render_data_lineage
            with st.expander("Full data lineage diagram", expanded=False):
                render_data_lineage(height=560)
        except Exception:
            pass

        render_section_header("Custom uploads", icon="upload_file")
        st.markdown(
            "Each page has a collapsed Data Import panel. Uploading a CSV "
            "or Excel file with the expected columns replaces the page's "
            "data for the session; a Default Data option restores the "
            "shipped sample files."
        )

        render_section_header("Known gaps", icon="warning")
        st.markdown(
            "Not estimated, and shown as explicit data-gap panels instead: "
            "per-plant treatment capacity and efficiency, faecal-sludge-"
            "treatment utilization, SDG 6.4.2 water-stress inputs (national "
            "freshwater withdrawals), aged-debt breakdowns, capital "
            "expenditure, and tariff-band splits. Production volume, service "
            "hours, billing, and non-revenue water are measured, not "
            "estimated."
        )
