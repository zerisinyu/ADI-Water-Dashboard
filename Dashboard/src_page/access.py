import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from utils import prepare_access_data, prepare_service_data, DATA_DIR

def load_financial_data():
    """Load financial services data for the access dashboard."""
    fin_path = DATA_DIR / "financial_services.csv"
    df_fin = pd.DataFrame()
    
    if fin_path.exists():
        df_fin = pd.read_csv(fin_path)
        if 'date_MMYY' in df_fin.columns:
            df_fin['date'] = pd.to_datetime(df_fin['date_MMYY'], format='%b/%y', errors='coerce')
        df_fin['year'] = df_fin['date'].dt.year
        df_fin['month'] = df_fin['date'].dt.month
    return df_fin

def scene_access():
    """
    Access & Coverage scene - Redesigned based on User Journey.
    """
    # Load data
    access_data = prepare_access_data()
    df_water = access_data["water_full"]
    df_sewer = access_data["sewer_full"]
    
    service_data = prepare_service_data()
    df_service = service_data["full_data"]
    
    df_fin = load_financial_data()

    # --- 1. Filters (Retrieved from Sidebar/Session State) ---
    selected_country = st.session_state.get("selected_country", "All")
    selected_zone = st.session_state.get("selected_zone", "All")
    selected_year = st.session_state.get("selected_year")
    selected_month_name = st.session_state.get("selected_month", "All")

    # Map month name to number (for Service Data)
    month_map = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    selected_month = month_map.get(selected_month_name) if selected_month_name != 'All' else 'All'

    # Ensure selected_year is valid for this dataset, otherwise default to max
    if selected_year not in df_water['year'].unique():
        # If the selected year (from global filter) isn't in access data, fallback or show empty?
        # Usually better to show empty or nearest. Let's stick to the filter.
        pass 

    # --- Apply Filters ---
    # Water Data
    df_w_filt = df_water.copy()
    if selected_country != 'All': df_w_filt = df_w_filt[df_w_filt['country'] == selected_country]
    if selected_zone != 'All': df_w_filt = df_w_filt[df_w_filt['zone'] == selected_zone]
    if selected_year: df_w_filt = df_w_filt[df_w_filt['year'] == selected_year]

    # Sewer Data
    df_s_filt = df_sewer.copy()
    if selected_country != 'All': df_s_filt = df_s_filt[df_s_filt['country'] == selected_country]
    if selected_zone != 'All': df_s_filt = df_s_filt[df_s_filt['zone'] == selected_zone]
    if selected_year: df_s_filt = df_s_filt[df_s_filt['year'] == selected_year]

    # Service Data (Monthly)
    df_svc_filt = df_service.copy()
    if selected_country != 'All': df_svc_filt = df_svc_filt[df_svc_filt['country'] == selected_country]
    if selected_zone != 'All': df_svc_filt = df_svc_filt[df_svc_filt['zone'] == selected_zone]
    if selected_year: df_svc_filt = df_svc_filt[df_svc_filt['year'] == selected_year]
    if selected_month != 'All': df_svc_filt = df_svc_filt[df_svc_filt['month'] == selected_month]

    # Financial Data (for Pro-Poor)
    df_f_filt = df_fin.copy()
    if selected_country != 'All' and 'country' in df_f_filt.columns:
        df_f_filt = df_f_filt[df_f_filt['country'].str.lower() == selected_country.lower()]
    if 'year' in df_f_filt.columns and selected_year:
        df_f_filt = df_f_filt[df_f_filt['year'] == selected_year]
    if selected_month != 'All' and 'month' in df_f_filt.columns:
        df_f_filt = df_f_filt[df_f_filt['month'] == selected_month]

    if df_w_filt.empty and df_s_filt.empty:
        st.warning("⚠️ No access data available for selected filters")
        return

    # --- CSS Styling ---
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
        
        .section-header {
            font-size: 18px;
            font-weight: 600;
            color: #111827;
            margin: 24px 0 16px 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .chart-container {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 16px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }
    </style>
    """, unsafe_allow_html=True)

    # --- Step 1: Coverage Level Metrics ---
    st.markdown("<div class='section-header'>📊 Coverage Metrics <span style='font-size:14px;color:#6b7280;font-weight:400'>| Service Reach & Growth</span></div>", unsafe_allow_html=True)

    # ===== WATER COVERAGE CALCULATIONS =====
    # Municipal Supply Percentage (Annual data)
    total_pop_w = df_w_filt['popn_total'].sum()
    muni_cov_count = df_w_filt['municipal_coverage'].sum()
    muni_supply_pct = (muni_cov_count / total_pop_w * 100) if total_pop_w > 0 else 0
    
    # YoY Growth for Municipal Supply (Always YoY since it's annual data)
    if selected_year and selected_year > df_water['year'].min():
        last_year = selected_year - 1
        df_w_last = df_water.copy()
        if selected_country != 'All': df_w_last = df_w_last[df_w_last['country'] == selected_country]
        if selected_zone != 'All': df_w_last = df_w_last[df_w_last['zone'] == selected_zone]
        df_w_last = df_w_last[df_w_last['year'] == last_year]
        
        total_pop_w_last = df_w_last['popn_total'].sum()
        muni_cov_last = df_w_last['municipal_coverage'].sum()
        muni_supply_pct_last = (muni_cov_last / total_pop_w_last * 100) if total_pop_w_last > 0 else 0
        muni_yoy_growth = muni_supply_pct - muni_supply_pct_last
    else:
        muni_yoy_growth = 0
    
    # Water: Households Covered & Population Served (from water access data)
    water_households = df_w_filt['households'].sum() / 1000  # Convert to K
    water_population = total_pop_w / 1000000  # Convert to M
    
    # ===== SANITATION COVERAGE CALCULATIONS =====
    # Sewered Connections Percentage (Monthly data from service data)
    if not df_svc_filt.empty:
        # Aggregate by zone first, then sum
        svc_agg = df_svc_filt.groupby('zone').agg({
            'sewer_connections': 'sum',
            'households': 'max'  # Take max households per zone as it's relatively stable
        }).reset_index()
        total_sewer_conn = svc_agg['sewer_connections'].sum()
        total_hh_svc = svc_agg['households'].sum()
        sewer_conn_pct = (total_sewer_conn / total_hh_svc * 100) if total_hh_svc > 0 else 0
        
        # Calculate growth (YoY or MoM depending on filter)
        if selected_month != 'All':
            # MoM Growth (Month-over-Month)
            last_month = selected_month - 1 if selected_month > 1 else 12
            last_month_year = selected_year if selected_month > 1 else (selected_year - 1 if selected_year else None)
            
            df_svc_last = df_service.copy()
            if selected_country != 'All': df_svc_last = df_svc_last[df_svc_last['country'] == selected_country]
            if selected_zone != 'All': df_svc_last = df_svc_last[df_svc_last['zone'] == selected_zone]
            if last_month_year: df_svc_last = df_svc_last[df_svc_last['year'] == last_month_year]
            df_svc_last = df_svc_last[df_svc_last['month'] == last_month]
            
            if not df_svc_last.empty:
                svc_agg_last = df_svc_last.groupby('zone').agg({
                    'sewer_connections': 'sum',
                    'households': 'max'
                }).reset_index()
                total_sewer_conn_last = svc_agg_last['sewer_connections'].sum()
                total_hh_svc_last = svc_agg_last['households'].sum()
                sewer_conn_pct_last = (total_sewer_conn_last / total_hh_svc_last * 100) if total_hh_svc_last > 0 else 0
                sewer_growth = sewer_conn_pct - sewer_conn_pct_last
                growth_label = "MoM"
            else:
                sewer_growth = 0
                growth_label = "MoM"
        else:
            # YoY Growth (when 'All' months selected)
            if selected_year and selected_year > df_service['year'].min():
                last_year = selected_year - 1
                df_svc_last = df_service.copy()
                if selected_country != 'All': df_svc_last = df_svc_last[df_svc_last['country'] == selected_country]
                if selected_zone != 'All': df_svc_last = df_svc_last[df_svc_last['zone'] == selected_zone]
                df_svc_last = df_svc_last[df_svc_last['year'] == last_year]
                
                if not df_svc_last.empty:
                    svc_agg_last = df_svc_last.groupby('zone').agg({
                        'sewer_connections': 'sum',
                        'households': 'max'
                    }).reset_index()
                    total_sewer_conn_last = svc_agg_last['sewer_connections'].sum()
                    total_hh_svc_last = svc_agg_last['households'].sum()
                    sewer_conn_pct_last = (total_sewer_conn_last / total_hh_svc_last * 100) if total_hh_svc_last > 0 else 0
                    sewer_growth = sewer_conn_pct - sewer_conn_pct_last
                else:
                    sewer_growth = 0
            else:
                sewer_growth = 0
            growth_label = "YoY"
        
        # Sanitation: Households Connected & Population Served
        # Use households from service data and estimate population
        san_households = total_sewer_conn / 1000  # Households connected in K
        # Estimate population served (assume average household size ~5)
        san_population = (total_sewer_conn * 5) / 1000000  # Population in M
    else:
        sewer_conn_pct = 0
        sewer_growth = 0
        growth_label = "YoY"
        san_households = 0
        san_population = 0

    # ===== RENDER TWO-COLUMN LAYOUT =====
    col_water, col_san = st.columns(2)
    
    # WATER COVERAGE COLUMN
    with col_water:
        st.markdown("""
        <div style='font-size: 16px; font-weight: 700; color: #1e40af; margin-bottom: 16px; text-align: center;'>
            💧 WATER COVERAGE
        </div>
        """, unsafe_allow_html=True)
        
        # Row 1: Municipal Supply % and YoY Growth
        
        r1c1, r1c2 = st.columns([3, 2])
        with r1c1:
            # Progress ring visualization
            st.markdown(f"""
            <div style='text-align: center;'>
                <div style='font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;'>
                    Municipal Supply
                </div>
                <div style='position: relative; width: 120px; height: 120px; margin: 0 auto;'>
                    <svg width="120" height="120" style='transform: rotate(-90deg);'>
                        <circle cx="60" cy="60" r="50" fill="none" stroke="#e5e7eb" stroke-width="8"/>
                        <circle cx="60" cy="60" r="50" fill="none" stroke="#3b82f6" stroke-width="8"
                                stroke-dasharray="{2 * 3.14159 * 50 * muni_supply_pct / 100} {2 * 3.14159 * 50}"
                                stroke-linecap="round"/>
                    </svg>
                    <div style='position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);'>
                        <div style='font-size: 28px; font-weight: 700; color: #111827;'>{muni_supply_pct:.1f}%</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with r1c2:
            growth_color = "#059669" if muni_yoy_growth >= 0 else "#dc2626"
            growth_icon = "↑" if muni_yoy_growth >= 0 else "↓"
            st.markdown(f"""
            <div style='text-align: center; padding-top: 20px;'>
                <div style='font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;'>
                    YoY Growth
                </div>
                <div style='font-size: 32px; font-weight: 700; color: {growth_color};'>
                    {growth_icon}{abs(muni_yoy_growth):.1f}%
                </div>
                <div style='font-size: 10px; color: #6b7280; margin-top: 4px;'>
                    vs Last Year
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Row 2: Households Covered and Population Served
        
        r2c1, r2c2 = st.columns(2)
        with r2c1:
            st.markdown(f"""
            <div style='text-align: center;'>
                <div style='font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;'>
                    Households Covered
                </div>
                <div style='font-size: 28px; font-weight: 700; color: #111827;'>
                    {water_households:.1f}K
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with r2c2:
            st.markdown(f"""
            <div style='text-align: center;'>
                <div style='font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;'>
                    Population Served
                </div>
                <div style='font-size: 28px; font-weight: 700; color: #111827;'>
                    {water_population:.2f}M
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("</div></div>", unsafe_allow_html=True)
    
    # SANITATION COVERAGE COLUMN
    with col_san:
        st.markdown("""
        <div style='font-size: 16px; font-weight: 700; color: #6b21a8; margin-bottom: 16px; text-align: center;'>
            🚽 SANITATION COVERAGE
        </div>
        """, unsafe_allow_html=True)
        
        # Row 1: Sewered Connections % and Growth (YoY or MoM)
        
        r1c1, r1c2 = st.columns([3, 2])
        with r1c1:
            # Progress ring visualization
            st.markdown(f"""
            <div style='text-align: center;'>
                <div style='font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;'>
                    Sewered Connections
                </div>
                <div style='position: relative; width: 120px; height: 120px; margin: 0 auto;'>
                    <svg width="120" height="120" style='transform: rotate(-90deg);'>
                        <circle cx="60" cy="60" r="50" fill="none" stroke="#e5e7eb" stroke-width="8"/>
                        <circle cx="60" cy="60" r="50" fill="none" stroke="#8b5cf6" stroke-width="8"
                                stroke-dasharray="{2 * 3.14159 * 50 * sewer_conn_pct / 100} {2 * 3.14159 * 50}"
                                stroke-linecap="round"/>
                    </svg>
                    <div style='position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);'>
                        <div style='font-size: 28px; font-weight: 700; color: #111827;'>{sewer_conn_pct:.1f}%</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with r1c2:
            growth_color = "#059669" if sewer_growth >= 0 else "#dc2626"
            growth_icon = "↑" if sewer_growth >= 0 else "↓"
            st.markdown(f"""
            <div style='text-align: center; padding-top: 20px;'>
                <div style='font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;'>
                    {growth_label} Growth
                </div>
                <div style='font-size: 32px; font-weight: 700; color: {growth_color};'>
                    {growth_icon}{abs(sewer_growth):.1f}%
                </div>
                <div style='font-size: 10px; color: #6b7280; margin-top: 4px;'>
                    vs Last {'Month' if growth_label == 'MoM' else 'Year'}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Row 2: Households Connected and Population Served
        
        r2c1, r2c2 = st.columns(2)
        with r2c1:
            st.markdown(f"""
            <div style='text-align: center;'>
                <div style='font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;'>
                    Households Connected
                </div>
                <div style='font-size: 28px; font-weight: 700; color: #111827;'>
                    {san_households:.1f}K
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with r2c2:
            st.markdown(f"""
            <div style='text-align: center;'>
                <div style='font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;'>
                    Population Served
                </div>
                <div style='font-size: 28px; font-weight: 700; color: #111827;'>
                    {san_population:.2f}M
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("</div></div>", unsafe_allow_html=True)

    # --- Define ladder columns and labels (used by multiple sections) ---
    w_ladder_cols = ['surface_water', 'w_unimproved', 'w_limited', 'w_basic', 'w_safely_managed']
    w_ladder_labels = ['Surface Water', 'Unimproved', 'Limited', 'Basic', 'Safely Managed']
    s_ladder_cols = ['open_def', 's_unimproved', 's_limited', 's_basic', 's_safely_managed']
    s_ladder_labels = ['Open Defecation', 'Unimproved', 'Limited', 'Basic', 'Safely Managed']

    # --- Step 2: The "Ladder" Analysis (Quality of Access) ---
    st.markdown("<div class='section-header'>🪜 Ladder Analysis <span style='font-size:14px;color:#6b7280;font-weight:400'>| Quality of Access</span></div>", unsafe_allow_html=True)
    
    # Professional controls layout
    with st.container():
        ctrl_row1_col1, ctrl_row1_col2, ctrl_row1_col3, ctrl_row1_col4 = st.columns([2, 2, 2, 2])
        
        with ctrl_row1_col1:
            chart_type = st.selectbox(
                "Visualization Type:",
                ["Stacked Bar Chart", "Trend Analysis"],
                key="chart_type_selector"
            )
        
        with ctrl_row1_col2:
            display_mode = st.radio(
                "Display Mode:", 
                ["Percentage", "Absolute"], 
                horizontal=True, 
                key="ladder_display"
            )
        
        with ctrl_row1_col3:
            st.markdown("<div style='font-size:12px;font-weight:600;color:#6b7280;margin-bottom:4px;'>SHOW DATA FOR:</div>", unsafe_allow_html=True)
            data_selection = st.radio(
                "Show Data For",
                ["💧 Water", "🚽 Sanitation", "Both"],
                horizontal=True,
                key="data_selection",
                index=2,
                label_visibility="collapsed"
            )
            show_water = data_selection in ["💧 Water", "Both"]
            show_sanitation = data_selection in ["🚽 Sanitation", "Both"]
        
        with ctrl_row1_col4:
            pass
    
    # Get available years for filtering
    available_years = sorted(df_water['year'].unique())
    
    # Filter data - use selected_year from global filter
    df_w_ladder = df_water.copy()
    df_s_ladder = df_sewer.copy()
    
    if selected_country != 'All': 
        df_w_ladder = df_w_ladder[df_w_ladder['country'] == selected_country]
        df_s_ladder = df_s_ladder[df_s_ladder['country'] == selected_country]
    if selected_zone != 'All': 
        df_w_ladder = df_w_ladder[df_w_ladder['zone'] == selected_zone]
        df_s_ladder = df_s_ladder[df_s_ladder['zone'] == selected_zone]
    
    # For bar chart, use selected year; for trend, use all years
    if chart_type == "Stacked Bar Chart":
        if selected_year:
            df_w_ladder = df_w_ladder[df_w_ladder['year'] == selected_year]
            df_s_ladder = df_s_ladder[df_s_ladder['year'] == selected_year]
        else:
            # Use latest year if no year selected
            latest_year = available_years[-1] if available_years else 2024
            df_w_ladder = df_w_ladder[df_w_ladder['year'] == latest_year]
            df_s_ladder = df_s_ladder[df_s_ladder['year'] == latest_year]
    
    # Determine grouping level
    if selected_country == 'All':
        group_by = 'country'
    elif selected_zone == 'All':
        group_by = 'zone'
    else:
        group_by = None  # Single entity
    
    # Color schemes - Use same colors for both water and sanitation
    colors = ['#ef4444', '#f97316', '#eab308', '#60a5fa', '#1e3a8a']
    
    # Determine bar width and gap based on what's shown
    both_shown = show_water and show_sanitation
    bar_width = 0.25 if both_shown else 0.45
    bar_gap = 0.15 if both_shown else 0.2
    
    # Create the chart based on selected type
    fig_ladder = go.Figure()
    
    # TREND ANALYSIS CHART
    if chart_type == "Trend Analysis":
        # Use all available years for trend
        df_w_trend = df_water.copy()
        df_s_trend = df_sewer.copy()
        
        if selected_country != 'All':
            df_w_trend = df_w_trend[df_w_trend['country'] == selected_country]
            df_s_trend = df_s_trend[df_s_trend['country'] == selected_country]
        if selected_zone != 'All':
            df_w_trend = df_w_trend[df_w_trend['zone'] == selected_zone]
            df_s_trend = df_s_trend[df_s_trend['zone'] == selected_zone]
        
        # Water Trend Lines
        if show_water:
            w_trend_agg = df_w_trend.groupby('year')[w_ladder_cols + ['popn_total']].sum().reset_index()
            
            for idx, (col, label, color) in enumerate(zip(w_ladder_cols, w_ladder_labels, colors)):
                if display_mode == "Percentage":
                    y_values = (w_trend_agg[col] / w_trend_agg['popn_total'] * 100).fillna(0)
                    y_suffix = "%"
                else:
                    y_values = w_trend_agg[col] / 1000  # Convert to K
                    y_suffix = "K"
                
                fig_ladder.add_trace(go.Scatter(
                    x=w_trend_agg['year'],
                    y=y_values,
                    name=f'W: {label}',
                    mode='lines+markers',
                    line=dict(color=color, width=2),
                    marker=dict(size=6, symbol='circle'),
                    legendgroup='water',
                    legendgrouptitle_text='Water Access',
                    hovertemplate=f'<b>{label}</b><br>Year: %{{x}}<br>Value: %{{y:.1f}}{y_suffix}<extra></extra>'
                ))
        
        # Sanitation Trend Lines
        if show_sanitation:
            s_trend_agg = df_s_trend.groupby('year')[s_ladder_cols + ['popn_total']].sum().reset_index()
            
            for idx, (col, label, color) in enumerate(zip(s_ladder_cols, s_ladder_labels, colors)):
                if display_mode == "Percentage":
                    y_values = (s_trend_agg[col] / s_trend_agg['popn_total'] * 100).fillna(0)
                    y_suffix = "%"
                else:
                    y_values = s_trend_agg[col] / 1000  # Convert to K
                    y_suffix = "K"
                
                fig_ladder.add_trace(go.Scatter(
                    x=s_trend_agg['year'],
                    y=y_values,
                    name=f'S: {label}',
                    mode='lines+markers',
                    line=dict(color=color, width=2, dash='dot'),
                    marker=dict(size=6, symbol='diamond'),
                    legendgroup='sanitation',
                    legendgrouptitle_text='Sanitation Access',
                    hovertemplate=f'<b>{label}</b><br>Year: %{{x}}<br>Value: %{{y:.1f}}{y_suffix}<extra></extra>'
                ))
        
        # Update layout for trend chart
        y_title = "Percentage (%)" if display_mode == "Percentage" else "Population (Thousands)"
        fig_ladder.update_layout(
            height=450,
            margin=dict(l=0, r=0, t=40, b=0),
            title=dict(
                text=f"Access Ladder Trends (2020-2024)",
                font=dict(size=16)
            ),
            xaxis=dict(
                title="Year",
                tickmode='linear',
                dtick=1,
                showgrid=True,
                gridcolor='rgba(128,128,128,0.1)'
            ),
            yaxis=dict(
                title=y_title,
                showgrid=True,
                gridcolor='rgba(128,128,128,0.1)'
            ),
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02,
                groupclick="toggleitem"
            ),
            hovermode='x unified',
            plot_bgcolor='rgba(250,250,250,0.5)'
        )
    
    # STACKED BAR CHART
    elif group_by:
        # Grouped by country or zone
        # Water Access
        if show_water:
            w_grouped = df_w_ladder.groupby(group_by)[w_ladder_cols + ['popn_total']].sum().reset_index()
            
            for idx, (col, label, color) in enumerate(zip(w_ladder_cols, w_ladder_labels, colors)):
                if display_mode == "Percentage":
                    y_values = (w_grouped[col] / w_grouped['popn_total'] * 100).fillna(0)
                    customdata = w_grouped[col]  # Actual numbers for hover
                    text_values = [f"{y:.1f}%" if y > 5 else "" for y in y_values]
                    hovertemplate = f'<b>{label}</b><br>%{{x}}<br>%{{y:.1f}}%<br>Population: %{{customdata:,.0f}}<extra></extra>'
                else:
                    y_values = w_grouped[col]
                    customdata = (w_grouped[col] / w_grouped['popn_total'] * 100).fillna(0)
                    text_values = [f"{y/1000:.1f}K" if y > 5000 else "" for y in y_values]
                    hovertemplate = f'<b>{label}</b><br>%{{x}}<br>%{{y:,.0f}} people<br>Percentage: %{{customdata:.1f}}%<extra></extra>'
                
                fig_ladder.add_trace(go.Bar(
                    name=f'W: {label}',
                    x=w_grouped[group_by],
                    y=y_values,
                    customdata=customdata,
                    text=text_values,
                    textposition='inside',
                    textfont=dict(size=10, color='white'),
                    marker_color=color,
                    legendgroup='water',
                    legendgrouptitle_text='Water Access',
                    hovertemplate=hovertemplate,
                    offsetgroup='water',
                    width=bar_width
                ))
        
        # Sanitation Access
        if show_sanitation:
            s_grouped = df_s_ladder.groupby(group_by)[s_ladder_cols + ['popn_total']].sum().reset_index()
            
            for idx, (col, label, color) in enumerate(zip(s_ladder_cols, s_ladder_labels, colors)):
                if display_mode == "Percentage":
                    y_values = (s_grouped[col] / s_grouped['popn_total'] * 100).fillna(0)
                    customdata = s_grouped[col]
                    text_values = [f"{y:.1f}%" if y > 5 else "" for y in y_values]
                    hovertemplate = f'<b>{label}</b><br>%{{x}}<br>%{{y:.1f}}%<br>Population: %{{customdata:,.0f}}<extra></extra>'
                else:
                    y_values = s_grouped[col]
                    customdata = (s_grouped[col] / s_grouped['popn_total'] * 100).fillna(0)
                    text_values = [f"{y/1000:.1f}K" if y > 5000 else "" for y in y_values]
                    hovertemplate = f'<b>{label}</b><br>%{{x}}<br>%{{y:,.0f}} people<br>Percentage: %{{customdata:.1f}}%<extra></extra>'
                
                fig_ladder.add_trace(go.Bar(
                    name=f'S: {label}',
                    x=s_grouped[group_by],
                    y=y_values,
                    customdata=customdata,
                    text=text_values,
                    textposition='inside',
                    textfont=dict(size=10, color='white'),
                    marker=dict(
                        color=color,
                        pattern=dict(shape='/', solidity=0.5, size=6, bgcolor='rgba(255,255,255,0.2)')
                    ),
                    legendgroup='sanitation',
                    legendgrouptitle_text='Sanitation Access',
                    hovertemplate=hovertemplate,
                    offsetgroup='sanitation',
                    width=bar_width
                ))
    else:
        # Single entity (specific zone selected)
        entity_name = selected_zone if selected_zone != 'All' else selected_country
        
        # Water Access
        if show_water:
            w_totals = df_w_ladder[w_ladder_cols].sum()
            total_pop_w = df_w_ladder['popn_total'].sum()
            
            for idx, (col, label, color) in enumerate(zip(w_ladder_cols, w_ladder_labels, colors)):
                if display_mode == "Percentage":
                    y_value = (w_totals[col] / total_pop_w * 100) if total_pop_w > 0 else 0
                    customdata = [w_totals[col]]
                    text_val = f"{y_value:.1f}%" if y_value > 5 else ""
                    hovertemplate = f'<b>{label}</b><br>Water<br>{y_value:.1f}%<br>Population: {w_totals[col]:,.0f}<extra></extra>'
                else:
                    y_value = w_totals[col]
                    pct = (w_totals[col] / total_pop_w * 100) if total_pop_w > 0 else 0
                    customdata = [pct]
                    text_val = f"{y_value/1000:.1f}K" if y_value > 5000 else ""
                    hovertemplate = f'<b>{label}</b><br>Water<br>{y_value:,.0f} people<br>Percentage: {pct:.1f}%<extra></extra>'
                
                fig_ladder.add_trace(go.Bar(
                    name=f'W: {label}',
                    x=['Water Access'],
                    y=[y_value],
                    customdata=customdata,
                    text=[text_val],
                    textposition='inside',
                    textfont=dict(size=10, color='white'),
                    marker_color=color,
                    legendgroup='water',
                    legendgrouptitle_text='Water Access',
                    hovertemplate=hovertemplate,
                    offsetgroup='water',
                    width=bar_width
                ))
        
        # Sanitation Access
        if show_sanitation:
            s_totals = df_s_ladder[s_ladder_cols].sum()
            total_pop_s = df_s_ladder['popn_total'].sum()
            
            for idx, (col, label, color) in enumerate(zip(s_ladder_cols, s_ladder_labels, colors)):
                if display_mode == "Percentage":
                    y_value = (s_totals[col] / total_pop_s * 100) if total_pop_s > 0 else 0
                    customdata = [s_totals[col]]
                    text_val = f"{y_value:.1f}%" if y_value > 5 else ""
                    hovertemplate = f'<b>{label}</b><br>Sanitation<br>{y_value:.1f}%<br>Population: {s_totals[col]:,.0f}<extra></extra>'
                else:
                    y_value = s_totals[col]
                    pct = (s_totals[col] / total_pop_s * 100) if total_pop_s > 0 else 0
                    customdata = [pct]
                    text_val = f"{y_value/1000:.1f}K" if y_value > 5000 else ""
                    hovertemplate = f'<b>{label}</b><br>Sanitation<br>{y_value:,.0f} people<br>Percentage: {pct:.1f}%<extra></extra>'
                
                fig_ladder.add_trace(go.Bar(
                    name=f'S: {label}',
                    x=['Sanitation Access'],
                    y=[y_value],
                    customdata=customdata,
                    text=[text_val],
                    textposition='inside',
                    textfont=dict(size=10, color='white'),
                    marker=dict(
                        color=color,
                        pattern=dict(shape='/', solidity=0.5, size=6, bgcolor='rgba(255,255,255,0.2)')
                    ),
                    legendgroup='sanitation',
                    legendgrouptitle_text='Sanitation Access',
                    hovertemplate=hovertemplate,
                    offsetgroup='sanitation',
                    width=bar_width
                ))
    
    # Update layout for bar chart
    if chart_type == "Stacked Bar Chart":
        y_title = "Percentage (%)" if display_mode == "Percentage" else "Population"
        chart_year = selected_year if selected_year else available_years[-1] if available_years else 2024
        fig_ladder.update_layout(
            barmode='stack',
            height=450,
            margin=dict(l=0, r=0, t=40, b=0),
            title=dict(
                text=f"Access Ladder Comparison - {chart_year}",
                font=dict(size=16)
            ),
            xaxis_title=group_by.title() if group_by else "Access Type",
            yaxis_title=y_title,
            bargap=bar_gap,
            bargroupgap=0.1,
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02,
                groupclick="toggleitem"
            ),
            hovermode='closest'
        )
    
    st.plotly_chart(fig_ladder, use_container_width=True)

    # --- Step 4: The Equity Check (Zonal Disparities) ---
    st.markdown("<div class='section-header'>⚖️ Equity Check <span style='font-size:14px;color:#6b7280;font-weight:400'>| Zonal Disparities</span></div>", unsafe_allow_html=True)
    
    e_col1, e_col2 = st.columns(2)
    
    with e_col1:
        # Dynamic chart based on filter selection
        if selected_country == 'All':
            # Show comparison by country
            st.markdown("**Municipal Coverage by Country**")
            
            country_cov = df_water.groupby('country').agg({
                'municipal_coverage': 'sum',
                'popn_total': 'sum'
            }).reset_index()
            
            country_cov['Coverage %'] = (country_cov['municipal_coverage'] / country_cov['popn_total'] * 100).fillna(0)
            
            fig_zone = px.bar(country_cov.sort_values('Coverage %'), x='Coverage %', y='country', orientation='h',
                              color='Coverage %', color_continuous_scale=[[0, '#fed7aa'], [0.5, '#fb923c'], [1, '#3b82f6']],
                              labels={'country': 'Country', 'Coverage %': 'Coverage (%)'})
            fig_zone.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0), xaxis_title="Municipal Coverage (%)")
            st.plotly_chart(fig_zone, use_container_width=True)
            
        elif selected_zone == 'All':
            # Show comparison by zone
            st.markdown("**Municipal Coverage by Zone**")
            
            zone_cov = df_w_filt.groupby('zone').agg({
                'municipal_coverage': 'sum',
                'popn_total': 'sum'
            }).reset_index()
            
            zone_cov['Coverage %'] = (zone_cov['municipal_coverage'] / zone_cov['popn_total'] * 100).fillna(0)
            
            fig_zone = px.bar(zone_cov.sort_values('Coverage %'), x='Coverage %', y='zone', orientation='h',
                              color='Coverage %', color_continuous_scale=[[0, '#fed7aa'], [0.5, '#fb923c'], [1, '#3b82f6']],
                              labels={'zone': 'Zone', 'Coverage %': 'Coverage (%)'})
            fig_zone.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0), xaxis_title="Municipal Coverage (%)")
            st.plotly_chart(fig_zone, use_container_width=True)
            
        else:
            # Show line chart for specific zone over time (2020-2024)
            st.markdown(f"**Municipal Coverage Trend - {selected_zone}**")
            
            zone_trend = df_water[df_water['zone'] == selected_zone].groupby('year').agg({
                'municipal_coverage': 'sum',
                'popn_total': 'sum'
            }).reset_index()
            
            zone_trend['Coverage %'] = (zone_trend['municipal_coverage'] / zone_trend['popn_total'] * 100).fillna(0)
            
            fig_zone = go.Figure()
            fig_zone.add_trace(go.Scatter(
                x=zone_trend['year'],
                y=zone_trend['Coverage %'],
                mode='lines+markers',
                line=dict(color='#3b82f6', width=3),
                marker=dict(size=8, color='#f97316'),
                fill='tozeroy',
                fillcolor='rgba(59, 130, 246, 0.1)',
                hovertemplate='<b>Year: %{x}</b><br>Coverage: %{y:.1f}%<extra></extra>'
            ))
            
            fig_zone.update_layout(
                height=350,
                margin=dict(l=0, r=0, t=0, b=0),
                xaxis=dict(
                    title="Year",
                    tickmode='linear',
                    dtick=1,
                    showgrid=True,
                    gridcolor='rgba(128,128,128,0.1)'
                ),
                yaxis=dict(
                    title="Municipal Coverage (%)",
                    showgrid=True,
                    gridcolor='rgba(128,128,128,0.1)',
                    range=[0, 100]
                ),
                plot_bgcolor='rgba(250,250,250,0.5)'
            )
            st.plotly_chart(fig_zone, use_container_width=True)

    with e_col2:
        st.markdown("**Pro-Poor Overlay: Coverage vs Vulnerability**")
        
        # Determine aggregation level based on filters
        if selected_country == 'All':
            # Aggregate by country
            if not df_water.empty and not df_fin.empty:
                # Water coverage by country
                country_cov = df_water.groupby('country').agg({
                    'municipal_coverage': 'sum',
                    'popn_total': 'sum'
                }).reset_index()
                country_cov['Coverage %'] = (country_cov['municipal_coverage'] / country_cov['popn_total'] * 100).fillna(0)
                
                # Pro-poor population by country
                country_fin = df_fin.groupby('country')['propoor_popn'].mean().reset_index()
                
                # Get total population by country from financial data for accurate percentage
                country_pop = df_water.groupby('country')['popn_total'].mean().reset_index()
                country_fin = pd.merge(country_fin, country_pop, on='country', how='inner')
                country_fin['Pro-Poor %'] = (country_fin['propoor_popn'] / country_fin['popn_total'] * 100).fillna(0)
                
                # Merge
                merged_equity = pd.merge(country_cov, country_fin[['country', 'Pro-Poor %', 'propoor_popn']], 
                                        on='country', how='inner')
                
                if not merged_equity.empty:
                    # Calculate priority score: high pro-poor % + low coverage = high priority
                    # Normalize both metrics to 0-1 scale, then create priority score
                    merged_equity['Priority Score'] = (merged_equity['Pro-Poor %'] / 100) * (1 - merged_equity['Coverage %'] / 100)
                    
                    fig_scatter = go.Figure()
                    fig_scatter.add_trace(go.Scatter(
                        x=merged_equity['Pro-Poor %'],
                        y=merged_equity['Coverage %'],
                        mode='markers+text',
                        marker=dict(
                            size=merged_equity['popn_total'] / 500000,  # Much smaller size scale
                            sizemode='diameter',
                            sizemin=4,
                            color=merged_equity['Priority Score'],
                            colorscale='RdYlBu_r',  # Red (high priority) to Blue (low priority)
                            showscale=True,
                            colorbar=dict(
                                title="Priority<br>Score",
                                tickmode="linear",
                                tick0=0,
                                dtick=0.2
                            ),
                            line=dict(width=1, color='white')
                        ),
                        text=merged_equity['country'],
                        textposition='top center',
                        textfont=dict(size=9),
                        customdata=merged_equity[['popn_total']],
                        hovertemplate='<b>%{text}</b><br>Pro-Poor: %{x:.1f}%<br>Coverage: %{y:.1f}%<br>Population: %{customdata[0]:,.0f}<br>Priority: %{marker.color:.2f}<extra></extra>'
                    ))
                    
                    fig_scatter.update_layout(
                        height=350,
                        margin=dict(l=0, r=0, t=0, b=0),
                        xaxis_title="Pro-Poor Population (%)",
                        yaxis_title="Municipal Coverage (%)",
                        xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.1)'),
                        yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.1)'),
                        plot_bgcolor='rgba(250,250,250,0.5)'
                    )
                    st.plotly_chart(fig_scatter, use_container_width=True)
                else:
                    st.info("Insufficient data overlap between Access and Financial datasets for Pro-Poor analysis.")
            else:
                st.info("No financial or access data available for Pro-Poor analysis.")
                
        else:
            # Aggregate by zone (when specific country or zone selected)
            # Need to map Zones to Cities to link with Financial Data (Pro-Poor)
            if not df_service.empty:
                zone_city_map = df_service[['zone', 'city']].drop_duplicates().set_index('zone')['city'].to_dict()
                
                # Add City to Water Data
                df_w_city = df_w_filt.copy()
                df_w_city['city'] = df_w_city['zone'].map(zone_city_map)
                
                # Aggregate Water Data by Zone
                zone_cov = df_w_filt.groupby('zone').agg({
                    'municipal_coverage': 'sum',
                    'popn_total': 'sum'
                }).reset_index()
                zone_cov['Coverage %'] = (zone_cov['municipal_coverage'] / zone_cov['popn_total'] * 100).fillna(0)
                zone_cov['city'] = zone_cov['zone'].map(zone_city_map)
                
                # Aggregate Financial Data by City (Pro-Poor Pop)
                if not df_f_filt.empty:
                    city_fin = df_f_filt.groupby('city')['propoor_popn'].mean().reset_index()
                    
                    # Merge
                    merged_equity = pd.merge(zone_cov, city_fin, on='city', how='inner')
                    
                    if not merged_equity.empty:
                        # Calculate Pro-Poor % (Pro-Poor Pop / Total Pop)
                        merged_equity['Pro-Poor %'] = (merged_equity['propoor_popn'] / merged_equity['popn_total'] * 100).fillna(0)
                        
                        # Calculate priority score: high pro-poor % + low coverage = high priority
                        merged_equity['Priority Score'] = (merged_equity['Pro-Poor %'] / 100) * (1 - merged_equity['Coverage %'] / 100)
                        
                        fig_scatter = go.Figure()
                        fig_scatter.add_trace(go.Scatter(
                            x=merged_equity['Pro-Poor %'],
                            y=merged_equity['Coverage %'],
                            mode='markers+text',
                            marker=dict(
                                size=merged_equity['popn_total'] / 100000,  # Much smaller size scale
                                sizemode='diameter',
                                sizemin=4,
                                color=merged_equity['Priority Score'],
                                colorscale='RdYlBu_r',  # Red (high priority) to Blue (low priority)
                                showscale=True,
                                colorbar=dict(
                                    title="Priority<br>Score",
                                    tickmode="linear",
                                    tick0=0,
                                    dtick=0.2
                                ),
                                line=dict(width=1, color='white')
                            ),
                            text=merged_equity['zone'],
                            textposition='top center',
                            textfont=dict(size=9),
                            customdata=merged_equity[['popn_total']],
                            hovertemplate='<b>%{text}</b><br>Pro-Poor: %{x:.1f}%<br>Coverage: %{y:.1f}%<br>Population: %{customdata[0]:,.0f}<br>Priority: %{marker.color:.2f}<extra></extra>'
                        ))
                        
                        fig_scatter.update_layout(
                            height=350,
                            margin=dict(l=0, r=0, t=0, b=0),
                            xaxis_title="Pro-Poor Population (%)",
                            yaxis_title="Municipal Coverage (%)",
                            xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.1)'),
                            yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.1)'),
                            plot_bgcolor='rgba(250,250,250,0.5)'
                        )
                        st.plotly_chart(fig_scatter, use_container_width=True)
                    else:
                        st.info("Insufficient data overlap between Service and Financial datasets for Pro-Poor analysis.")
                else:
                    st.info("No financial data available for Pro-Poor analysis.")
            else:
                st.info("Service data unavailable for mapping zones to cities.")

    # --- Step 5: Access Transition Report (Population Flow Summary) ---
    st.markdown("<div class='section-header'>📈 Access Transition Report <span style='font-size:14px;color:#6b7280;font-weight:400'>| Population Movement Analysis</span></div>", unsafe_allow_html=True)
    
    # Calculate population flow for water and sanitation
    # Get 2020 and 2024 data (or earliest and latest available years)
    flow_years = sorted(df_water['year'].unique())
    if len(flow_years) >= 2:
        start_year = flow_years[0]
        end_year = flow_years[-1]
        
        # Filter for start and end years
        df_w_start = df_water.copy()
        df_w_end = df_water.copy()
        df_s_start = df_sewer.copy()
        df_s_end = df_sewer.copy()
        
        # Apply country and zone filters
        if selected_country != 'All':
            df_w_start = df_w_start[df_w_start['country'] == selected_country]
            df_w_end = df_w_end[df_w_end['country'] == selected_country]
            df_s_start = df_s_start[df_s_start['country'] == selected_country]
            df_s_end = df_s_end[df_s_end['country'] == selected_country]
        if selected_zone != 'All':
            df_w_start = df_w_start[df_w_start['zone'] == selected_zone]
            df_w_end = df_w_end[df_w_end['zone'] == selected_zone]
            df_s_start = df_s_start[df_s_start['zone'] == selected_zone]
            df_s_end = df_s_end[df_s_end['zone'] == selected_zone]
        
        # Filter by year
        df_w_start = df_w_start[df_w_start['year'] == start_year]
        df_w_end = df_w_end[df_w_end['year'] == end_year]
        df_s_start = df_s_start[df_s_start['year'] == start_year]
        df_s_end = df_s_end[df_s_end['year'] == end_year]
        
        # Generate two-column flow report
        flow_col1, flow_col2 = st.columns(2)
        
        # WATER ACCESS COLUMN
        with flow_col1:
            if not df_w_start.empty and not df_w_end.empty:
                w_start_totals = df_w_start[w_ladder_cols].sum()
                w_end_totals = df_w_end[w_ladder_cols].sum()
                w_start_pop = df_w_start['popn_total'].sum()
                w_end_pop = df_w_end['popn_total'].sum()
                
                st.markdown(f"**💧 Water Access Flow ({start_year} → {end_year}):**")
                
                for col, label in zip(w_ladder_cols, w_ladder_labels):
                    start_pct = (w_start_totals[col] / w_start_pop * 100) if w_start_pop > 0 else 0
                    end_pct = (w_end_totals[col] / w_end_pop * 100) if w_end_pop > 0 else 0
                    pop_change = w_end_totals[col] - w_start_totals[col]
                    
                    # Format the change with color
                    if pop_change >= 0:
                        change_text = f":green[+{pop_change:,.0f} people]"
                    else:
                        change_text = f":red[{pop_change:,.0f} people]"
                    
                    st.markdown(f"**{label}** ({start_pct:.1f}% → {end_pct:.1f}%): {change_text}")
        
        # SANITATION ACCESS COLUMN
        with flow_col2:
            if not df_s_start.empty and not df_s_end.empty:
                s_start_totals = df_s_start[s_ladder_cols].sum()
                s_end_totals = df_s_end[s_ladder_cols].sum()
                s_start_pop = df_s_start['popn_total'].sum()
                s_end_pop = df_s_end['popn_total'].sum()
                
                st.markdown(f"**🚽 Sanitation Access Flow ({start_year} → {end_year}):**")
                
                for col, label in zip(s_ladder_cols, s_ladder_labels):
                    start_pct = (s_start_totals[col] / s_start_pop * 100) if s_start_pop > 0 else 0
                    end_pct = (s_end_totals[col] / s_end_pop * 100) if s_end_pop > 0 else 0
                    pop_change = s_end_totals[col] - s_start_totals[col]
                    
                    # Format the change with color
                    if pop_change >= 0:
                        change_text = f":green[+{pop_change:,.0f} people]"
                    else:
                        change_text = f":red[{pop_change:,.0f} people]"
                    
                    st.markdown(f"**{label}** ({start_pct:.1f}% → {end_pct:.1f}%): {change_text}")
    else:
        st.info("Need at least 2 years of data for population flow analysis")
