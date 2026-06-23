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
    JMP_COLORS,
    STATUS_GOOD,
    STATUS_WARNING,
    STATUS_CRITICAL,
    apply_axis_currency,
    apply_axis_percent,
    style_fig,
    status_label,
)
from data.database import query
from data.metrics import (
    non_revenue_water,
    collection_efficiency,
    cost_coverage,
    population_weighted_mean,
)
from ai_insights import InsightsEngine, generate_board_brief_text

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
        render_target_bar,
        render_risk_card,
        render_action_checklist,
    )
    from ai_insights import TARGETS

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

    # --- B. Overnight delta band ------------------------------------------
    # Compare latest 30-day window vs prior 30-day window per pillar.
    def _window_score(df, value_col, date_col="date", days=30):
        if df is None or df.empty or date_col not in df.columns or value_col not in df.columns:
            return None, None
        try:
            d = df.copy()
            d[date_col] = pd.to_datetime(d[date_col], errors="coerce")
            d = d.dropna(subset=[date_col])
            if d.empty:
                return None, None
            latest = d[date_col].max()
            cur = d[(d[date_col] > latest - pd.Timedelta(days=days)) & (d[date_col] <= latest)][value_col].mean()
            prev = d[(d[date_col] > latest - pd.Timedelta(days=2 * days)) & (d[date_col] <= latest - pd.Timedelta(days=days))][value_col].mean()
            return (float(cur) if pd.notna(cur) else None,
                    float(prev) if pd.notna(prev) else None)
        except Exception:
            return None, None

    cur_paid, prev_paid       = _window_score(f_billing, "paid")
    cur_billed, prev_billed   = _window_score(f_billing, "billed")
    cur_prod, prev_prod       = _window_score(f_prod, "production_m3")
    cur_svc, prev_svc         = _window_score(f_prod, "service_hours")

    def _delta_card(label: str, current: float, prev: float, unit: str = "", fmt: str = "{:.1f}"):
        if current is None:
            value_str = "—"
            change_html = '<span class="delta-card__change delta-card__change--flat">No data</span>'
        else:
            value_str = fmt.format(current) + unit
            if prev is None or prev == 0:
                change_html = '<span class="delta-card__change delta-card__change--flat">— vs prior</span>'
            else:
                pct_change = (current - prev) / abs(prev) * 100
                cls = "up" if pct_change > 0.5 else "down" if pct_change < -0.5 else "flat"
                arrow = "▲" if cls == "up" else "▼" if cls == "down" else "•"
                change_html = (
                    f'<span class="delta-card__change delta-card__change--{cls}">'
                    f'{arrow} {pct_change:+.1f}% vs prior 30d'
                    f'</span>'
                )
        return (
            f'<div class="delta-card">'
            f'<div class="delta-card__label">{label}</div>'
            f'<div class="delta-card__value">{value_str}</div>'
            f'{change_html}'
            f'</div>'
        )

    delta_html_parts = [
        '<div class="delta-band">',
        _delta_card("Avg daily payments", cur_paid, prev_paid, " $", fmt="{:,.0f}"),
        _delta_card("Avg daily billings", cur_billed, prev_billed, " $", fmt="{:,.0f}"),
        _delta_card("Avg daily production", cur_prod, prev_prod, " m³", fmt="{:,.0f}"),
        _delta_card("Avg service hours", cur_svc, prev_svc, " hrs"),
        '</div>',
    ]
    st.markdown("".join(delta_html_parts), unsafe_allow_html=True)

    # --- C. Top risks / wins + today's actions ----------------------------
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

    rwc1, rwc2 = st.columns(2)
    with rwc1:
        render_risk_card("Top risks", risk_items[:3], tone="warn")
    with rwc2:
        render_risk_card("Top wins", win_items[:3], tone="good")

    # Today's actions — generated from threshold breaches with page deep-links.
    action_items: List[Dict[str, str]] = []
    if nrw > 30:
        action_items.append({
            "text": f"Investigate NRW spike ({nrw:.1f}%) — drill into worst-performing zone.",
            "page": "pages/2_Access_&_Coverage.py", "label": "Open Access page",
        })
    if coll_eff < 85:
        action_items.append({
            "text": f"Collection efficiency below target — {coll_eff:.1f}% vs 85% goal. Review aged debt.",
            "page": "pages/4_Financial_Health.py", "label": "Open Financial Health",
        })
    if service_hours and service_hours < 18:
        action_items.append({
            "text": f"Service continuity at {service_hours:.1f} hrs/day — below 18-hour target.",
            "page": "pages/3_Service_Quality.py", "label": "Open Service & Quality",
        })
    if not action_items:
        action_items.append({
            "text": "No threshold breaches detected — continue routine monitoring.",
            "page": "pages/7_Forecasting.py", "label": "Check forecasts",
        })
    render_action_checklist("Today's actions", action_items[:4])

    # --- E. Cross-cutting targets bar -------------------------------------
    render_section_header("Cross-cutting targets", eyebrow="Actuals vs goalposts", icon="adjust")
    tcol1, tcol2, tcol3, tcol4 = st.columns(4)
    with tcol1:
        render_target_bar("Non-revenue water", nrw, TARGETS["nrw"]["value"],
                          unit="%", direction="lower_is_better", icon=TARGETS["nrw"]["icon"])
    with tcol2:
        render_target_bar("Collection efficiency", coll_eff, TARGETS["collection_efficiency"]["value"],
                          unit="%", direction="higher_is_better", icon=TARGETS["collection_efficiency"]["icon"])
    with tcol3:
        render_target_bar("Service continuity", service_hours or 0.0, TARGETS["service_hours"]["value"],
                          unit="h", direction="higher_is_better", icon=TARGETS["service_hours"]["icon"])
    with tcol4:
        render_target_bar("Service coverage", coverage_score, TARGETS["coverage"]["value"],
                          unit="%", direction="higher_is_better", icon=TARGETS["coverage"]["icon"])

    # --- G. AI summary (collapsed) ----------------------------------------
    try:
        from ai_insights import generate_quick_insight
        quick_insight = generate_quick_insight(f_billing, f_prod, f_fin, selected_country)
        if quick_insight:
            with st.expander("MajiBot's read on today", expanded=False):
                st.markdown(quick_insight)
    except Exception:
        pass

    # ---- Pillar quick-look (legacy KPI row preserved) --------------------
    render_section_header("Pillar quick-look", eyebrow="Snapshot", icon="speed")

    cov_kind = _delta_kind_for_status(cov_status)
    fin_kind = _delta_kind_for_status(fin_status)
    eff_status = status_label(eff_score, good=80, warning=60, higher_is_better=True)
    qual_status = status_label(qual_score, good=80, warning=60, higher_is_better=True)

    # Build short historical sparkline series from filtered billing/production
    # (best-effort — empty/short series simply render no sparkline)
    def _last_n(series, n=12):
        s = series.dropna().tail(n).tolist() if hasattr(series, "dropna") else []
        return [float(x) for x in s if isinstance(x, (int, float))]

    cov_spark = []
    if not f_nat.empty and "water_access" in f_nat.columns:
        cov_spark = _last_n(f_nat.sort_values("year")["water_access"]) if "year" in f_nat.columns else _last_n(f_nat["water_access"])
    eff_spark = _last_n(f_prod.sort_values("date_dt").groupby(f_prod["date_dt"].dt.to_period("M"))["production_m3"].sum()) if not f_prod.empty and "date_dt" in f_prod.columns else []
    fin_spark = _last_n(f_billing.sort_values("date_dt").groupby(f_billing["date_dt"].dt.to_period("M"))["paid"].sum()) if not f_billing.empty and "date_dt" in f_billing.columns else []
    qual_spark = _last_n(svc_df["water_quality_rate"]) if not svc_df.empty and "water_quality_rate" in svc_df.columns else []

    render_kpi_row([
        KPI(
            label="Service coverage",
            value=f"{coverage_score:.0f}%",
            delta=f"Water {w_cov:.0f}% · San {s_cov:.0f}%",
            delta_kind=cov_kind,
            footnote=f"{pop_served:.1f}M people served",
            icon="diversity_3",
            sparkline=cov_spark,
        ),
        KPI(
            label="Financial health",
            value=f"{fin_score:.0f}",
            delta=fin_status,
            delta_kind=fin_kind,
            footnote=f"Revenue ${total_revenue / 1e6:.1f}M · Cost recovery {opex_cov:.0f}%",
            icon="payments",
            sparkline=fin_spark,
        ),
        KPI(
            label="Operational efficiency",
            value=f"{eff_score:.0f}",
            delta=f"NRW {nrw:.1f}% · Continuity {service_hours:.1f}h",
            delta_kind=_STATUS_DELTA_KIND[eff_status],
            footnote=f"Capacity utilisation {cap_util:.0f}%",
            icon="bolt",
            sparkline=eff_spark,
        ),
        KPI(
            label="Service quality",
            value=f"{qual_score:.0f}",
            delta=f"Water qual {wq_compliance:.0f}% · Resolution {cust_res_rate:.0f}%",
            delta_kind=_STATUS_DELTA_KIND[qual_status],
            footnote="Index of compliance, resolution & asset health",
            icon="verified",
            sparkline=qual_spark,
        ),
    ])

    # Quick deep-link strip
    nav_c1, nav_c2, nav_c3, nav_c4 = st.columns(4)
    with nav_c1:
        st.page_link("pages/2_Access_&_Coverage.py", label="Access & Coverage", icon=":material/arrow_forward:", width="stretch")
    with nav_c2:
        st.page_link("pages/4_Financial_Health.py", label="Financial Health", icon=":material/arrow_forward:", width="stretch")
    with nav_c3:
        st.page_link("pages/5_Production.py", label="Production", icon=":material/arrow_forward:", width="stretch")
    with nav_c4:
        st.page_link("pages/3_Service_Quality.py", label="Service & Quality", icon=":material/arrow_forward:", width="stretch")

    # --- Performance Trends Dashboard ---
    render_section_header("Performance trends", eyebrow="Last 12 months", icon="show_chart")
    
    # Prepare Trend Data (Global for tabs)
    trend_billing = billing_df.copy()
    trend_fin = fin_df.copy()
    trend_prod = prod_df.copy()
    trend_svc = service_data_dict["full_data"].copy()
    trend_water_acc = access_data["water_full"].copy()

    if selected_country and selected_country != "All":
        # Case-insensitive country filtering
        trend_billing = trend_billing[trend_billing["country"].str.lower() == selected_country.lower()]
        trend_fin = trend_fin[trend_fin["country"].str.lower() == selected_country.lower()]
        trend_prod = trend_prod[trend_prod["country"].str.lower() == selected_country.lower()]
        trend_svc = trend_svc[trend_svc["country"].str.lower() == selected_country.lower()]
        trend_water_acc = trend_water_acc[trend_water_acc["country"].str.lower() == selected_country.lower()]
        
    if selected_zone and selected_zone != "All":
        # Case-insensitive zone filtering
        if "zone" in trend_billing.columns: trend_billing = trend_billing[trend_billing["zone"].str.lower() == selected_zone.lower()]
        if "zone" in trend_prod.columns: trend_prod = trend_prod[trend_prod["zone"].str.lower() == selected_zone.lower()]
        if "zone" in trend_svc.columns: trend_svc = trend_svc[trend_svc["zone"].str.lower() == selected_zone.lower()]
        if "zone" in trend_water_acc.columns: trend_water_acc = trend_water_acc[trend_water_acc["zone"].str.lower() == selected_zone.lower()]

    tab_fin, tab_ops, tab_cov, tab_qual, tab_map, tab_bench = st.tabs([
        "Financial", "Operational", "Coverage", "Quality", "Geographic", "Benchmarking"
    ])

    # --- Financial Tab ---
    with tab_fin:
        # Group by Month
        fin_monthly = trend_fin.groupby(pd.Grouper(key="date", freq="ME")).agg({"opex": "sum", "sewer_revenue": "sum"}).reset_index()
        billing_monthly = trend_billing.groupby(pd.Grouper(key="date", freq="ME")).agg({"billed": "sum", "paid": "sum"}).reset_index()
        
        merged_fin = pd.merge(fin_monthly, billing_monthly, on="date", how="outer").fillna(0)
        merged_fin["total_revenue"] = merged_fin["paid"] + merged_fin["sewer_revenue"]
        
        # Ensure safe division for collection efficiency
        merged_fin["coll_eff"] = (merged_fin["paid"] / merged_fin["billed"].replace(0, 1) * 100).fillna(0)
        
        # Calculate Cost Recovery Ratio (Revenue / Opex * 100) - more meaningful for utilities
        # Shows what % of operating costs are covered by revenue
        merged_fin["cost_recovery"] = (merged_fin["total_revenue"] / merged_fin["opex"].replace(0, 1) * 100).fillna(0)
        
        # Clamp values to realistic ranges
        merged_fin["coll_eff"] = merged_fin["coll_eff"].clip(0, 150)  # Allow slight over-collection
        merged_fin["cost_recovery"] = merged_fin["cost_recovery"].clip(0, 200)  # Cap at 200% cost recovery
        
        # Sort and take last 12 months for "rolling view"
        merged_fin = merged_fin.sort_values("date").tail(12)
        
        if len(merged_fin) > 0:
            fig_fin = go.Figure()
            fig_fin.add_trace(go.Bar(x=merged_fin["date"], y=merged_fin["total_revenue"], name="Revenue", marker_color=STATUS_GOOD, opacity=0.85))
            fig_fin.add_trace(go.Bar(x=merged_fin["date"], y=merged_fin["opex"], name="Opex", marker_color=STATUS_CRITICAL, opacity=0.85))
            fig_fin.add_trace(go.Scatter(x=merged_fin["date"], y=merged_fin["coll_eff"], name="Collection efficiency %", yaxis="y2", line=dict(color=DATA_WATER, width=2.5)))
            fig_fin.add_trace(go.Scatter(x=merged_fin["date"], y=merged_fin["cost_recovery"], name="Cost recovery %", yaxis="y2", line=dict(color=STATUS_WARNING, width=2.5, dash="dot")))

            style_fig(fig_fin, height=380, legend_top=True)
            fig_fin.update_layout(
                yaxis=dict(title="Amount ($)"),
                yaxis2=dict(title="Percent", overlaying="y", side="right", range=[0, 150], showgrid=False),
                barmode='group',
            )
            apply_axis_currency(fig_fin, axis="y")
            with chart_card("Financial performance", meta="Revenue · Opex · Collection · Cost recovery"):
                st.plotly_chart(fig_fin, use_container_width=True)
        else:
            st.info("No financial data available for selected period")

    # --- Operational Tab ---
    with tab_ops:
        prod_monthly = trend_prod.groupby(pd.Grouper(key="date", freq="ME")).agg({"production_m3": "sum"}).reset_index()
        billing_monthly_cons = trend_billing.groupby(pd.Grouper(key="date", freq="ME")).agg({"consumption_m3": "sum"}).reset_index()
        
        merged_ops = pd.merge(prod_monthly, billing_monthly_cons, on="date", how="inner")
        merged_ops["nrw_pct"] = ((merged_ops["production_m3"] - merged_ops["consumption_m3"]) / merged_ops["production_m3"] * 100).fillna(0)
        
        svc_monthly = trend_svc.groupby(pd.Grouper(key="date", freq="ME")).agg({"ww_treated": "sum", "ww_capacity": "sum"}).reset_index()
        svc_monthly["cap_util"] = (svc_monthly["ww_treated"] / svc_monthly["ww_capacity"] * 100).fillna(0)
        
        merged_ops = pd.merge(merged_ops, svc_monthly[["date", "cap_util"]], on="date", how="left").fillna(0)
        merged_ops = merged_ops.sort_values("date").tail(12)
        
        fig_ops = go.Figure()
        fig_ops.add_trace(go.Scatter(x=merged_ops["date"], y=merged_ops["nrw_pct"], name="NRW %", line=dict(color=STATUS_CRITICAL, width=2.5)))
        fig_ops.add_trace(go.Scatter(x=merged_ops["date"], y=merged_ops["cap_util"], name="Capacity util %", line=dict(color=DATA_WATER, width=2.5)))
        fig_ops.add_trace(go.Scatter(x=merged_ops["date"], y=merged_ops["production_m3"], name="Production m³", yaxis="y2", line=dict(color=STATUS_GOOD, dash="dot")))
        fig_ops.add_trace(go.Scatter(x=merged_ops["date"], y=merged_ops["consumption_m3"], name="Consumption m³", yaxis="y2", line=dict(color=DATA_SANITATION, dash="dot")))

        style_fig(fig_ops, height=380, legend_top=True)
        fig_ops.update_layout(
            yaxis=dict(title="Percent"),
            yaxis2=dict(title="Volume (m³)", overlaying="y", side="right", showgrid=False),
        )
        apply_axis_percent(fig_ops, axis="y")

        if len(merged_ops) > 1:
            start_nrw = merged_ops["nrw_pct"].iloc[0]
            end_nrw = merged_ops["nrw_pct"].iloc[-1]
            if end_nrw < start_nrw:
                fig_ops.add_annotation(
                    x=merged_ops["date"].iloc[-1], y=end_nrw,
                    text="Efficiency improved", showarrow=True, arrowhead=1,
                    font=dict(color=STATUS_GOOD, size=11),
                )

        with chart_card("Operational efficiency", meta="NRW, capacity utilisation, volume"):
            st.plotly_chart(fig_ops, use_container_width=True)

    # --- Coverage Tab ---
    with tab_cov:
        # --- Water Access Chart ---
        w_cols = ["w_safely_managed_pct", "w_basic_pct", "w_limited_pct", "w_unimproved_pct", "surface_water_pct"]
        for c in w_cols:
            if c in trend_water_acc.columns:
                trend_water_acc[c] = pd.to_numeric(trend_water_acc[c], errors="coerce").fillna(0)
        
        if "popn_total" in trend_water_acc.columns:
            # Calculate absolute pops per row
            for c in w_cols:
                if c in trend_water_acc.columns:
                    level_name = c.replace("_pct", "")
                    trend_water_acc[level_name] = trend_water_acc["popn_total"] * (trend_water_acc[c] / 100)
            
            level_cols = [c.replace("_pct", "") for c in w_cols if c in trend_water_acc.columns]
            w_trend = trend_water_acc.groupby("year")[level_cols].sum().reset_index()
            
            if len(w_trend) > 0:
                fig_cov = go.Figure()
                stack_group = 'one'
                # Order matches JMP hierarchy: Safe -> Basic -> Limited -> Unimproved -> Surface
                order = ["w_safely_managed", "w_basic", "w_limited", "w_unimproved", "surface_water"]
                # JMP color mapping
                colors = [JMP_COLORS["safely_managed"], JMP_COLORS["basic"], JMP_COLORS["limited"], 
                         JMP_COLORS["unimproved"], JMP_COLORS["surface_water"]]
                labels = ["Safely Managed", "Basic", "Limited", "Unimproved", "Surface Water"]
                
                for i, level in enumerate(order):
                    if level in w_trend.columns:
                        fig_cov.add_trace(go.Scatter(
                            x=w_trend["year"].apply(lambda y: format_year_month(int(y))), 
                            y=w_trend[level], 
                            name=labels[i], 
                            stackgroup=stack_group,
                            mode='lines',
                            line=dict(width=0.5, color=colors[i]),
                            fillcolor=colors[i],
                            hovertemplate='%{customdata}<br>Population: %{y:,.0f}<extra></extra>',
                            customdata=[labels[i]] * len(w_trend)
                        ))
                
                style_fig(fig_cov, height=340)
                fig_cov.update_layout(yaxis=dict(title="Population"), xaxis=dict(title="Year"))
                with chart_card("Water access ladder", meta="Population by service level"):
                    st.plotly_chart(fig_cov, use_container_width=True)
            else:
                st.warning("No water coverage data available for selected period")
        else:
            st.warning("Population data not available for water coverage trends.")
        
        # --- Sanitation Access Chart ---
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
            # Calculate absolute pops per row for sanitation
            for c in s_cols:
                if c in trend_san_acc.columns:
                    level_name = c.replace("_pct", "")
                    trend_san_acc[level_name] = trend_san_acc["popn_total"] * (trend_san_acc[c] / 100)
            
            s_level_cols = [c.replace("_pct", "") for c in s_cols if c in trend_san_acc.columns]
            s_trend = trend_san_acc.groupby("year")[s_level_cols].sum().reset_index()
            
            if len(s_trend) > 0:
                fig_san = go.Figure()
                # Order matches JMP hierarchy: Safely Managed -> Basic -> Limited -> Unimproved -> Open Defecation
                s_order = ["s_safely_managed", "s_basic", "s_limited", "s_unimproved", "open_def"]
                # Sanitation color scheme (matching access page)
                san_colors = ['#349438', '#49B754', '#FDEE79', '#FFD94F', '#FFB02B']
                s_labels = ["Safely Managed", "Basic", "Limited", "Unimproved", "Open Defecation"]
                
                for i, level in enumerate(s_order):
                    if level in s_trend.columns:
                        fig_san.add_trace(go.Scatter(
                            x=s_trend["year"].apply(lambda y: format_year_month(int(y))), 
                            y=s_trend[level], 
                            name=s_labels[i], 
                            stackgroup='san',
                            mode='lines',
                            line=dict(width=0.5, color=san_colors[i]),
                            fillcolor=san_colors[i],
                            hovertemplate='%{customdata}<br>Population: %{y:,.0f}<extra></extra>',
                            customdata=[s_labels[i]] * len(s_trend)
                        ))
                
                style_fig(fig_san, height=340)
                fig_san.update_layout(yaxis=dict(title="Population"), xaxis=dict(title="Year"))
                with chart_card("Sanitation access ladder", meta="Population by service level"):
                    st.plotly_chart(fig_san, use_container_width=True)
            else:
                st.warning("No sanitation coverage data available for selected period")
        else:
            st.warning("Population data not available for sanitation coverage trends.")

    # --- Quality Tab ---
    with tab_qual:
        svc_qual = trend_svc.groupby(pd.Grouper(key="date", freq="ME")).agg({
            "water_quality_rate": "mean",
            "complaint_resolution_rate": "mean"
        }).reset_index()
        
        prod_svc = trend_prod.groupby(pd.Grouper(key="date", freq="ME")).agg({"service_hours": "mean"}).reset_index()
        
        merged_qual = pd.merge(svc_qual, prod_svc, on="date", how="outer").sort_values("date").tail(12)
        
        if len(merged_qual) > 0:
            # Calculate dynamic y-axis range for percentage metrics
            qual_data = merged_qual[["water_quality_rate", "complaint_resolution_rate"]].dropna()
            if not qual_data.empty:
                min_qual = max(0, qual_data.min().min() - 5)  # 5% padding
                max_qual = min(100, qual_data.max().max() + 5)  # 5% padding
            else:
                min_qual, max_qual = 0, 100
            
            fig_qual = go.Figure()
            fig_qual.add_trace(go.Scatter(x=merged_qual["date"], y=merged_qual["water_quality_rate"], name="Water quality %", line=dict(color=STATUS_GOOD, width=2.5), mode='lines+markers'))
            fig_qual.add_trace(go.Scatter(x=merged_qual["date"], y=merged_qual["complaint_resolution_rate"], name="Resolution rate %", line=dict(color=DATA_WATER, width=2.5), mode='lines+markers'))
            fig_qual.add_trace(go.Scatter(x=merged_qual["date"], y=merged_qual["service_hours"], name="Service hours", yaxis="y2", line=dict(color=STATUS_WARNING, width=2.5, dash="dot"), mode='lines+markers'))

            style_fig(fig_qual, height=380, legend_top=True)
            fig_qual.update_layout(
                yaxis=dict(title="Percent", range=[min_qual, max_qual]),
                yaxis2=dict(title="Hours / day", overlaying="y", side="right", range=[0, 24], showgrid=False),
            )
            with chart_card("Service quality trends", meta="Quality compliance, resolution rate, continuity"):
                st.plotly_chart(fig_qual, use_container_width=True)
        else:
            st.info("No service quality data available for selected period")

    # --- Geographic Map Tab ---
    with tab_map:
        try:
            from components.geo_map import render_map_selector_and_chart
            render_map_selector_and_chart(country_filter=selected_country)
        except Exception as e:
            st.info(f"Geographic visualization unavailable: {e}")

    # --- Benchmarking Tab ---
    with tab_bench:
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

    # Determine period label
    if selected_month and selected_month != "All":
        period = f"{selected_month} {selected_year}"
    elif selected_year and selected_year != "All":
        period = f"Year {selected_year}"
    else:
        period = "Current Period"

    col_opts1, col_opts2, col_opts3 = st.columns([2, 2, 1])
    with col_opts1:
        report_period = st.text_input("Report period", value=period, key="report_period_input")
    with col_opts2:
        report_format = st.selectbox("Format", ["Markdown", "Plain Text"], key="report_format")
    with col_opts3:
        st.write("")
        generate_clicked = st.button("Generate", type="primary", width="stretch")

    if generate_clicked:
        with st.spinner("Generating executive brief…"):
            try:
                brief_text = generate_board_brief_text(f_billing, f_prod, f_fin, report_period)
                st.session_state["generated_brief"] = brief_text
                st.session_state["brief_generated"] = True
            except Exception as e:
                st.error(f"Error generating report: {str(e)}")
                st.session_state["brief_generated"] = False

    if st.session_state.get("brief_generated", False) and st.session_state.get("generated_brief"):
        brief_text = st.session_state["generated_brief"]

        with st.expander("Generated board brief", expanded=True):
            st.markdown(brief_text)

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
