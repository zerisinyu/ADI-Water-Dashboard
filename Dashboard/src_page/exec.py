import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from utils import (
    load_json, 
    conic_css as _conic_css, 
    download_button as _download_button, 
    scene_page_path as _scene_page_path, 
    DATA_DIR, 
    prepare_access_data, 
    prepare_service_data,
    filter_df_by_user_access,
    validate_selected_country
)
from ai_insights import InsightsEngine, generate_board_brief_text

# ============================================================================
# CONSTANTS & UTILITIES
# ============================================================================

# JMP Color Coding Standards (Joint Monitoring Programme)
# Colors aligned with Access & Coverage page for consistency
JMP_COLORS = {
    "safely_managed": "#088BCE",      # Blue (Water) / Green (Sanitation)
    "basic": "#48BFE7",               # Light Blue (Water) / Light Green (Sanitation)
    "limited": "#FDEE79",             # Yellow
    "unimproved": "#FFD94F",          # Orange
    "surface_water": "#FFB02B"        # Dark Orange
}

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
    Load raw dashboard data (internal, cached).
    This loads all data without access filtering.
    """
    # 1. Load Billing Data (for Collection Efficiency & NRW consumption)
    billing_path = DATA_DIR / "billing.csv"
    if billing_path.exists():
        billing_cols = ["date", "consumption_m3", "billed", "paid", "country", "zone", "source"]
        billing_df = pd.read_csv(billing_path, usecols=billing_cols, low_memory=False)
        billing_df["date"] = pd.to_datetime(billing_df["date"], errors="coerce")
        for col in ["consumption_m3", "billed", "paid"]:
            billing_df[col] = pd.to_numeric(billing_df[col], errors="coerce")
        billing_df = billing_df.dropna(subset=["date"])
    else:
        billing_df = pd.DataFrame(columns=["date", "consumption_m3", "billed", "paid", "country", "zone", "source"])

    # 2. Load Financial Services Data
    fin_path = DATA_DIR / "all_fin_service.csv"
    if fin_path.exists():
        fin_df = pd.read_csv(fin_path)
        fin_df["date"] = pd.to_datetime(fin_df["date_MMYY"], format="%b/%y")
    else:
        fin_df = pd.DataFrame(columns=["country", "city", "date", "sewer_revenue", "opex", "complaints", "resolved"])

    # 3. Load Production Data
    prod_path = DATA_DIR / "production.csv"
    if prod_path.exists():
        prod_df = pd.read_csv(prod_path)
        prod_df["date"] = pd.to_datetime(prod_df["date_YYMMDD"])
        if not billing_df.empty:
            source_map = billing_df[["source", "zone", "country"]].drop_duplicates().dropna()
            prod_df = prod_df.merge(source_map, on=["source", "country"], how="left")
            prod_df["zone"] = prod_df["zone"].fillna("Unknown")
    else:
        prod_df = pd.DataFrame(columns=["date", "production_m3", "service_hours", "country", "zone"])

    # 4. Load National Data
    nat_path = DATA_DIR / "all_nationalacc.csv"
    if nat_path.exists():
        nat_df = pd.read_csv(nat_path)
    else:
        nat_df = pd.DataFrame()

    return billing_df, fin_df, prod_df, nat_df


def load_dashboard_data():
    """
    Load and prepare data for the executive dashboard.
    Data is automatically filtered based on user access permissions.
    
    Note: Access filtering is applied AFTER caching to ensure proper user isolation.
    """
    # Load raw cached data
    billing_df, fin_df, prod_df, nat_df = _load_raw_dashboard_data()
    
    # Apply access control filtering (this happens on each call)
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
             filtered = filtered[filtered["year"] == int(year)]
        elif "date_YY" in filtered.columns: # for national data
             filtered = filtered[filtered["date_YY"] == int(year)]
        
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

def _render_gauge_card(title, value, sub_metrics, color_class, link_target, link_text):
    colors = {
        "status-good": "#10b981",
        "status-warning": "#f59e0b",
        "status-critical": "#ef4444"
    }
    gauge_color = colors.get(color_class, "#3b82f6")
    
    st.markdown(f"""<div class="metric-card">
    <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom:10px;">
        <div style="font-size:14px; font-weight:600; color:#64748b;">{title}</div>
        <div style="background:{gauge_color}20; color:{gauge_color}; padding:4px 10px; border-radius:12px; font-size:11px; font-weight:600;">{value}%</div>
    </div>
    <div style="display:flex; justify-content:center; margin-bottom:12px;">
        <div style="
            width: 100px; height: 100px; border-radius: 50%;
            background: radial-gradient(closest-side, white 79%, transparent 80% 100%),
            conic-gradient({gauge_color} {value}%, #e2e8f0 0);
            display: flex; align-items: center; justify-content: center;
        ">
            <span style="font-weight:700; color:{gauge_color}; font-size: 24px;">{value}%</span>
        </div>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:12px;">
        {''.join([f'<div style="background:#f8fafc; padding:6px; border-radius:6px; text-align:center;"><div style="font-size:11px; color:#64748b;">{k}</div><div style="font-size:13px; font-weight:600; color:#334155;">{v}</div></div>' for k,v in sub_metrics.items()])}
    </div>
</div>""", unsafe_allow_html=True)
    if link_target:
        st.page_link(link_target, label=link_text, icon="👉", use_container_width=True)

def _render_trend_card(title, score, status, sub_metrics, link_target, link_text):
    color = "#10b981" if status == "Healthy" else "#f59e0b" if status == "At Risk" else "#ef4444"
    st.markdown(f"""<div class="metric-card">
    <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom:16px;">
        <div style="font-size:14px; font-weight:600; color:#64748b;">{title}</div>
        <div style="background:{color}20; color:{color}; padding:4px 10px; border-radius:12px; font-size:11px; font-weight:600;">{status}</div>
    </div>
    <div style="margin-bottom:16px;">
        <div style="font-size:32px; font-weight:700; color:#0f172a; line-height:1;">{score}</div>
        <div style="font-size:12px; color:#64748b; margin-top:4px;">Index Score</div>
    </div>
    <div style="height:4px; background:#e2e8f0; border-radius:2px; margin-bottom:16px; overflow:hidden;">
        <div style="width:{score}%; height:100%; background:{color}; border-radius:2px;"></div>
    </div>
    <div style="display:flex; flex-direction:column; gap:8px; margin-bottom:12px;">
        {''.join([f'<div style="display:flex; justify-content:space-between; font-size:13px;"><span style="color:#64748b;">{k}</span><span style="font-weight:600; color:#334155;">{v}</span></div>' for k,v in sub_metrics.items()])}
    </div>
</div>""", unsafe_allow_html=True)
    if link_target:
        st.page_link(link_target, label=link_text, icon="👉", use_container_width=True)

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
    # Water Coverage (Municipal Coverage)
    # Use water_safely_pct as a safer proxy if municipal_coverage is population count
    w_cov = w_latest["water_safely_pct"].mean() if not w_latest.empty else 0
    # Sanitation Coverage (Safely Managed Pct as proxy for coverage quality or use sewer connections if available)
    # Using s_safely_managed_pct from access data
    s_cov = s_latest["sewer_safely_pct"].mean() if not s_latest.empty else 0
    
    coverage_score = (w_cov + s_cov) / 2
    pop_served = (w_latest["popn_total"].sum() / 1_000_000) if not w_latest.empty else 0
    
    cov_status = "status-good" if coverage_score > 80 else "status-warning" if coverage_score > 60 else "status-critical"

    # Card 2: Financial Health Index
    total_billed = f_billing["billed"].sum()
    total_paid = f_billing["paid"].sum()
    coll_eff = (total_paid / total_billed * 100) if total_billed > 0 else 0
    
    total_sewer_rev = f_fin["sewer_revenue"].sum()
    total_revenue = total_paid + total_sewer_rev
    total_opex = f_fin["opex"].sum()
    opex_cov = (total_revenue / total_opex * 100) if total_opex > 0 else 0
    
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
    nrw = ((total_prod - total_cons) / total_prod * 100) if total_prod > 0 else 0
    
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

    # CSS Styling for Scorecards (matching other pages)
    st.markdown("""
<style>
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 16px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        height: 100%;
        min-height: 340px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .metric-label {
        font-size: 12px;
        font-weight: 600;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }
    .metric-value {
        font-size: 28px;
        font-weight: 700;
        color: #111827;
        line-height: 1.2;
    }
    .metric-delta {
        font-size: 12px;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 4px;
        margin-top: 8px;
    }
    .delta-up { color: #059669; }
    .delta-down { color: #dc2626; }
    .delta-neutral { color: #6b7280; }
    .pulse-banner {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 24px;
        border-radius: 12px;
        margin-bottom: 24px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .pulse-score {
        font-size: 48px;
        font-weight: 800;
        display: inline-block;
        margin-right: 16px;
    }
    .pulse-text {
        font-size: 16px;
        line-height: 1.6;
        opacity: 0.95;
    }
    .anomaly-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 12px;
        font-weight: 600;
        margin-right: 8px;
        margin-top: 8px;
    }
    .badge-critical { background: #fca5a5; color: #7f1d1d; }
    .badge-warning { background: #fcd34d; color: #78350f; }
</style>
""", unsafe_allow_html=True)

    # Alert Banner - Status check only
    if nrw > 40:
        st.markdown(f"<div class='panel bad'>⚠️ Critical Alert: NRW is high ({nrw:.1f}%) in selected region. Immediate action required.</div>", unsafe_allow_html=True)
    elif service_hours < 12:
        st.markdown(f"<div class='panel warn'>⚠️ Warning: Service hours dropped to {service_hours:.1f} hrs/day.</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='panel ok'>✅ Systems Operational. All key metrics within acceptable range.</div>", unsafe_allow_html=True)

    # Scorecards Row
    st.markdown("### Key Performance Indicators")
    
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        _render_gauge_card(
            "Service Coverage", 
            int(coverage_score), 
            {"Water": f"{w_cov:.0f}%", "Sanitation": f"{s_cov:.0f}%", "Pop Served": f"{pop_served:.1f}M"},
            cov_status,
            "pages/2_🗺️_Access_&_Coverage.py",
            "Access & Coverage"
        )
        
    with c2:
        _render_trend_card(
            "Financial Health",
            int(fin_score),
            fin_status,
            {"Revenue": f"${total_revenue/1e6:.1f}M", "Op Margin": f"{opex_cov:.0f}%"},
            "pages/4_💹_Financial_Health.py",
            "Financial Health"
        )
        
    with c3:
        # Operational Efficiency - Radial Progress
        st.markdown(f"""<div class="metric-card">
    <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom:10px;">
        <div style="font-size:14px; font-weight:600; color:#64748b;">Operational Eff.</div>
        <div style="font-size:24px; font-weight:700; color:#0f172a;">{int(eff_score)}</div>
    </div>
    <div style="display:flex; justify-content:center; margin-bottom:12px;">
        <div style="
            width: 80px; height: 80px; border-radius: 50%;
            background: radial-gradient(closest-side, white 79%, transparent 80% 100%),
            conic-gradient(#3b82f6 {eff_score}%, #e2e8f0 0);
            display: flex; align-items: center; justify-content: center;
        ">
            <span style="font-weight:700; color:#3b82f6;">{int(eff_score)}%</span>
        </div>
    </div>
    <div style="display:grid; grid-template-columns:1fr; gap:6px; margin-bottom:12px;">
        <div style="display:flex; justify-content:space-between; font-size:12px;"><span style="color:#64748b;">NRW</span><span style="font-weight:600;">{nrw:.1f}%</span></div>
        <div style="display:flex; justify-content:space-between; font-size:12px;"><span style="color:#64748b;">Cap Util</span><span style="font-weight:600;">{cap_util:.0f}%</span></div>
        <div style="display:flex; justify-content:space-between; font-size:12px;"><span style="color:#64748b;">Continuity</span><span style="font-weight:600;">{service_hours:.1f}h</span></div>
    </div>
</div>""", unsafe_allow_html=True)
        st.page_link("pages/5_♻️_Production.py", label="Production", icon="👉", use_container_width=True)

    with c4:
        # Service Quality Index
        st.markdown(f"""<div class="metric-card">
    <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom:16px;">
        <div style="font-size:14px; font-weight:600; color:#64748b;">Service Quality</div>
        <div style="color:#10b981; font-weight:600; font-size:12px;">↗ Trending</div>
    </div>
    <div style="margin-bottom:16px;">
        <div style="font-size:32px; font-weight:700; color:#0f172a; line-height:1;">{qual_score:.1f}</div>
        <div style="font-size:12px; color:#64748b; margin-top:4px;">Quality Index</div>
    </div>
    <div style="display:flex; flex-direction:column; gap:8px; margin-bottom:12px;">
            <div style="display:flex; justify-content:space-between; font-size:13px;">
            <span style="color:#64748b;">Water Qual</span>
            <span style="font-weight:600; color:#334155;">{wq_compliance:.1f}%</span>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:13px;">
            <span style="color:#64748b;">Resolution</span>
            <span style="font-weight:600; color:#334155;">{cust_res_rate:.1f}%</span>
            </div>
    </div>
</div>""", unsafe_allow_html=True)
        st.page_link("pages/3_🛠️_Service_Quality_&_Reliability.py", label="Service & Quality", icon="👉", use_container_width=True)

    # --- Performance Trends Dashboard ---
    st.markdown("### Performance Trends Dashboard")
    
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

    tab_fin, tab_ops, tab_cov, tab_qual = st.tabs(["Financial", "Operational", "Coverage", "Quality"])

    # --- Financial Tab ---
    with tab_fin:
        # Group by Month
        fin_monthly = trend_fin.groupby(pd.Grouper(key="date", freq="ME")).agg({"opex": "sum", "sewer_revenue": "sum"}).reset_index()
        billing_monthly = trend_billing.groupby(pd.Grouper(key="date", freq="ME")).agg({"billed": "sum", "paid": "sum"}).reset_index()
        
        merged_fin = pd.merge(fin_monthly, billing_monthly, on="date", how="outer").fillna(0)
        merged_fin["total_revenue"] = merged_fin["paid"] + merged_fin["sewer_revenue"]
        
        # Ensure safe division for collection efficiency
        merged_fin["coll_eff"] = (merged_fin["paid"] / merged_fin["billed"].replace(0, 1) * 100).fillna(0)
        
        # Calculate op_margin safely (Revenue - Opex) / Revenue * 100
        # Ensure we don't divide by zero
        merged_fin["op_margin"] = ((merged_fin["total_revenue"] - merged_fin["opex"]) / merged_fin["total_revenue"].replace(0, 1) * 100).fillna(0)
        
        # Clamp values to realistic ranges
        merged_fin["coll_eff"] = merged_fin["coll_eff"].clip(0, 150)  # Allow slight over-collection
        merged_fin["op_margin"] = merged_fin["op_margin"].clip(-100, 100)  # Range: -100% to 100%
        
        # Sort and take last 12 months for "rolling view"
        merged_fin = merged_fin.sort_values("date").tail(12)
        
        if len(merged_fin) > 0:
            # Dual Axis Chart
            fig_fin = go.Figure()
            # Bars: Revenue & Costs
            fig_fin.add_trace(go.Bar(x=merged_fin["date"], y=merged_fin["total_revenue"], name="Revenue", marker_color="#10b981", opacity=0.7))
            fig_fin.add_trace(go.Bar(x=merged_fin["date"], y=merged_fin["opex"], name="Opex", marker_color="#ef4444", opacity=0.7))
            
            # Lines: Collection Eff & Op Margin (both metrics on right y-axis as percentages)
            fig_fin.add_trace(go.Scatter(x=merged_fin["date"], y=merged_fin["coll_eff"], name="Collection Eff %", yaxis="y2", line=dict(color="#3b82f6", width=3, dash="solid")))
            fig_fin.add_trace(go.Scatter(x=merged_fin["date"], y=merged_fin["op_margin"], name="Op Margin %", yaxis="y2", line=dict(color="#f59e0b", width=3, dash="dot")))
            
            fig_fin.update_layout(
                title="Financial Performance (Last 12 Months)",
                yaxis=dict(title="Amount ($)", showgrid=True),
                yaxis2=dict(title="Percentage (%)", overlaying="y", side="right", range=[-50, 150], showgrid=False),
                barmode='group',
                legend=dict(orientation="h", y=1.1, x=0),
                height=400,
                hovermode='x unified'
            )
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
        fig_ops.add_trace(go.Scatter(x=merged_ops["date"], y=merged_ops["nrw_pct"], name="NRW %", line=dict(color="#ef4444", width=3)))
        fig_ops.add_trace(go.Scatter(x=merged_ops["date"], y=merged_ops["cap_util"], name="Capacity Util %", line=dict(color="#3b82f6", width=3)))
        fig_ops.add_trace(go.Scatter(x=merged_ops["date"], y=merged_ops["production_m3"], name="Production m3", yaxis="y2", line=dict(color="#10b981", dash="dot")))
        fig_ops.add_trace(go.Scatter(x=merged_ops["date"], y=merged_ops["consumption_m3"], name="Consumption m3", yaxis="y2", line=dict(color="#059669", dash="dot")))
        
        fig_ops.update_layout(
            title="Operational Efficiency Trends",
            yaxis=dict(title="Percentage (%)"),
            yaxis2=dict(title="Volume (m3)", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", y=1.1),
            height=400
        )
        
        if len(merged_ops) > 1:
            start_nrw = merged_ops["nrw_pct"].iloc[0]
            end_nrw = merged_ops["nrw_pct"].iloc[-1]
            if end_nrw < start_nrw:
                fig_ops.add_annotation(x=merged_ops["date"].iloc[-1], y=end_nrw, text="▼ Efficiency Improved", showarrow=True, arrowhead=1)
        
        st.plotly_chart(fig_ops, use_container_width=True)

    # --- Coverage Tab ---
    with tab_cov:
        cols = ["w_safely_managed_pct", "w_basic_pct", "w_limited_pct", "w_unimproved_pct", "surface_water_pct"]
        for c in cols:
            if c in trend_water_acc.columns:
                trend_water_acc[c] = pd.to_numeric(trend_water_acc[c], errors="coerce").fillna(0)
        
        if "popn_total" in trend_water_acc.columns:
            # Calculate absolute pops per row
            for c in cols:
                if c in trend_water_acc.columns:
                    level_name = c.replace("_pct", "")
                    trend_water_acc[level_name] = trend_water_acc["popn_total"] * (trend_water_acc[c] / 100)
            
            level_cols = [c.replace("_pct", "") for c in cols if c in trend_water_acc.columns]
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
                
                fig_cov.update_layout(
                    title="Population Served by Service Level - JMP Standards (Growth Trajectory)",
                    yaxis=dict(title="Population", showgrid=True),
                    xaxis=dict(title="Year"),
                    height=400,
                    legend=dict(orientation="h", y=-0.2, x=0),
                    hovermode='x unified'
                )
                st.plotly_chart(fig_cov, use_container_width=True)
            else:
                st.warning("No coverage data available for selected period")
        else:
            st.warning("Population data not available for coverage trends.")

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
            fig_qual.add_trace(go.Scatter(x=merged_qual["date"], y=merged_qual["water_quality_rate"], name="Water Quality %", line=dict(color="#10b981", width=3), mode='lines+markers'))
            fig_qual.add_trace(go.Scatter(x=merged_qual["date"], y=merged_qual["complaint_resolution_rate"], name="Resolution Rate %", line=dict(color="#3b82f6", width=3), mode='lines+markers'))
            fig_qual.add_trace(go.Scatter(x=merged_qual["date"], y=merged_qual["service_hours"], name="Service Hours", yaxis="y2", line=dict(color="#f59e0b", width=3, dash="dot"), mode='lines+markers'))
            
            fig_qual.update_layout(
                title="Service Quality Trends",
                yaxis=dict(title="Percentage (%)", range=[min_qual, max_qual], showgrid=True, gridwidth=1, gridcolor='#e2e8f0'),
                yaxis2=dict(title="Hours/Day", overlaying="y", side="right", range=[0, 24], showgrid=False),
                legend=dict(orientation="h", y=1.1, x=0),
                height=400,
                hovermode='x unified'
            )
            st.plotly_chart(fig_qual, use_container_width=True)
        else:
            st.info("No service quality data available for selected period")

    # --- Board Brief Generation ---
    st.markdown("---")
    st.markdown("### 📋 Executive Reporting")
    
    col_brief_1, col_brief_2 = st.columns([2, 1])
    
    with col_brief_1:
        st.markdown("Generate a comprehensive board brief with AI-powered narrative and insights.")
    
    with col_brief_2:
        if st.button("📄 Generate Board Brief", type="primary", use_container_width=True):
            with st.spinner("Generating board brief..."):
                # Determine period label
                if selected_month and selected_month != "All":
                    period = f"{selected_month} {selected_year}"
                elif selected_year and selected_year != "All":
                    period = f"Year {selected_year}"
                else:
                    period = "Current Period"
                
                brief_text = generate_board_brief_text(f_billing, f_prod, f_fin, period)
                
                # Display in expander
                with st.expander("📊 Board Brief", expanded=True):
                    st.markdown(brief_text)
                    
                    # Download button
                    st.download_button(
                        label="Download as Text",
                        data=brief_text,
                        file_name=f"board_brief_{pd.Timestamp.now().strftime('%Y%m%d')}.txt",
                        mime="text/plain"
                    )
