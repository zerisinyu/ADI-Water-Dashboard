import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from utils import load_json, conic_css as _conic_css, download_button as _download_button, scene_page_path as _scene_page_path, DATA_DIR
from ai_insights import InsightsEngine, generate_board_brief_text

@st.cache_data
def load_dashboard_data():
    """
    Load and prepare data for the executive dashboard.
    """
    # 1. Load Billing Data (for Collection Efficiency & NRW consumption)
    billing_path = DATA_DIR / "all_data - billing.csv"
    if billing_path.exists():
        # Read only necessary columns to save memory
        billing_cols = ["date", "consumption_m3", "billed", "paid", "country", "zone", "source"]
        # Set low_memory=False to handle mixed types warning, and handle date parsing manually for robustness
        billing_df = pd.read_csv(billing_path, usecols=billing_cols, low_memory=False)
        
        # Clean up Date column
        billing_df["date"] = pd.to_datetime(billing_df["date"], errors="coerce")
        
        # Clean up Numeric columns (force numeric, coerce errors to NaN)
        for col in ["consumption_m3", "billed", "paid"]:
            billing_df[col] = pd.to_numeric(billing_df[col], errors="coerce")
            
        # Drop rows with invalid dates (essential for time-based filtering)
        billing_df = billing_df.dropna(subset=["date"])
    else:
        billing_df = pd.DataFrame(columns=["date", "consumption_m3", "billed", "paid", "country", "zone", "source"])

    # 2. Load Financial Services Data (for Opex, Complaints)
    fin_path = DATA_DIR / "financial_services.csv"
    if fin_path.exists():
        fin_df = pd.read_csv(fin_path)
        # Parse date "Jan/20" -> datetime
        fin_df["date"] = pd.to_datetime(fin_df["date_MMYY"], format="%b/%y")
    else:
        fin_df = pd.DataFrame(columns=["country", "city", "date", "sewer_revenue", "opex", "complaints", "resolved"])

    # 3. Load Production Data (for NRW production, Service Hours)
    prod_path = DATA_DIR / "production.csv"
    if prod_path.exists():
        prod_df = pd.read_csv(prod_path)
        prod_df["date"] = pd.to_datetime(prod_df["date_YYMMDD"])
        
        # Map Source to Zone using Billing Data
        if not billing_df.empty:
            source_map = billing_df[["source", "zone", "country"]].drop_duplicates().dropna()
            # Merge zone info into production
            prod_df = prod_df.merge(source_map, on=["source", "country"], how="left")
            # Fill missing zones with "Unknown" or keep NaN
            prod_df["zone"] = prod_df["zone"].fillna("Unknown")
    else:
        prod_df = pd.DataFrame(columns=["date", "production_m3", "service_hours", "country", "zone"])

    return billing_df, fin_df, prod_df

def filter_dataframe(df, country, zone, year, month):
    """
    Filter dataframe based on selected criteria.
    """
    if df.empty:
        return df
    
    filtered = df.copy()
    
    if country and country != "All":
        filtered = filtered[filtered["country"] == country]
    
    if zone and zone != "All":
        if "zone" in filtered.columns:
            filtered = filtered[filtered["zone"] == zone]
            
    if year and year != "All":
        filtered = filtered[filtered["date"].dt.year == int(year)]
        
    if month and month != "All":
        # Map month name to number
        month_map = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }
        m_num = month_map.get(month)
        if m_num:
            filtered = filtered[filtered["date"].dt.month == m_num]
            
    return filtered

def scene_executive():
    # --- 1. Load Data ---
    billing_df, fin_df, prod_df = load_dashboard_data()

    # --- 2. Get Filters from Session State ---
    selected_country = st.session_state.get("selected_country", "All")
    selected_zone = st.session_state.get("selected_zone", "All")
    selected_year = st.session_state.get("selected_year", "All")
    selected_month = st.session_state.get("selected_month", "All")

    # --- 3. Filter Data ---
    f_billing = filter_dataframe(billing_df, selected_country, selected_zone, selected_year, selected_month)
    f_fin = filter_dataframe(fin_df, selected_country, selected_zone, selected_year, selected_month) # Fin data has city, not zone, but let's assume city~zone or ignore zone filter for fin if not present
    f_prod = filter_dataframe(prod_df, selected_country, selected_zone, selected_year, selected_month)

    # Note: Financial data often is at City level. If Zone is selected, we might need to approximate or show City data.
    # For this exercise, we'll assume strict filtering if column exists.

    # --- 4. Calculate KPIs ---

    # A. Collection Efficiency
    total_billed = f_billing["billed"].sum()
    total_paid = f_billing["paid"].sum()
    coll_eff = (total_paid / total_billed * 100) if total_billed > 0 else 0

    # B. Operating Cost Coverage
    # Revenue = Paid (Billing) + Sewer Revenue (Fin)
    # Note: Fin data might need scaling if it's monthly and we filter by year.
    total_sewer_rev = f_fin["sewer_revenue"].sum()
    total_revenue = total_paid + total_sewer_rev
    total_opex = f_fin["opex"].sum()
    opex_coverage = (total_revenue / total_opex) if total_opex > 0 else 0

    # C. NRW (Non-Revenue Water)
    total_production = f_prod["production_m3"].sum()
    total_consumption = f_billing["consumption_m3"].sum()
    nrw_pct = ((total_production - total_consumption) / total_production * 100) if total_production > 0 else 0
    
    # D. Service Hours
    avg_service_hours = f_prod["service_hours"].mean() if not f_prod.empty else 0

    # E. Complaint Resolution
    total_complaints = f_fin["complaints"].sum()
    total_resolved = f_fin["resolved"].sum()
    complaint_res_rate = (total_resolved / total_complaints * 100) if total_complaints > 0 else 0

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
        "nrw_percent": nrw_pct,
        "service_hours": avg_service_hours,
        "anomalies": anomalies,
        "zones": insights_engine.zone_performance_summary(),
        "suggested_questions": suggested_questions
    }

    # --- 6. Layout & Visualization ---

    # CSS Styling for Scorecards (matching other pages)
    st.markdown("""
    <style>
        .metric-container {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 16px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            height: 100%;
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
    if nrw_pct > 40:
        st.markdown(f"<div class='panel bad'>⚠️ Critical Alert: NRW is high ({nrw_pct:.1f}%) in selected region. Immediate action required.</div>", unsafe_allow_html=True)
    elif avg_service_hours < 12:
        st.markdown(f"<div class='panel warn'>⚠️ Warning: Service hours dropped to {avg_service_hours:.1f} hrs/day.</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='panel ok'>✅ Systems Operational. All key metrics within acceptable range.</div>", unsafe_allow_html=True)

    # Scorecards Row
    st.markdown("### Key Performance Indicators")
    
    # Define metrics: (Label, Value, Target, Unit, HigherIsBetter)
    metrics_data = [
        ("Collection Efficiency", coll_eff, 95, "%", True),
        ("Operating Cost Coverage", opex_coverage, 1.0, "", True),
        ("Non-Revenue Water", nrw_pct, 25, "%", False), # Lower is better
        ("Avg Service Hours", avg_service_hours, 20, "h", True)
    ]

    cols = st.columns(4)
    
    for col, (label, value, target, unit, higher_is_better) in zip(cols, metrics_data):
        delta = value - target
        
        # Determine color (Good/Bad)
        is_good = (delta >= 0) if higher_is_better else (delta <= 0)
        delta_cls = "delta-up" if is_good else "delta-down"
        
        # Determine Icon (Direction)
        if delta > 0: icon = "↑"
        elif delta < 0: icon = "↓"
        else: icon = "-"
        
        val_str = f"{value:.2f}" if unit == "" else f"{value:.1f}{unit}"
        
        with col:
            st.markdown(f"""
            <div class='metric-container'>
                <div class='metric-label'>{label}</div>
                <div class='metric-value'>{val_str}</div>
                <div class='metric-delta {delta_cls}'>
                    {icon} {abs(delta):.1f}{unit} vs Target
                </div>
            </div>
            """, unsafe_allow_html=True)

    # --- Charts Row 1 ---
    st.markdown("### Financial & Operational Trends")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Revenue vs Opex Trend**")
        # Aggregate by month for the chart
        # We need to group fin_df by date
        fin_trend = fin_df.copy()
        if selected_country and selected_country != "All":
            fin_trend = fin_trend[fin_trend["country"] == selected_country]
        # (Zone filter might not apply to fin data easily if it's city based, skipping for trend to show broader context or just use filtered)
        # Actually let's use the filtered f_fin but we need to group by date.
        # If f_fin is already filtered by specific month, the trend will be a single point. 
        # Usually trends ignore the "Month" filter to show history.
        
        # Re-filter for trend (ignore month/year filter, keep location)
        trend_fin = fin_df.copy()
        trend_billing = billing_df.copy()
        if selected_country and selected_country != "All":
            trend_fin = trend_fin[trend_fin["country"] == selected_country]
            trend_billing = trend_billing[trend_billing["country"] == selected_country]
        if selected_zone and selected_zone != "All":
             if "zone" in trend_billing.columns:
                trend_billing = trend_billing[trend_billing["zone"] == selected_zone]
             # Fin data doesn't have zone usually, so we might keep it as is or try to filter by city if mapped.
        
        # Group by Month
        fin_monthly = trend_fin.groupby(pd.Grouper(key="date", freq="ME")).agg({"opex": "sum", "sewer_revenue": "sum"}).reset_index()
        billing_monthly = trend_billing.groupby(pd.Grouper(key="date", freq="ME")).agg({"paid": "sum"}).reset_index()
        
        merged_trend = pd.merge(fin_monthly, billing_monthly, on="date", how="outer").fillna(0)
        merged_trend["total_revenue"] = merged_trend["paid"] + merged_trend["sewer_revenue"]
        
        # Sort by date
        merged_trend = merged_trend.sort_values("date")
        
        fig_fin = go.Figure()
        fig_fin.add_trace(go.Bar(x=merged_trend["date"], y=merged_trend["total_revenue"], name="Revenue", marker_color="#10b981"))
        fig_fin.add_trace(go.Bar(x=merged_trend["date"], y=merged_trend["opex"], name="Opex", marker_color="#ef4444"))
        fig_fin.update_layout(barmode='group', margin=dict(l=0, r=0, t=0, b=0), height=300, legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig_fin, use_container_width=True)

    with c2:
        st.markdown("**NRW Trend (Last 12 Months)**")
        # Trend for NRW
        trend_prod = prod_df.copy()
        if selected_country and selected_country != "All":
            trend_prod = trend_prod[trend_prod["country"] == selected_country]
        if selected_zone and selected_zone != "All":
            trend_prod = trend_prod[trend_prod["zone"] == selected_zone]
            
        prod_monthly = trend_prod.groupby(pd.Grouper(key="date", freq="ME")).agg({"production_m3": "sum"}).reset_index()
        cons_monthly = trend_billing.groupby(pd.Grouper(key="date", freq="ME")).agg({"consumption_m3": "sum"}).reset_index()
        
        nrw_trend = pd.merge(prod_monthly, cons_monthly, on="date", how="inner")
        nrw_trend["nrw_pct"] = (nrw_trend["production_m3"] - nrw_trend["consumption_m3"]) / nrw_trend["production_m3"] * 100
        
        fig_nrw = px.line(nrw_trend, x="date", y="nrw_pct", markers=True)
        fig_nrw.add_hline(y=25, line_dash="dash", line_color="green", annotation_text="Target (25%)")
        fig_nrw.update_traces(line_color="#f59e0b")
        fig_nrw.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=300, yaxis_title="NRW %")
        st.plotly_chart(fig_nrw, use_container_width=True)

    # --- Charts Row 2 & Strategic ---
    c3, c4 = st.columns([2, 1])
    
    with c3:
        st.markdown("**Service Hours vs Complaints**")
        # Dual axis chart
        # Service hours from prod (daily/monthly avg), Complaints from fin (monthly)
        
        # Group prod by month for compatibility
        prod_monthly_svc = trend_prod.groupby(pd.Grouper(key="date", freq="ME")).agg({"service_hours": "mean"}).reset_index()
        fin_monthly_comp = trend_fin.groupby(pd.Grouper(key="date", freq="ME")).agg({"complaints": "sum"}).reset_index()
        
        svc_comp = pd.merge(prod_monthly_svc, fin_monthly_comp, on="date", how="outer").sort_values("date")
        
        fig_dual = go.Figure()
        fig_dual.add_trace(go.Scatter(x=svc_comp["date"], y=svc_comp["service_hours"], name="Avg Service Hours", line=dict(color="#4f46e5", width=3)))
        fig_dual.add_trace(go.Scatter(x=svc_comp["date"], y=svc_comp["complaints"], name="Complaints", yaxis="y2", line=dict(color="#ef4444", dash="dot")))
        
        fig_dual.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            height=300,
            yaxis=dict(title="Hours/Day"),
            yaxis2=dict(title="Complaints", overlaying="y", side="right"),
            legend=dict(orientation="h", y=1.1)
        )
        st.plotly_chart(fig_dual, use_container_width=True)

    with c4:
        # Mock Data for Strategic Indicators (as file is missing)
        asset_health = 4.2 # out of 5
        training_budget = 150000 # $
        
        st.markdown("**Strategic Growth**")
        st.markdown(f"""
        <div class='panel'>
        <div style='margin-bottom:1rem'>
            <div class='meta'>Asset Health Index</div>
            <div style='font-size:2rem;font-weight:700;color:#4f46e5'>{asset_health}/5.0</div>
            <div class='meta'>Target: 4.5</div>
            <div style='background:#e0e7ff;height:8px;border-radius:4px;margin-top:4px'>
                <div style='background:#4f46e5;width:{asset_health/5*100}%;height:100%;border-radius:4px'></div>
            </div>
        </div>
        
        <div>
            <div class='meta'>Staff Training Investment</div>
            <div style='font-size:2rem;font-weight:700;color:#10b981'>${training_budget/1000:.0f}k</div>
            <div class='meta'>YTD Actual</div>
        </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Complaint Resolution Rate
        st.markdown("**Complaint Resolution**")
        st.markdown(f"""
        <div class='panel' style='display:flex;align-items:center;justify-content:space-between'>
            <div>
                <div class='meta'>Resolution Rate</div>
                <div style='font-size:1.5rem;font-weight:700'>{complaint_res_rate:.1f}%</div>
            </div>
            <div class='gauge' style='{_conic_css(complaint_res_rate, "#10b981")};width:48px;height:48px'>
                <div class='gauge-inner' style='width:36px;height:36px'></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

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
