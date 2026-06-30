import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from typing import Dict, List
from utils import (
    KPI,
    chart_card,
    load_json,
    download_button as _download_button,
    scene_page_path as _scene_page_path,
    DATA_DIR,
    prepare_access_data,
    prepare_service_data,
    filter_df_by_user_access,
    validate_selected_country,
    render_kpi_row,
    render_section_header,
    _ensure_pipeline,
)
from charts import (
    DATA_SERIES,
    DATA_WATER,
    DATA_SANITATION,
    BRAND_STRONG,
    JMP_COLORS,
    LADDER_COLORS,
    STATUS_GOOD,
    STATUS_WARNING,
    STATUS_CRITICAL,
    apply_axis_currency,
    apply_axis_percent,
    style_fig,
    status_label,
    status_heatmap,
)
from data.database import query
from data.metrics import (
    non_revenue_water,
    collection_efficiency,
    cost_coverage,
    population_weighted_mean,
)
from ai_insights import InsightsEngine, generate_board_brief_text, generate_board_brief_llm
from auth import get_current_user
from llm import is_llm_configured
import briefing_config

def format_year_month(year: int, month: int = None) -> str:
    """Format year and month to readable format (e.g., 2020/6 or 2020)"""
    if month and isinstance(month, (int, float)):
        return f"{int(year)}/{int(month)}"
    return str(int(year))

def format_date_label(date_obj) -> str:
    """Format datetime object to readable label"""
    if pd.isna(date_obj):
        return "Unknown"
    if isinstance(date_obj, pd.Timestamp):
        return date_obj.strftime("%Y/%m")
    return str(date_obj)

@st.cache_data
def _load_raw_dashboard_data():
    """
    Load raw dashboard data from DuckDB (internal, cached).
    This loads all data without access filtering.
    """
    _ensure_pipeline()

    billing_df = query("SELECT * FROM billing WHERE date IS NOT NULL")

    fin_df = query("SELECT * FROM fin_service")

    prod_df = query("SELECT * FROM production")
    if not billing_df.empty:
        source_map = billing_df[["source", "zone", "country"]].drop_duplicates().dropna()
        prod_df = prod_df.merge(source_map, on=["source", "country"], how="left")
        prod_df["zone"] = prod_df["zone"].fillna("Unknown")

    nat_df = query("SELECT * FROM national_accounts")

    return billing_df, fin_df, prod_df, nat_df


def load_dashboard_data():
    """
    Load and prepare data for the executive dashboard.
    Data is automatically filtered based on user access permissions.
    """
    billing_df, fin_df, prod_df, nat_df = _load_raw_dashboard_data()

    billing_df = filter_df_by_user_access(billing_df.copy(), "country")
    fin_df = filter_df_by_user_access(fin_df.copy(), "country")
    prod_df = filter_df_by_user_access(prod_df.copy(), "country")
    nat_df = filter_df_by_user_access(nat_df.copy(), "country")

    return billing_df, fin_df, prod_df, nat_df


@st.cache_data
def _load_monthly_trends(country: str, zone: str) -> dict:
    """Monthly trend frames pulled from the pre-aggregated DuckDB views
    (v_billing_monthly / v_nrw_monthly / v_service_quality / v_financial_monthly)
    instead of re-grouping the full billing table in pandas on every rerun.

    Filtered by country (and zone where the view carries it). Access control is
    enforced because `country` is the already-validated selection — non-master
    users are pinned to their assigned country upstream. Returns month-keyed
    frames (month = first-of-month DATE).
    """
    def _where(has_zone: bool):
        clauses, params = [], []
        if country and country != "All":
            clauses.append("LOWER(country) = ?")
            params.append(country.lower())
        if has_zone and zone and zone != "All":
            clauses.append("LOWER(zone) = ?")
            params.append(zone.lower())
        return ((" WHERE " + " AND ".join(clauses)) if clauses else ""), params

    w, p = _where(True)
    billing = query(
        f"SELECT month, SUM(total_billed) AS billed, SUM(total_paid) AS paid, "
        f"SUM(total_consumption_m3) AS consumption FROM v_billing_monthly{w} "
        f"GROUP BY month ORDER BY month", p)

    w, p = _where(False)
    nrw = query(
        f"SELECT month, SUM(total_production_m3) AS production, "
        f"SUM(total_consumption_m3) AS consumption, "
        f"CASE WHEN SUM(total_production_m3) > 0 THEN "
        f"(SUM(total_production_m3) - SUM(total_consumption_m3)) / SUM(total_production_m3) * 100 "
        f"ELSE NULL END AS nrw_pct, AVG(avg_service_hours) AS service_hours "
        f"FROM v_nrw_monthly{w} GROUP BY month ORDER BY month", p)

    w, p = _where(True)
    quality = query(
        f"SELECT date_trunc('month', date)::DATE AS month, "
        f"AVG(water_quality_rate) AS water_quality_rate FROM v_service_quality{w}"
        f"{' AND' if w else ' WHERE'} water_quality_rate IS NOT NULL "
        f"GROUP BY 1 ORDER BY 1", p)

    w, p = _where(False)
    financial = query(
        f"SELECT date_trunc('month', date)::DATE AS month, SUM(opex) AS opex, "
        f"SUM(sewer_revenue) AS sewer_revenue FROM v_financial_monthly{w} "
        f"GROUP BY 1 ORDER BY 1", p)

    return {"billing": billing, "nrw": nrw, "quality": quality, "financial": financial}


def filter_dataframe(df, country, zone, year, month):
    """
    Filter dataframe based on selected criteria.
    Uses case-insensitive comparison for country and zone.
    """
    if df.empty:
        return df
    
    filtered = df.copy()
    
    if country and country != "All":
        if "country" in filtered.columns:
            # Case-insensitive comparison for country
            filtered = filtered[filtered["country"].str.lower() == country.lower()]
    
    if zone and zone != "All":
        if "zone" in filtered.columns:
            # Case-insensitive comparison for zone
            filtered = filtered[filtered["zone"].str.lower() == zone.lower()]
            
    if year and year != "All":
        if "date" in filtered.columns:
            filtered = filtered[filtered["date"].dt.year == int(year)]
        elif "year" in filtered.columns:
             # national_accounts and access tables both expose a 4-digit `year`
             filtered = filtered[filtered["year"] == int(year)]

    if month and month != "All":
        # Map month name to number
        month_map = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }
        m_num = month_map.get(month)
        if m_num and "date" in filtered.columns:
            filtered = filtered[filtered["date"].dt.month == m_num]
            
    return filtered

_STATUS_DELTA_KIND = {"good": "positive", "warning": "neutral", "critical": "negative"}


def _delta_kind_for_status(status_class: str) -> str:
    """Map a status string into a KPI delta-kind."""
    if "good" in status_class or status_class == "Healthy":
        return "positive"
    if "critical" in status_class or status_class == "Critical":
        return "negative"
    return "neutral"

def scene_executive():
    # --- 1. Load Data (automatically filtered by user access) ---
    billing_df, fin_df, prod_df, nat_df = load_dashboard_data()
    access_data = prepare_access_data()
    service_data_dict = prepare_service_data()

    # --- 2. Get Filters from Session State (validated against user access) ---
    selected_country = st.session_state.get("selected_country", "All")
    # Validate country selection against user access permissions
    selected_country = validate_selected_country(selected_country)
    st.session_state["selected_country"] = selected_country
    
    selected_zone = st.session_state.get("selected_zone", "All")
    selected_year = st.session_state.get("selected_year", "All")
    selected_month = st.session_state.get("selected_month", "All")

    # --- 3. Filter Data ---
    f_billing = filter_dataframe(billing_df, selected_country, selected_zone, selected_year, selected_month)
    f_fin = filter_dataframe(fin_df, selected_country, selected_zone, selected_year, selected_month)
    f_prod = filter_dataframe(prod_df, selected_country, selected_zone, selected_year, selected_month)
    f_nat = filter_dataframe(nat_df, selected_country, "All", selected_year, "All") # National data usually country level

    # Access Data Filtering (case-insensitive)
    w_latest = access_data["water_latest"]
    s_latest = access_data["sewer_latest"]
    if selected_country and selected_country != "All":
        w_latest = w_latest[w_latest["country"].str.lower() == selected_country.lower()]
        s_latest = s_latest[s_latest["country"].str.lower() == selected_country.lower()]
    if selected_zone and selected_zone != "All":
        w_latest = w_latest[w_latest["zone"].str.lower() == selected_zone.lower()]
        s_latest = s_latest[s_latest["zone"].str.lower() == selected_zone.lower()]

    # Service Data Filtering
    svc_df = service_data_dict["full_data"]
    svc_df = filter_dataframe(svc_df, selected_country, selected_zone, selected_year, selected_month)

    # --- 4. Calculate KPIs for Cards ---

    # Card 1: Service Coverage Score
    # Coverage % must be POPULATION-WEIGHTED across zones — a simple mean lets a
    # 2-person zone count the same as a 2-million-person zone, which is wrong for
    # SDG 6 reporting. Fall back to a plain mean only if population is missing.
    w_cov = population_weighted_mean(w_latest, "water_safely_pct", "popn_total")
    if w_cov is None:
        w_cov = w_latest["water_safely_pct"].mean() if not w_latest.empty else 0
    s_cov = population_weighted_mean(s_latest, "sewer_safely_pct", "popn_total")
    if s_cov is None:
        s_cov = s_latest["sewer_safely_pct"].mean() if not s_latest.empty else 0

    coverage_score = (w_cov + s_cov) / 2
    pop_served = (w_latest["popn_total"].sum() / 1_000_000) if not w_latest.empty else 0
    
    cov_status = "status-good" if coverage_score > 80 else "status-warning" if coverage_score > 60 else "status-critical"

    # Card 2: Financial Health Index
    # Canonical, utility-wide definitions (water + sewer) from data.metrics so
    # the Executive and Financial Health pages cannot disagree on these numbers.
    total_billed = f_billing["billed"].sum()
    total_paid = f_billing["paid"].sum()
    coll_eff = collection_efficiency(f_billing, f_fin) or 0.0

    total_sewer_rev = f_fin["sewer_revenue"].sum()
    total_revenue = total_paid + total_sewer_rev
    total_opex = f_fin["opex"].sum()
    opex_cov = cost_coverage(f_billing, f_fin) or 0.0
    
    # Budget Utilization (Annual)
    # If monthly filter is on, we might not have full budget context, but let's try
    total_budget = f_nat["budget_allocated"].sum()
    # If we are looking at a month, budget utilization might be low. 
    # Let's use Opex Coverage as the main driver if budget is missing
    budget_util = (total_opex / total_budget * 100) if total_budget > 0 else 0
    
    # Composite Financial Score (Weighted)
    # Cap metrics at 100 for scoring purposes
    fin_score = (min(coll_eff, 100) * 0.4) + (min(opex_cov, 120)/1.2 * 0.4) + (min(budget_util, 100) * 0.2)
    fin_status = "Healthy" if fin_score > 80 else "At Risk" if fin_score > 60 else "Critical"

    # Card 3: Operational Efficiency
    total_prod = f_prod["production_m3"].sum()
    total_cons = f_billing["consumption_m3"].sum()
    nrw = non_revenue_water(f_prod, f_billing) or 0.0
    
    # Capacity Utilization (Wastewater)
    ww_cap = svc_df["ww_capacity"].sum()
    ww_treated = svc_df["ww_treated"].sum()
    cap_util = (ww_treated / ww_cap * 100) if ww_cap > 0 else 0
    
    service_hours = f_prod["service_hours"].mean() if not f_prod.empty else 0
    
    # Efficiency Score: Lower NRW is better. Higher Cap Util & Service Hours is better.
    # Normalize NRW: (100 - NRW)
    # Normalize Service Hours: (Hours / 24 * 100)
    eff_score = ((100 - min(nrw, 100)) + min(cap_util, 100) + (service_hours/24*100)) / 3
    
    # Card 4: Service Quality Index
    wq_compliance = svc_df["water_quality_rate"].mean() if not svc_df.empty else 0
    cust_res_rate = svc_df["complaint_resolution_rate"].mean() if not svc_df.empty else 0
    asset_health = f_nat["asset_health"].mean() if not f_nat.empty else 0 # Scale 0-100 usually? Data says 66.31 etc.
    
    qual_score = (wq_compliance + cust_res_rate + asset_health) / 3

    # --- 5. Create AI Insights Engine ---
    insights_engine = InsightsEngine(f_billing, f_prod, f_fin)
    daily_pulse = insights_engine.generate_daily_pulse()
    overall_score = insights_engine.calculate_overall_score()
    anomalies = insights_engine.detect_anomalies()
    suggested_questions = insights_engine.get_suggested_questions()
    
    # Cache insights for LLM access
    st.session_state["exec_insights_cache"] = {
        "overall_score": overall_score,
        "collection_efficiency": coll_eff,
        "nrw_percent": nrw,
        "service_hours": service_hours,
        "anomalies": anomalies,
        "zones": insights_engine.zone_performance_summary(),
        "suggested_questions": suggested_questions
    }

    # MajiBot's "read on today" is no longer shown as a separate expander on the
    # home page — instead it's stashed here so it can be folded into MajiBot's
    # chat context (see llm.build_data_context_prompt).
    try:
        from ai_insights import generate_quick_insight
        _daily_reading = generate_quick_insight(f_billing, f_prod, f_fin, selected_country)
        if _daily_reading:
            st.session_state["daily_reading"] = _daily_reading
    except Exception:
        pass

    # --- 6. Layout & Visualization ---

    # =======================================================================
    # DAILY BRIEFING — manager-style landing page.
    # Replaces the previous "AI quick insight" hero with a four-part
    # briefing: status header → overnight deltas → top risks/wins +
    # today's action list → cross-cutting targets bar. The original
    # KPI row + tabbed trend deep-dives sit below this block, acting as
    # the "open the dashboard" surface once the manager has scanned the
    # briefing.
    # =======================================================================
    import html as _html_mod
    from datetime import datetime as _dt
    from utils import (
        render_status_badge,
        render_risk_card,
        render_majibot_todo,
    )

    # --- A. Status header --------------------------------------------------
    if eff_score >= 80 and qual_score >= 80 and fin_score >= 80:
        overall_state, badge_label = "good", "All pillars healthy"
    elif eff_score < 60 or qual_score < 60 or fin_score < 60:
        overall_state, badge_label = "critical", "Action required"
    else:
        overall_state, badge_label = "warn", "Watch list"

    today_str = _dt.now().strftime("%A · %B %d, %Y")
    badge_html = render_status_badge(overall_state, badge_label)
    scope_label = selected_country if selected_country and selected_country != "All" else "All countries"

    # Only admins may customise the briefing layout.
    try:
        _cur_user = get_current_user()
        _role_v = getattr(getattr(_cur_user, "role", None), "value", "") or ""
    except Exception:
        _role_v = ""
    is_admin = _role_v in {"master_user", "country_admin"}

    @st.dialog("Customise daily briefing")
    def _briefing_dialog():
        st.write(
            "Choose which metric appears in each briefing card and how it's "
            "visualised (sparkline or donut). Customisation lives on the "
            "**Settings** page."
        )
        gc1, gc2 = st.columns(2)
        with gc1:
            if st.button("Go to Settings", type="primary", width="stretch"):
                st.switch_page("pages/6_Admin_Settings.py")
        with gc2:
            if st.button("Stay here", width="stretch"):
                st.rerun()

    hdr_col, gear_col = st.columns([0.93, 0.07])
    with hdr_col:
        st.markdown(
            f'<div class="briefing-header">'
            f'<div class="briefing-header__title">'
            f'<h2>Daily briefing</h2>'
            f'<span class="briefing-date">{today_str} · {_html_mod.escape(scope_label)}</span>'
            f'</div>'
            f'{badge_html}'
            f'</div>',
            unsafe_allow_html=True,
        )
    with gear_col:
        if is_admin:
            if st.button(":material/settings:", key="briefing_gear",
                         help="Customise the daily briefing"):
                _briefing_dialog()

    # --- B. Briefing cards — one configurable card per pillar -------------
    # Merges the old overnight-delta band and the pillar quick-look into a single
    # admin-configurable four-card row (one card per sector). No fixed targets —
    # actuals + trend only. Admins pick the metric and viz per slot in Settings.
    def _last_n(series, n=12):
        s = series.dropna().tail(n).tolist() if hasattr(series, "dropna") else []
        return [float(x) for x in s if isinstance(x, (int, float))]

    cov_spark = []
    if not f_nat.empty and "water_access" in f_nat.columns:
        cov_spark = _last_n(f_nat.sort_values("year")["water_access"]) if "year" in f_nat.columns else _last_n(f_nat["water_access"])
    eff_spark = _last_n(f_prod.sort_values("date_dt").groupby(f_prod["date_dt"].dt.to_period("M"))["production_m3"].sum()) if not f_prod.empty and "date_dt" in f_prod.columns else []
    fin_spark = _last_n(f_billing.sort_values("date_dt").groupby(f_billing["date_dt"].dt.to_period("M"))["paid"].sum()) if not f_billing.empty and "date_dt" in f_billing.columns else []
    qual_spark = _last_n(svc_df["water_quality_rate"]) if not svc_df.empty and "water_quality_rate" in svc_df.columns else []

    cov_kind = _delta_kind_for_status(cov_status)
    fin_kind = _delta_kind_for_status(fin_status)
    eff_status = status_label(eff_score, good=80, warning=60, higher_is_better=True)
    qual_status = status_label(qual_score, good=80, warning=60, higher_is_better=True)

    # Display props per choosable metric id (value/delta/footnote/series/pct).
    # Labels, icons and registry-keys come from briefing_config.METRIC_CHOICES.
    # Composite indices aren't in METRIC_REGISTRY, so they carry their own help
    # text; registry-backed metrics fall through to the ⓘ tooltip via metric_key.
    _help = {
        "service_coverage": "Average of water & sanitation safely-managed coverage (%), population-weighted. Source: annual JMP access data.",
        "financial_health": "Composite 0–100: 40% collection efficiency + 40% O&M cost coverage + 20% budget utilisation. Monthly.",
        "operational_efficiency": "Composite 0–100: average of (100 − NRW%), capacity utilisation % and service hours ÷ 24. Monthly.",
        "service_quality": "Composite 0–100: average of water-quality compliance, complaint resolution and asset health. Monthly.",
        "capacity_utilisation": "Wastewater treated ÷ design capacity × 100. Monthly.",
        "complaint_resolution": "Complaints resolved ÷ complaints received × 100. Monthly.",
        "water_coverage": "Population with safely-managed water ÷ total population × 100. Annual (JMP).",
        "sanitation_coverage": "Population with safely-managed sanitation ÷ total population × 100. Annual (JMP).",
    }
    metric_values = {
        "service_coverage": dict(value=f"{coverage_score:.0f}%", delta=f"Water {w_cov:.0f}% · San {s_cov:.0f}%", delta_kind=cov_kind, footnote=f"{pop_served:.1f}M people served", pct=coverage_score, series=cov_spark),
        "water_coverage": dict(value=f"{w_cov:.0f}%", delta="Safely managed", delta_kind="neutral", footnote=f"{pop_served:.1f}M people", pct=w_cov, series=cov_spark),
        "sanitation_coverage": dict(value=f"{s_cov:.0f}%", delta="Safely managed", delta_kind="neutral", footnote=None, pct=s_cov, series=[]),
        "financial_health": dict(value=f"{fin_score:.0f}", delta=fin_status, delta_kind=fin_kind, footnote=f"Revenue ${total_revenue / 1e6:.1f}M · Cost recovery {opex_cov:.0f}%", pct=fin_score, series=fin_spark),
        "collection_efficiency": dict(value=f"{coll_eff:.1f}%", delta="Utility-wide cash", delta_kind="neutral", footnote="Water + sewer collected", pct=min(coll_eff, 100), series=fin_spark),
        "cost_coverage": dict(value=f"{opex_cov:.0f}%", delta="O&M coverage", delta_kind="neutral", footnote="Revenue ÷ opex", pct=min(opex_cov, 100), series=[]),
        "operational_efficiency": dict(value=f"{eff_score:.0f}", delta=f"NRW {nrw:.1f}% · Continuity {service_hours:.1f}h", delta_kind=_STATUS_DELTA_KIND[eff_status], footnote=f"Capacity utilisation {cap_util:.0f}%", pct=eff_score, series=eff_spark),
        "nrw": dict(value=f"{nrw:.1f}%", delta="Distribution losses", delta_kind="neutral", footnote="Lower is better", pct=min(nrw, 100), series=eff_spark),
        "capacity_utilisation": dict(value=f"{cap_util:.0f}%", delta="of design capacity", delta_kind="neutral", footnote=None, pct=min(cap_util, 100), series=[]),
        "service_continuity": dict(value=f"{(service_hours or 0):.1f} hrs/day", delta="Target 24h", delta_kind="neutral", footnote=None, pct=min((service_hours or 0) / 24 * 100, 100), series=[]),
        "service_quality": dict(value=f"{qual_score:.0f}", delta=f"Water qual {wq_compliance:.0f}% · Resolution {cust_res_rate:.0f}%", delta_kind=_STATUS_DELTA_KIND[qual_status], footnote="Index of compliance, resolution & asset health", pct=qual_score, series=qual_spark),
        "water_quality_compliance": dict(value=f"{wq_compliance:.0f}%", delta="Samples passed", delta_kind="neutral", footnote=None, pct=wq_compliance, series=qual_spark),
        "complaint_resolution": dict(value=f"{cust_res_rate:.0f}%", delta="Complaints resolved", delta_kind="neutral", footnote=None, pct=cust_res_rate, series=[]),
    }

    layout = briefing_config.load_layout()
    briefing_cards = []
    for slot in briefing_config.SLOTS:
        sel = layout[slot]
        metric_id, viz = sel["metric"], sel["viz"]
        label, icon, mkey = briefing_config.METRIC_CHOICES[slot][metric_id]
        props = metric_values.get(metric_id, {})
        briefing_cards.append(KPI(
            label=label,
            value=props.get("value", "—"),
            delta=props.get("delta"),
            delta_kind=props.get("delta_kind", "neutral"),
            footnote=props.get("footnote"),
            icon=icon,
            metric_key=mkey,
            help=_help.get(metric_id),
            sparkline=(props.get("series") or None) if viz == "sparkline" else None,
            donut=(props.get("pct") if viz == "donut" else None),
        ))
    render_kpi_row(briefing_cards)

    # One "Open …" deep-link under each briefing card, in slot order
    # (access · finance · ops · quality).
    _slot_pages = {
        "access":  ("pages/2_Access_&_Coverage.py", "Open Access & Coverage"),
        "finance": ("pages/4_Financial_Health.py", "Open Financial Health"),
        "ops":     ("pages/5_Production.py", "Open Production"),
        "quality": ("pages/3_Service_Quality.py", "Open Service & Quality"),
    }
    nav_cols = st.columns(len(briefing_config.SLOTS))
    for col, slot in zip(nav_cols, briefing_config.SLOTS):
        page, label = _slot_pages[slot]
        with col:
            st.page_link(page, label=label, icon=":material/arrow_forward:", width="stretch")

    # --- C. Signals (risks/wins toggle) + MajiBot to-do -------------------
    risk_items: List[Dict[str, str]] = []
    win_items: List[Dict[str, str]] = []
    try:
        for a in (anomalies or [])[:6]:
            metric = a.get("metric", "metric")
            zone = a.get("zone") or a.get("country") or "system"
            change_pct = a.get("change_pct", 0)
            direction_bad = (
                (metric.lower() in {"nrw", "non_revenue_water", "opex", "complaints"} and change_pct > 0) or
                (metric.lower() in {"collection_efficiency", "service_hours", "paid", "revenue"} and change_pct < 0)
            )
            item = {
                "label": f"{metric.replace('_', ' ').title()} · {zone}",
                "detail": f"Changed {change_pct:+.1f}% vs prior window",
            }
            if direction_bad:
                item["action"] = "Investigate root cause"
                if len(risk_items) < 3:
                    risk_items.append(item)
            else:
                if len(win_items) < 3:
                    win_items.append(item)
    except Exception:
        pass

    # Threshold-driven risks (NRW, collection, service hours, water quality).
    try:
        from ai_insights import ALERT_THRESHOLDS
        if nrw > ALERT_THRESHOLDS["nrw"]["warning"]:
            risk_items.insert(0, {
                "label": f"NRW at {nrw:.1f}% — above warning ({ALERT_THRESHOLDS['nrw']['warning']}%)",
                "detail": "Distribution losses are eating into revenue.",
                "action": "Open Access & Coverage → audit Zone 4 meters.",
            })
        if coll_eff < ALERT_THRESHOLDS["collection_efficiency"]["warning"]:
            risk_items.append({
                "label": f"Collection efficiency at {coll_eff:.1f}%",
                "detail": f"Below the {ALERT_THRESHOLDS['collection_efficiency']['warning']}% warning line.",
                "action": "Open Financial Health → review aged debt.",
            })
    except Exception:
        pass

    # MajiBot's to-do list — threshold-driven next actions (replaces the old
    # "Today's actions" checklist; lives beside the signals toggle).
    todo_items: List[Dict[str, str]] = []
    if nrw > 30:
        todo_items.append({"text": f"Investigate NRW spike ({nrw:.1f}%) — drill into the worst-performing zone."})
    if coll_eff < 85:
        todo_items.append({"text": f"Collection efficiency below target — {coll_eff:.1f}% vs 85%. Review aged debt."})
    if service_hours and service_hours < 18:
        todo_items.append({"text": f"Service continuity at {service_hours:.1f} hrs/day — below the 18-hour target."})
    if not todo_items:
        todo_items.append({"text": "No threshold breaches detected — continue routine monitoring."})

    # Signals (left) toggles between risks & wins as one equal-height card;
    # MajiBot's to-do sits on the right.
    sig_col, todo_col = st.columns([1, 1])
    with sig_col:
        with st.container(key="signals-card"):
            signal_view = st.segmented_control(
                "Signals",
                ["Top risks", "Top wins"],
                default="Top risks",
                key="signals_toggle",
                label_visibility="collapsed",
            ) or "Top risks"
            if signal_view == "Top wins":
                render_risk_card("Top wins", win_items[:4], tone="good", bare=True)
            else:
                render_risk_card("Top risks", risk_items[:4], tone="warn", bare=True)
    with todo_col:
        render_majibot_todo("MajiBot's to-do", todo_items[:5])

    # --- Performance Trends Dashboard ---
    render_section_header("Performance trends", eyebrow="At a glance · last 12 months", icon="show_chart")

    # Monthly trends come from the pre-aggregated DuckDB views (cheap) rather than
    # re-grouping the full billing table in pandas on every rerun.
    trends = _load_monthly_trends(selected_country, selected_zone)

    # The access ladders below read the (small, annual) access tables directly.
    trend_water_acc = access_data["water_full"].copy()
    if selected_country and selected_country != "All":
        trend_water_acc = trend_water_acc[trend_water_acc["country"].str.lower() == selected_country.lower()]
    if selected_zone and selected_zone != "All" and "zone" in trend_water_acc.columns:
        trend_water_acc = trend_water_acc[trend_water_acc["zone"].str.lower() == selected_zone.lower()]

    # =======================================================================
    # A. Pillar health heatmap — the at-a-glance object. 4 pillars × last 12
    #    months, each cell green/amber/red by threshold. Trajectory reads
    #    left→right, cross-pillar comparison top→bottom. Deliberately distinct
    #    from the briefing cards above; detailed per-metric charts stay on their
    #    own pages. Built from the monthly views.
    # =======================================================================
    heat = (
        trends["billing"]
        .merge(trends["nrw"][["month", "nrw_pct", "service_hours"]], on="month", how="outer")
        .merge(trends["quality"], on="month", how="outer")
        .sort_values("month").tail(12)
    )
    if not heat.empty:
        heat["coll"] = heat["paid"] / heat["billed"].replace(0, float("nan")) * 100
        month_labels = [pd.Timestamp(m).strftime("%b %y") for m in heat["month"]]
        heat_rows = [
            {"label": "Collection eff.", "values": heat["coll"].tolist(),
             "good": 90, "warning": 80, "higher_is_better": True, "fmt": "{:.0f}%"},
            {"label": "Non-revenue water", "values": heat["nrw_pct"].tolist(),
             "good": 25, "warning": 35, "higher_is_better": False, "fmt": "{:.0f}%"},
            {"label": "Service hours", "values": heat["service_hours"].tolist(),
             "good": 20, "warning": 12, "higher_is_better": True, "fmt": "{:.0f}h"},
            {"label": "Water quality", "values": heat["water_quality_rate"].tolist(),
             "good": 95, "warning": 85, "higher_is_better": True, "fmt": "{:.0f}%"},
        ]
        fig_heat = status_heatmap(month_labels, heat_rows, height=260)
        with chart_card("Pillar health heatmap",
                        meta="Green on track · amber watch · red action — last 12 months"):
            st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.info("Not enough monthly data to build the performance heatmap.")

    # =======================================================================
    # B. Access & sanitation ladders — population by service level, two area
    #    charts side by side, using the shared access-page palette.
    # =======================================================================
    cov_l, cov_r = st.columns(2)

    with cov_l:
        w_cols = ["w_safely_managed_pct", "w_basic_pct", "w_limited_pct", "w_unimproved_pct", "surface_water_pct"]
        for c in w_cols:
            if c in trend_water_acc.columns:
                trend_water_acc[c] = pd.to_numeric(trend_water_acc[c], errors="coerce").fillna(0)

        if "popn_total" in trend_water_acc.columns:
            for c in w_cols:
                if c in trend_water_acc.columns:
                    level_name = c.replace("_pct", "")
                    trend_water_acc[level_name] = trend_water_acc["popn_total"] * (trend_water_acc[c] / 100)

            level_cols = [c.replace("_pct", "") for c in w_cols if c in trend_water_acc.columns]
            w_trend = trend_water_acc.groupby("year")[level_cols].sum().reset_index()

            if len(w_trend) > 0:
                fig_cov = go.Figure()
                order = ["w_safely_managed", "w_basic", "w_limited", "w_unimproved", "surface_water"]
                colors = LADDER_COLORS["water"]
                labels = ["Safely Managed", "Basic", "Limited", "Unimproved", "Surface Water"]
                for i, level in enumerate(order):
                    if level in w_trend.columns:
                        fig_cov.add_trace(go.Scatter(
                            x=w_trend["year"].apply(lambda y: format_year_month(int(y))),
                            y=w_trend[level], name=labels[i], stackgroup="one", mode="lines",
                            line=dict(width=0.5, color=colors[i]), fillcolor=colors[i],
                            hovertemplate="%{customdata}<br>Population: %{y:,.0f}<extra></extra>",
                            customdata=[labels[i]] * len(w_trend),
                        ))
                style_fig(fig_cov, height=320)
                fig_cov.update_layout(yaxis=dict(title="Population"), xaxis=dict(title="Year"))
                with chart_card("Water access ladder", meta="Population by service level"):
                    st.plotly_chart(fig_cov, use_container_width=True)
            else:
                st.warning("No water coverage data available for selected period")
        else:
            st.warning("Population data not available for water coverage trends.")

    with cov_r:
        trend_san_acc = access_data["sewer_full"].copy()
        if selected_country and selected_country != "All":
            trend_san_acc = trend_san_acc[trend_san_acc["country"].str.lower() == selected_country.lower()]
        if selected_zone and selected_zone != "All" and "zone" in trend_san_acc.columns:
            trend_san_acc = trend_san_acc[trend_san_acc["zone"].str.lower() == selected_zone.lower()]

        s_cols = ["s_safely_managed_pct", "s_basic_pct", "s_limited_pct", "s_unimproved_pct", "open_def_pct"]
        for c in s_cols:
            if c in trend_san_acc.columns:
                trend_san_acc[c] = pd.to_numeric(trend_san_acc[c], errors="coerce").fillna(0)

        if "popn_total" in trend_san_acc.columns:
            for c in s_cols:
                if c in trend_san_acc.columns:
                    level_name = c.replace("_pct", "")
                    trend_san_acc[level_name] = trend_san_acc["popn_total"] * (trend_san_acc[c] / 100)

            s_level_cols = [c.replace("_pct", "") for c in s_cols if c in trend_san_acc.columns]
            s_trend = trend_san_acc.groupby("year")[s_level_cols].sum().reset_index()

            if len(s_trend) > 0:
                fig_san = go.Figure()
                s_order = ["s_safely_managed", "s_basic", "s_limited", "s_unimproved", "open_def"]
                san_colors = LADDER_COLORS["sanitation"]
                s_labels = ["Safely Managed", "Basic", "Limited", "Unimproved", "Open Defecation"]
                for i, level in enumerate(s_order):
                    if level in s_trend.columns:
                        fig_san.add_trace(go.Scatter(
                            x=s_trend["year"].apply(lambda y: format_year_month(int(y))),
                            y=s_trend[level], name=s_labels[i], stackgroup="san", mode="lines",
                            line=dict(width=0.5, color=san_colors[i]), fillcolor=san_colors[i],
                            hovertemplate="%{customdata}<br>Population: %{y:,.0f}<extra></extra>",
                            customdata=[s_labels[i]] * len(s_trend),
                        ))
                style_fig(fig_san, height=320)
                fig_san.update_layout(yaxis=dict(title="Population"), xaxis=dict(title="Year"))
                with chart_card("Sanitation access ladder", meta="Population by service level"):
                    st.plotly_chart(fig_san, use_container_width=True)
            else:
                st.warning("No sanitation coverage data available for selected period")
        else:
            st.warning("Population data not available for sanitation coverage trends.")

    # =======================================================================
    # C. Financial performance — revenue vs opex as comparable bars on the $
    #    axis; collection efficiency & cost recovery as PERCENT lines on the
    #    right axis (the % suffix and % hovertemplates fix the old "currency"
    #    mislabelling).
    # =======================================================================
    merged_fin = pd.merge(trends["billing"], trends["financial"], on="month", how="outer").fillna(0)
    merged_fin["total_revenue"] = merged_fin["paid"] + merged_fin["sewer_revenue"]
    merged_fin["coll_eff"] = (merged_fin["paid"] / merged_fin["billed"].replace(0, 1) * 100).clip(0, 150)
    merged_fin["cost_recovery"] = (merged_fin["total_revenue"] / merged_fin["opex"].replace(0, 1) * 100).clip(0, 200)
    merged_fin = merged_fin.sort_values("month").tail(12)

    if len(merged_fin) > 0:
        fig_fin = go.Figure()
        fig_fin.add_trace(go.Bar(x=merged_fin["month"], y=merged_fin["total_revenue"], name="Revenue",
                                 marker_color=STATUS_GOOD, opacity=0.9,
                                 hovertemplate="Revenue: $%{y:,.0f}<extra></extra>"))
        fig_fin.add_trace(go.Bar(x=merged_fin["month"], y=merged_fin["opex"], name="Opex",
                                 marker_color=STATUS_WARNING, opacity=0.9,
                                 hovertemplate="Opex: $%{y:,.0f}<extra></extra>"))
        fig_fin.add_trace(go.Scatter(x=merged_fin["month"], y=merged_fin["coll_eff"], name="Collection efficiency",
                                     yaxis="y2", line=dict(color=DATA_WATER, width=2.5),
                                     hovertemplate="Collection: %{y:.1f}%<extra></extra>"))
        fig_fin.add_trace(go.Scatter(x=merged_fin["month"], y=merged_fin["cost_recovery"], name="Cost recovery",
                                     yaxis="y2", line=dict(color=BRAND_STRONG, width=2.5, dash="dot"),
                                     hovertemplate="Cost recovery: %{y:.1f}%<extra></extra>"))
        style_fig(fig_fin, height=380, legend_top=True)
        fig_fin.update_layout(
            barmode="group",
            yaxis=dict(title="Amount ($)"),
            yaxis2=dict(title="Percent (%)", overlaying="y", side="right", range=[0, 200],
                        showgrid=False, ticksuffix="%"),
        )
        apply_axis_currency(fig_fin, axis="y")
        with chart_card("Financial performance", meta="Revenue vs opex ($) · collection & cost recovery (%)"):
            st.plotly_chart(fig_fin, use_container_width=True)
    else:
        st.info("No financial data available for selected period")

    # =======================================================================
    # D. Cross-country performance benchmark — master users only, with a
    #    score explainer.
    # =======================================================================
    try:
        _bench_user = get_current_user()
        _is_master = getattr(getattr(_bench_user, "role", None), "value", "") == "master_user"
    except Exception:
        _is_master = False

    if _is_master:
        render_section_header(
            "Cross-country performance benchmark",
            eyebrow="Peer comparison",
            icon="leaderboard",
            meta="Composite score (0–100), master users only",
        )
        with st.expander("How is the benchmark score calculated?", expanded=False):
            st.markdown(
                "Each country is scored 0–100 on four equally-weighted pillars, "
                "then ranked:\n\n"
                "- **Collection efficiency** — paid ÷ billed (%).\n"
                "- **NRW score** — `100 − NRW%`, so lower losses score higher.\n"
                "- **Service continuity** — average supply hours ÷ 24 × 100.\n"
                "- **Water access** — population safely-managed (%) in the latest year.\n\n"
                "The **overall score** is the average of the four. Restricted to "
                "master users because it exposes cross-country data."
            )
        try:
            from components.benchmarking import render_benchmarking_radar
            render_benchmarking_radar()
        except Exception as e:
            st.info(f"Benchmarking unavailable: {e}")

    # --- Board Brief Generation ---
    render_section_header(
        "Board brief generator",
        eyebrow="Executive reporting",
        icon="auto_stories",
        meta="AI-assisted summary",
    )

    # BYOK annotation — this is an AI-assisted feature. With a key it writes a
    # tailored brief; without one it falls back to a standard template.
    _byok_ready = is_llm_configured()
    if _byok_ready:
        st.caption(
            ":material/check_circle: AI key detected — your request below shapes a tailored, AI-written brief. "
            "Manage keys in MajiBot settings."
        )
    else:
        st.caption(
            ":material/info: No AI key configured — you'll get a standard template. Add your own API key (BYOK) "
            "in MajiBot settings to generate a customised, AI-written brief."
        )

    # Determine period label
    if selected_month and selected_month != "All":
        period = f"{selected_month} {selected_year}"
    elif selected_year and selected_year != "All":
        period = f"Year {selected_year}"
    else:
        period = "Current Period"

    col_opts1, col_opts2 = st.columns([1, 1])
    with col_opts1:
        report_period = st.text_input("Report period", value=period, key="report_period_input")
    with col_opts2:
        report_format = st.selectbox("Format", ["Markdown", "Plain Text"], key="report_format")
    custom_request = st.text_area(
        "Customise your request (optional)",
        placeholder="e.g. Focus on NRW and collection efficiency in Zone 4; keep it under 200 words; "
                    "flag the top 3 risks for the board.",
        key="brief_custom_request",
        disabled=not _byok_ready,
        help=None if _byok_ready else "Add an API key in MajiBot settings to use custom requests.",
    )
    generate_clicked = st.button("Generate brief", type="primary")

    if generate_clicked:
        with st.spinner("Generating executive brief…"):
            brief_text = None
            if _byok_ready:
                try:
                    brief_text = generate_board_brief_llm(
                        f_billing, f_prod, f_fin, report_period, custom_request, report_format
                    )
                except Exception as e:
                    st.warning(f"AI generation failed ({e}). Falling back to the standard template.")
            if not brief_text:
                try:
                    brief_text = generate_board_brief_text(f_billing, f_prod, f_fin, report_period)
                except Exception as e:
                    st.error(f"Error generating report: {str(e)}")
            if brief_text:
                st.session_state["generated_brief"] = brief_text
                st.session_state["brief_generated"] = True
            else:
                st.session_state["brief_generated"] = False

    if st.session_state.get("brief_generated", False) and st.session_state.get("generated_brief"):
        brief_text = st.session_state["generated_brief"]

        with st.expander("Generated board brief", expanded=True):
            # Escape '$' so Streamlit doesn't render currency pairs as LaTeX math
            # (the old "currency looks italic" bug). Downloads keep the raw text.
            st.markdown(brief_text.replace("$", "\\$"))

        dl_col1, dl_col2, dl_col3 = st.columns([1, 1, 2])
        with dl_col1:
            st.download_button(
                label="Download · Markdown",
                data=brief_text,
                file_name=f"board_brief_{pd.Timestamp.now().strftime('%Y%m%d')}.md",
                mime="text/markdown",
                width="stretch",
            )
        with dl_col2:
            # PDF export
            try:
                from components.pdf_export import generate_pdf_report
                pdf_kpis = {
                    "Collection Efficiency": f"{coll_eff:.1f}%",
                    "NRW": f"{nrw:.1f}%",
                    "Service Hours": f"{service_hours:.1f} hrs/day",
                    "Cost Recovery": f"{opex_cov:.1f}%",
                    "Water Coverage": f"{w_cov:.0f}%",
                    "Sanitation Coverage": f"{s_cov:.0f}%",
                }
                pdf_bytes = generate_pdf_report(
                    title="Water Utility Performance Report",
                    period=report_period,
                    country=selected_country or "All",
                    markdown_content=brief_text,
                    kpis=pdf_kpis,
                )
                st.download_button(
                    label="📕 Download as PDF",
                    data=pdf_bytes,
                    file_name=f"board_brief_{pd.Timestamp.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    width="stretch",
                )
            except Exception:
                plain_text = brief_text.replace("**", "").replace("# ", "").replace("## ", "").replace("### ", "")
                st.download_button(
                    label="📄 Download as Text",
                    data=plain_text,
                    file_name=f"board_brief_{pd.Timestamp.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain",
                    width="stretch",
                )
        with dl_col3:
            if st.button("Regenerate", width="stretch"):
                st.session_state["brief_generated"] = False
                st.rerun()
