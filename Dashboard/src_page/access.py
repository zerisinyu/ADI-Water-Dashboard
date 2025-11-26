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

def create_sparkline(data, color='#3b82f6'):
    """Create a simple sparkline chart."""
    # Calculate dynamic range to highlight changes
    y_range = None
    if data:
        min_val = min(data)
        max_val = max(data)
        diff = max_val - min_val
        # Add padding to make the line not touch the edges
        padding = diff * 0.1 if diff > 0 else 1.0
        y_range = [min_val - padding, max_val + padding]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(len(data))), 
        y=data, 
        mode='lines', 
        line=dict(color=color, width=2),
        fill='tozeroy',
        fillcolor=f"rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.1)"
    ))
    fig.update_layout(
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, range=y_range),
        margin=dict(l=0, r=0, t=0, b=0),
        height=40,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

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

    # --- Header Section ---
    header_container = st.container()
    
    # Filters Row
    filt_c1, filt_c2, filt_c3, filt_c4 = st.columns([2, 2, 2, 2])
    
    with filt_c1:
        st.markdown("<label style='font-size: 12px; font-weight: 600; color: #374151;'>View Period</label>", unsafe_allow_html=True)
        view_type = st.radio("View Period", ["Annual", "Quarterly"], horizontal=True, label_visibility="collapsed", key="view_type_toggle")
        
    with filt_c2:
        # Country Filter
        countries = ['All'] + sorted(df_water['country'].unique().tolist()) if 'country' in df_water.columns else ['All']
        # Try to get default from session state if available
        default_country_idx = 0
        if "selected_country" in st.session_state and st.session_state.selected_country in countries:
            default_country_idx = countries.index(st.session_state.selected_country)
            
        selected_country = st.selectbox("Country", countries, index=default_country_idx, key="header_country_select")
        
    with filt_c3:
        # Zone Filter (dependent on country)
        if selected_country != 'All':
            zones = ['All'] + sorted(df_water[df_water['country'] == selected_country]['zone'].unique().tolist())
        else:
            zones = ['All'] + sorted(df_water['zone'].unique().tolist())
            
        default_zone_idx = 0
        if "selected_zone" in st.session_state and st.session_state.selected_zone in zones:
            default_zone_idx = zones.index(st.session_state.selected_zone)
            
        selected_zone = st.selectbox("Zone/City", zones, index=default_zone_idx, key="header_zone_select")
        
    with filt_c4:
        # Year Filter
        years = sorted(df_water['year'].unique().tolist(), reverse=True)
        default_year_idx = 0
        if "selected_year" in st.session_state and st.session_state.selected_year in years:
            default_year_idx = years.index(st.session_state.selected_year)
            
        selected_year = st.selectbox("Year", years, index=default_year_idx, key="header_year_select")

    # Map month name to number (for Service Data)
    selected_month_name = st.session_state.get("selected_month", "All")
    month_map = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    selected_month = month_map.get(selected_month_name) if selected_month_name != 'All' else 'All'

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

    # --- Populate Header with Export Button ---
    with header_container:
        h_col1, h_col2 = st.columns([6, 1])
        with h_col1:
            st.markdown("<h1 style='font-size: 24px; font-weight: 700; color: #111827; margin-bottom: 16px;'>Access & Coverage</h1>", unsafe_allow_html=True)
        with h_col2:
            st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True) # Spacer for alignment
            csv = df_w_filt.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Export CSV",
                data=csv,
                file_name=f"access_data_{selected_country}_{selected_year}.csv",
                mime="text/csv",
                key="export_btn"
            )

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

    # --- Step 1: Key Performance Scorecards Row ---
    st.markdown("<div class='section-header'>📊 Key Performance Scorecards</div>", unsafe_allow_html=True)

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

    # --- Additional Calculations for Scorecards ---
    
    # Sparkline Data (Water Coverage Trend - Annual)
    df_w_trend = df_water.copy()
    if selected_country != 'All': df_w_trend = df_w_trend[df_w_trend['country'] == selected_country]
    if selected_zone != 'All': df_w_trend = df_w_trend[df_w_trend['zone'] == selected_zone]
    
    w_trend_agg = df_w_trend.groupby('year').agg({'municipal_coverage': 'sum', 'popn_total': 'sum'}).reset_index().sort_values('year')
    w_trend_agg['pct'] = (w_trend_agg['municipal_coverage'] / w_trend_agg['popn_total'] * 100).fillna(0)
    water_spark_data = w_trend_agg['pct'].tolist()

    # Sparkline Data (Sanitation Coverage Trend - Monthly last 12 months)
    df_s_trend = df_service.copy()
    if selected_country != 'All': df_s_trend = df_s_trend[df_s_trend['country'] == selected_country]
    if selected_zone != 'All': df_s_trend = df_s_trend[df_s_trend['zone'] == selected_zone]
    
    # Group by date to get trend
    s_trend_agg = df_s_trend.groupby('date').agg({'sewer_connections': 'sum', 'households': 'max'}).reset_index().sort_values('date')
    # Take last 12 points
    s_trend_agg = s_trend_agg.tail(12)
    s_trend_agg['pct'] = (s_trend_agg['sewer_connections'] / s_trend_agg['households'].replace(0, 1) * 100).fillna(0)
    san_spark_data = s_trend_agg['pct'].tolist()

    # 3. Safely Managed Water Access
    safely_managed_pop = df_w_filt['w_safely_managed'].sum()
    safely_managed_pct = (safely_managed_pop / total_pop_w * 100) if total_pop_w > 0 else 0
    
    # YoY Change for Safely Managed
    if selected_year and selected_year > df_water['year'].min():
        last_year = selected_year - 1
        df_w_last_sm = df_water.copy()
        if selected_country != 'All': df_w_last_sm = df_w_last_sm[df_w_last_sm['country'] == selected_country]
        if selected_zone != 'All': df_w_last_sm = df_w_last_sm[df_w_last_sm['zone'] == selected_zone]
        df_w_last_sm = df_w_last_sm[df_w_last_sm['year'] == last_year]
        
        sm_pop_last = df_w_last_sm['w_safely_managed'].sum()
        total_pop_last = df_w_last_sm['popn_total'].sum()
        sm_pct_last = (sm_pop_last / total_pop_last * 100) if total_pop_last > 0 else 0
        sm_yoy_change = safely_managed_pct - sm_pct_last
    else:
        sm_yoy_change = 0
        
    # Sparkline Data (Safely Managed Trend - Annual)
    # Need to aggregate safely_managed for all years
    w_trend_agg_sm = df_w_trend.groupby('year').agg({'w_safely_managed': 'sum', 'popn_total': 'sum'}).reset_index().sort_values('year')
    w_trend_agg_sm['sm_pct'] = (w_trend_agg_sm['w_safely_managed'] / w_trend_agg_sm['popn_total'] * 100).fillna(0)
    sm_spark_data = w_trend_agg_sm['sm_pct'].tolist()

    # 4. Service Gap Alert (Unimproved + Surface Water)
    gap_pop = df_w_filt['w_unimproved'].sum() + df_w_filt['surface_water'].sum()
    gap_pct = (gap_pop / total_pop_w * 100) if total_pop_w > 0 else 0
    
    # Render Cards
    kpi_c1, kpi_c2, kpi_c3, kpi_c4 = st.columns(4)
    
    with kpi_c1:
        st.markdown(f"""
        <div class="metric-container">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div>
                    <div class="metric-label">Water Supply Coverage</div>
                    <div class="metric-value">{muni_supply_pct:.1f}%</div>
                </div>
                <div style="font-size: 24px;">🚰</div>
            </div>
            <div class="metric-delta">
                <span class="{'delta-up' if muni_yoy_growth >= 0 else 'delta-down'}">
                    {muni_yoy_growth:+.1f}%
                </span>
                <span style="color: #6b7280;">vs last year</span>
            </div>
            <div style="margin-top: 12px;"></div>
        </div>
        """, unsafe_allow_html=True)
        if water_spark_data:
            st.plotly_chart(create_sparkline(water_spark_data, "#3b82f6"), use_container_width=True, config={'displayModeBar': False})
        
    with kpi_c2:
        st.markdown(f"""
        <div class="metric-container">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div>
                    <div class="metric-label">Sanitation Coverage</div>
                    <div class="metric-value">{sewer_conn_pct:.1f}%</div>
                </div>
                <div style="font-size: 24px;">🚽</div>
            </div>
            <div class="metric-delta">
                <span class="{'delta-up' if sewer_growth >= 0 else 'delta-down'}">
                    {sewer_growth:+.1f}%
                </span>
                <span style="color: #6b7280;">vs last period</span>
            </div>
            <div style="margin-top: 12px;"></div>
        </div>
        """, unsafe_allow_html=True)
        if san_spark_data:
            st.plotly_chart(create_sparkline(san_spark_data, "#8b5cf6"), use_container_width=True, config={'displayModeBar': False})
        
    with kpi_c3:
        st.markdown(f"""
        <div class="metric-container">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div>
                    <div class="metric-label">Safely Managed Water</div>
                    <div class="metric-value">{safely_managed_pct:.1f}%</div>
                </div>
                <div style="font-size: 24px;">🛡️</div>
            </div>
            <div class="metric-delta">
                <span class="{'delta-up' if sm_yoy_change >= 0 else 'delta-down'}">
                    {sm_yoy_change:+.1f}%
                </span>
                <span style="color: #6b7280;">vs last year</span>
            </div>
            <div style="margin-top: 12px;"></div>
        </div>
        """, unsafe_allow_html=True)
        if sm_spark_data:
            st.plotly_chart(create_sparkline(sm_spark_data, "#10b981"), use_container_width=True, config={'displayModeBar': False})
        
    with kpi_c4:
        st.markdown(f"""
        <div class="metric-container" style="border-left: 4px solid #ef4444;">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div>
                    <div class="metric-label">Service Gap Alert</div>
                    <div class="metric-value" style="color: #ef4444;">{gap_pct:.1f}%</div>
                </div>
                <div style="font-size: 24px;">⚠️</div>
            </div>
            <div class="metric-delta">
                <span style="color: #ef4444; font-weight: 600;">{gap_pop/1000:.1f}K</span>
                <span style="color: #6b7280;">people affected</span>
            </div>
            <div style="margin-top: 12px; font-size: 10px; color: #6b7280; display: flex; align-items: center; gap: 4px;">
                <div style="flex-grow: 1; height: 2px; background: #e5e7eb; position: relative;">
                    <div style="position: absolute; right: 0; top: -3px; width: 2px; height: 8px; background: #10b981;"></div>
                </div>
                <span>SDG Goal: 0%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # --- Define ladder columns and labels (used by multiple sections) ---
    # Updated order: Safely Managed (Bottom) -> Open Def/Surface (Top)
    w_ladder_cols = ['w_safely_managed', 'w_basic', 'w_limited', 'w_unimproved', 'surface_water']
    w_ladder_labels = ['Safely Managed', 'Basic', 'Limited', 'Unimproved', 'Surface Water']
    s_ladder_cols = ['s_safely_managed', 's_basic', 's_limited', 's_unimproved', 'open_def']
    s_ladder_labels = ['Safely Managed', 'Basic', 'Limited', 'Unimproved', 'Open Defecation']

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
    
    # Color schemes - Updated based on requirements
    # Water: Safely Managed (Dark Blue) -> Basic (Med Blue) -> Limited (Light Blue) -> Unimproved (Orange) -> Surface (Red)
    water_colors = ['#2874A6', '#5DADE2', '#AED6F1', '#F8C471', '#E74C3C']
    # Sanitation: Safely Managed (Dark Green) -> Basic (Green) -> Limited (Light Green) -> Unimproved (Yellow) -> Open Def (Dark Red)
    sanitation_colors = ['#1E8449', '#58D68D', '#ABEBC6', '#F4D03F', '#C0392B']
    
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
            
            for idx, (col, label, color) in enumerate(zip(w_ladder_cols, w_ladder_labels, water_colors)):
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
            
            for idx, (col, label, color) in enumerate(zip(s_ladder_cols, s_ladder_labels, sanitation_colors)):
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
            
            for idx, (col, label, color) in enumerate(zip(w_ladder_cols, w_ladder_labels, water_colors)):
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
            
            for idx, (col, label, color) in enumerate(zip(s_ladder_cols, s_ladder_labels, sanitation_colors)):
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
                    marker_color=color,
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
            
            for idx, (col, label, color) in enumerate(zip(w_ladder_cols, w_ladder_labels, water_colors)):
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
            
            for idx, (col, label, color) in enumerate(zip(s_ladder_cols, s_ladder_labels, sanitation_colors)):
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
                    marker_color=color,
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
        
        # Add Benchmark Line at 100% if Percentage mode
        if display_mode == "Percentage":
            fig_ladder.add_shape(
                type="line",
                xref="paper",
                x0=0,
                y0=100,
                x1=1,
                y1=100,
                line=dict(color="Black", width=2, dash="dash"),
            )
            fig_ladder.add_annotation(
                xref="paper",
                x=0.05,
                y=100,
                yshift=10,
                text="SDG Target for Basic + Safely Managed (100%)",
                showarrow=False,
                font=dict(size=10, color="black")
            )

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
                groupclick="toggleitem",
                traceorder="reversed"
            ),
            hovermode='closest'
        )
    
    st.plotly_chart(fig_ladder, use_container_width=True)

    # --- Step 3: Coverage Growth Trends ---
    st.markdown("<div class='section-header'>📈 Coverage Growth Trends</div>", unsafe_allow_html=True)
    
    # Chart Controls
    trend_metric = st.radio(
        "Select Metric:", 
        ["Coverage (%)", "Growth Rate (%)", "Combined View"], 
        horizontal=True,
        key="trend_metric_selector",
        label_visibility="collapsed"
    )
    
    cg_col1, cg_col2 = st.columns([3, 1])
    
    with cg_col1:
        # Prepare Water Data (Annual -> Quarterly Interpolation)
        df_w_growth = df_water.copy()
        if selected_country != 'All': df_w_growth = df_w_growth[df_w_growth['country'] == selected_country]
        if selected_zone != 'All': df_w_growth = df_w_growth[df_w_growth['zone'] == selected_zone]
        
        w_annual = df_w_growth.groupby('year').agg({'municipal_coverage': 'sum', 'popn_total': 'sum'}).reset_index()
        # Assume annual data is end of year
        w_annual['date'] = pd.to_datetime(w_annual['year'].astype(str) + '-12-31')
        w_annual = w_annual.set_index('date').sort_index()
        
        # Prepare Sewer Data (Monthly -> Quarterly)
        df_s_growth = df_service.copy()
        if selected_country != 'All': df_s_growth = df_s_growth[df_s_growth['country'] == selected_country]
        if selected_zone != 'All': df_s_growth = df_s_growth[df_s_growth['zone'] == selected_zone]
        
        # Group by date first (sum across zones if multiple)
        s_monthly = df_s_growth.groupby('date').agg({'sewer_connections': 'sum', 'households': 'sum'}).reset_index()
        s_monthly = s_monthly.set_index('date').sort_index()
        
        if not w_annual.empty and not s_monthly.empty:
            # Create common quarterly index
            start_date = min(w_annual.index.min(), s_monthly.index.min())
            end_date = max(w_annual.index.max(), s_monthly.index.max())
            dates = pd.date_range(start=start_date, end=end_date, freq='Q')
            
            # Reindex and Interpolate Water
            # Reindex to include annual dates + quarterly dates
            w_combined_idx = w_annual.index.union(dates).sort_values()
            w_interp = w_annual.reindex(w_combined_idx)
            w_interp['municipal_coverage'] = w_interp['municipal_coverage'].interpolate(method='time')
            w_interp['popn_total'] = w_interp['popn_total'].interpolate(method='time')
            # Filter to just quarterly dates
            w_q = w_interp.reindex(dates)
            w_q['coverage_pct'] = (w_q['municipal_coverage'] / w_q['popn_total'] * 100).fillna(0)
            w_q['growth_rate'] = w_q['coverage_pct'].pct_change() * 100
            
            # Resample Sewer
            s_q = s_monthly.resample('Q').agg({'sewer_connections': 'last', 'households': 'last'})
            s_q['coverage_pct'] = (s_q['sewer_connections'] / s_q['households'] * 100).fillna(0)
            s_q['growth_rate'] = s_q['coverage_pct'].pct_change() * 100
            
            # Plot
            fig_growth = go.Figure()
            
            # Colors (using the new softer palette)
            color_water = '#2874A6' # Safely Managed Water color
            color_sewer = '#1E8449' # Safely Managed Sanitation color
            
            # Water Coverage
            if trend_metric in ["Coverage (%)", "Combined View"]:
                fig_growth.add_trace(go.Scatter(
                    x=w_q.index, y=w_q['coverage_pct'],
                    name='Water Coverage',
                    mode='lines',
                    line=dict(color=color_water, width=3, shape='spline'),
                    fill='tozeroy',
                    fillcolor='rgba(40, 116, 166, 0.1)',
                    hovertemplate='<b>Water Coverage</b><br>%{y:.1f}%<extra></extra>'
                ))
            
            # Sewer Coverage
            if trend_metric in ["Coverage (%)", "Combined View"]:
                fig_growth.add_trace(go.Scatter(
                    x=s_q.index, y=s_q['coverage_pct'],
                    name='Sewer Coverage',
                    mode='lines',
                    line=dict(color=color_sewer, width=3, shape='spline'),
                    fill='tozeroy',
                    fillcolor='rgba(30, 132, 73, 0.1)',
                    hovertemplate='<b>Sewer Coverage</b><br>%{y:.1f}%<extra></extra>'
                ))
            
            # Water Growth
            if trend_metric in ["Growth Rate (%)", "Combined View"]:
                yaxis_ref = 'y2' if trend_metric == "Combined View" else 'y'
                # Conditional colors: Light red for negative growth
                w_colors = [color_water if val >= 0 else '#F87171' for val in w_q['growth_rate']]
                
                fig_growth.add_trace(go.Bar(
                    x=w_q.index, y=w_q['growth_rate'],
                    name='Water Growth %',
                    marker_color=w_colors,
                    yaxis=yaxis_ref,
                    hovertemplate='<b>Water Growth</b><br>%{y:+.2f}%<extra></extra>'
                ))
            
            # Sewer Growth
            if trend_metric in ["Growth Rate (%)", "Combined View"]:
                yaxis_ref = 'y2' if trend_metric == "Combined View" else 'y'
                # Conditional colors: Light red for negative growth
                s_colors = [color_sewer if val >= 0 else '#F87171' for val in s_q['growth_rate']]
                
                fig_growth.add_trace(go.Bar(
                    x=s_q.index, y=s_q['growth_rate'],
                    name='Sewer Growth %',
                    marker_color=s_colors,
                    yaxis=yaxis_ref,
                    hovertemplate='<b>Sewer Growth</b><br>%{y:+.2f}%<extra></extra>'
                ))
            
            # Layout Updates
            layout_args = dict(
                title=dict(text=f"Trends: {trend_metric}", font=dict(size=16, color="#111827")),
                xaxis=dict(title="Time", showgrid=True, gridcolor='rgba(128,128,128,0.1)'),
                yaxis=dict(
                    title="Percentage (%)" if trend_metric != "Growth Rate (%)" else "Growth Rate (%)",
                    showgrid=True,
                    gridcolor='rgba(128,128,128,0.1)',
                    zeroline=False
                ),
                hovermode='x unified',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=400,
                margin=dict(l=0, r=0, t=50, b=0),
                plot_bgcolor='rgba(255,255,255,1)',
                paper_bgcolor='rgba(255,255,255,1)',
                barmode='group'
            )

            if trend_metric == "Combined View":
                layout_args['yaxis']['title'] = "Coverage (%)"
                layout_args['yaxis']['range'] = [0, 100]
                layout_args['yaxis2'] = dict(
                    title="Growth Rate (%)",
                    overlaying='y',
                    side='right',
                    showgrid=False,
                    zeroline=False
                )
            elif trend_metric == "Coverage (%)":
                 layout_args['yaxis']['range'] = [0, 100]

            fig_growth.update_layout(**layout_args)
            
            st.plotly_chart(fig_growth, use_container_width=True)
        else:
            st.info("Insufficient data for growth trends.")
            
    with cg_col2:
        st.markdown("""
        <div style="background-color: #f9fafb; padding: 16px; border-radius: 8px; height: 100%;">
            <h4 style="margin-top: 0; color: #111827;">Analysis Notes</h4>
            <p style="font-size: 12px; color: #4b5563;">
                <strong>Water Coverage:</strong> Interpolated from annual data points. Growth rate reflects year-over-year trends smoothed quarterly.
            </p>
            <p style="font-size: 12px; color: #4b5563;">
                <strong>Sewer Coverage:</strong> Derived from monthly connection data. Growth rate shows quarter-over-quarter expansion.
            </p>
            <p style="font-size: 12px; color: #4b5563;">
                <strong>Growth Rate:</strong> Calculated as percentage change in coverage relative to the previous quarter.
            </p>
        </div>
        """, unsafe_allow_html=True)

    # --- Step 4: Infrastructure Metrics Row ---
    st.markdown("<div class='section-header'>🏗️ Infrastructure Metrics</div>", unsafe_allow_html=True)
    
    inf_c1, inf_c2, inf_c3 = st.columns(3)
    
    with inf_c1:
        st.markdown("**Metering Status**")
        # Simulated Data for Metering
        meter_fig = go.Figure(data=[go.Pie(
            labels=['Metered', 'Non-metered'], 
            values=[65, 35], 
            hole=.6,
            marker_colors=['#3B82F6', '#9CA3AF'],
            textinfo='none'
        )])
        meter_fig.update_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
            margin=dict(l=20, r=20, t=0, b=20),
            height=200,
            annotations=[dict(
                text="⚠️ No data available<br>for metered connections",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=10, color="#854d0e"),
                bgcolor="#fef9c3",
                bordercolor="#facc15",
                borderwidth=1,
                borderpad=4
            )]
        )
        meter_fig.update_traces(opacity=0.3, hoverinfo='skip')
        st.plotly_chart(meter_fig, use_container_width=True)
        # st.warning("⚠️ No data available for metered connections")

    with inf_c2:
        st.markdown("**Public Sanitation**")
        # Real Data Calculation
        if not df_svc_filt.empty and 'public_toilets' in df_svc_filt.columns:
            # Get latest public toilets count per zone
            pt_by_zone = df_svc_filt.groupby('zone')['public_toilets'].max().reset_index()
            total_toilets = pt_by_zone['public_toilets'].sum()
            
            # Population from water data (annual)
            pop_by_zone = df_w_filt.groupby('zone')['popn_total'].sum().reset_index()
            total_pop = pop_by_zone['popn_total'].sum()
            
            if total_pop > 0:
                # Toilets per 100,000 people
                toilets_per_capita = (total_toilets / total_pop) * 100000
                
                st.metric("Safely Managed Public Toilets", f"{toilets_per_capita:.1f}", "per 100k people")
                
                # Comparison Chart
                pt_merged = pd.merge(pt_by_zone, pop_by_zone, on='zone')
                pt_merged['per_100k'] = (pt_merged['public_toilets'] / pt_merged['popn_total'] * 100000).fillna(0)
                
                fig_pt = px.bar(
                    pt_merged, 
                    x='zone', 
                    y='per_100k',
                    color='per_100k',
                    color_continuous_scale=['#ef4444', '#eab308', '#22c55e'],
                    labels={'per_100k': 'Toilets/100k', 'zone': 'Zone'}
                )
                fig_pt.update_layout(
                    height=180, 
                    margin=dict(l=0, r=0, t=0, b=0),
                    xaxis_title=None,
                    yaxis_title="Per 100k",
                    coloraxis_showscale=False,
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_pt, use_container_width=True)
            else:
                st.info("Population data unavailable")
        else:
            st.info("⚠️ Data collection in progress")

    with inf_c3:
        st.markdown("**Service Provider Status**")
        # Simulated Data for Providers
        prov_fig = go.Figure(data=[go.Pie(
            labels=['Active', 'Inactive'], 
            values=[12, 4], 
            hole=.6,
            marker_colors=['#22C55E', '#EF4444'],
            textinfo='none'
        )])
        prov_fig.update_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
            margin=dict(l=20, r=20, t=0, b=20),
            height=200,
            annotations=[dict(
                text="⚠️ No data available<br>for service providers",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=10, color="#854d0e"),
                bgcolor="#fef9c3",
                bordercolor="#facc15",
                borderwidth=1,
                borderpad=4
            )]
        )
        prov_fig.update_traces(opacity=0.3, hoverinfo='skip')
        st.plotly_chart(prov_fig, use_container_width=True)
        
        st.markdown("""
        <div style="opacity: 0.4; filter: blur(1px); margin-top: -10px;">
            <p style="font-size: 11px; margin-bottom: 2px;"><strong>Top 5 Providers (Simulated):</strong></p>
            <ul style="font-size: 10px; padding-left: 14px; margin: 0; color: #6b7280;">
                <li>AquaServe Ltd</li>
                <li>City Water Co</li>
                <li>EcoSan Services</li>
                <li>Zone A Utility</li>
                <li>Global Water</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    # --- Step 5: The Equity Check (Zonal Disparities) ---
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
        st.markdown("**Access Disparities: Urban/Rural & Income Levels**")
        
        # Prepare Data for Classification
        if not df_w_filt.empty:
            equity_df = df_w_filt.copy()
            
            # Merge with Sewer data if available
            if not df_s_filt.empty:
                # Select relevant columns from sewer
                s_cols = df_s_filt[['zone', 's_basic_pct', 's_safely_managed_pct']]
                equity_df = pd.merge(equity_df, s_cols, on='zone', how='left')
            else:
                equity_df['s_basic_pct'] = 0
                equity_df['s_safely_managed_pct'] = 0
            
            # Calculate Access Metrics (Basic + Safely Managed)
            equity_df['Water Access'] = equity_df['w_basic_pct'] + equity_df['w_safely_managed_pct']
            equity_df['Sanitation Access'] = equity_df['s_basic_pct'].fillna(0) + equity_df['s_safely_managed_pct'].fillna(0)
            
            # --- Classification Logic ---
            
            # 1. Urban vs Rural
            # Heuristic: Municipal Coverage > 40% -> Urban, else Rural
            equity_df['muni_pct'] = (equity_df['municipal_coverage'] / equity_df['popn_total'] * 100).fillna(0)
            equity_df['Area Type'] = equity_df['muni_pct'].apply(lambda x: 'Urban' if x > 40 else 'Rural')
            
            # 2. Low Income vs Average Income
            # Heuristic: Use Financial Data (Pro-Poor) if available, else Unimproved Water proxy
            income_source = "Proxy (Unimproved Water > 20%)"
            has_financial_data = False
            
            if not df_service.empty and not df_fin.empty:
                try:
                    # Map Zone to City
                    zone_city_map = df_service[['zone', 'city']].drop_duplicates().set_index('zone')['city'].to_dict()
                    equity_df['city'] = equity_df['zone'].map(zone_city_map)
                    
                    # Get City Pro-Poor Data
                    city_propoor = df_fin.groupby('city')['propoor_popn'].mean().reset_index()
                    
                    # We need City Total Pop to calculate %
                    # Sum zone populations for each city
                    city_pop = equity_df.groupby('city')['popn_total'].sum().reset_index()
                    
                    city_income = pd.merge(city_propoor, city_pop, on='city')
                    city_income['propoor_pct'] = (city_income['propoor_popn'] / city_income['popn_total'] * 100).fillna(0)
                    
                    # Define Threshold (e.g., Median Pro-Poor %)
                    threshold = city_income['propoor_pct'].median()
                    if pd.isna(threshold): threshold = 20 # Default
                    
                    # Map back to Equity DF
                    equity_df = pd.merge(equity_df, city_income[['city', 'propoor_pct']], on='city', how='left')
                    
                    def classify_income(row):
                        if pd.isna(row['propoor_pct']):
                            # Fallback for zones without city map
                            return 'Low Income' if (row['w_unimproved_pct'] + row['surface_water_pct']) > 20 else 'Average Income'
                        return 'Low Income' if row['propoor_pct'] > threshold else 'Average Income'
                        
                    equity_df['Income Level'] = equity_df.apply(classify_income, axis=1)
                    income_source = f"Financial Data (Pro-Poor > {threshold:.1f}%)"
                    has_financial_data = True
                except Exception:
                    pass
            
            if not has_financial_data:
                # Fallback: Low Income if Unimproved + Surface > 20%
                equity_df['Income Level'] = equity_df.apply(
                    lambda x: 'Low Income' if (x['w_unimproved_pct'] + x['surface_water_pct']) > 20 else 'Average Income', 
                    axis=1
                )
            
            # --- Aggregation ---
            # Group by Area Type and Income Level
            grouped_list = []
            for (area, income), group in equity_df.groupby(['Area Type', 'Income Level']):
                pop_sum = group['popn_total'].sum()
                if pop_sum > 0:
                    w_avg = (group['Water Access'] * group['popn_total']).sum() / pop_sum
                    s_avg = (group['Sanitation Access'] * group['popn_total']).sum() / pop_sum
                else:
                    w_avg = 0
                    s_avg = 0
                grouped_list.append({
                    'Area Type': area,
                    'Income Level': income,
                    'Water Access': w_avg,
                    'Sanitation Access': s_avg,
                    'Population': pop_sum
                })
            grouped = pd.DataFrame(grouped_list)
            
            # --- Visualization ---
            fig_grouped = go.Figure()
            
            # Define categories for X-axis
            categories = []
            water_vals = []
            san_vals = []
            
            # Ensure all combinations exist
            for area in ['Rural', 'Urban']:
                for inc in ['Low Income', 'Average Income']:
                    label = f"{area}<br>{inc}"
                    if not grouped.empty:
                        row = grouped[(grouped['Area Type'] == area) & (grouped['Income Level'] == inc)]
                        val_w = row['Water Access'].values[0] if not row.empty else 0
                        val_s = row['Sanitation Access'].values[0] if not row.empty else 0
                    else:
                        val_w, val_s = 0, 0
                    
                    categories.append(label)
                    water_vals.append(val_w)
                    san_vals.append(val_s)
            
            # Water Trace
            fig_grouped.add_trace(go.Bar(
                name='Water (Basic+)',
                x=categories,
                y=water_vals,
                marker_color='#3b82f6',
                text=[f"{v:.1f}%" for v in water_vals],
                textposition='auto'
            ))
            
            # Sanitation Trace
            fig_grouped.add_trace(go.Bar(
                name='Sanitation (Basic+)',
                x=categories,
                y=san_vals,
                marker_color='#10b981',
                text=[f"{v:.1f}%" for v in san_vals],
                textposition='auto'
            ))
            
            # Add Gap Analysis Text (Annotation)
            try:
                best_w = max(water_vals)
                worst_w = min([v for v in water_vals if v > 0] or [0])
                gap_w = best_w - worst_w
                
                fig_grouped.add_annotation(
                    x=0.5, y=1.15,
                    xref="paper", yref="paper",
                    text=f"<b>Gap Analysis:</b> Max disparity is <b>{gap_w:.1f}%</b> in Water Access",
                    showarrow=False,
                    font=dict(size=12, color="#ef4444"),
                    bgcolor="#fee2e2",
                    bordercolor="#ef4444",
                    borderwidth=1,
                    borderpad=4
                )
            except:
                pass

            fig_grouped.update_layout(
                barmode='group',
                height=350,
                margin=dict(l=0, r=0, t=40, b=0),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                yaxis=dict(title="Access (%)", range=[0, 100]),
                plot_bgcolor='rgba(250,250,250,0.5)'
            )
            
            st.plotly_chart(fig_grouped, use_container_width=True)
            
            # Methodology Note
            st.markdown(f"""
            <div style='font-size:11px; color:#6b7280; background-color:#f9fafb; padding:8px; border-radius:4px;'>
            <b>Methodology:</b><br>
            • <b>Urban/Rural:</b> Classified based on Municipal Water Coverage (>40% = Urban).<br>
            • <b>Income Level:</b> {income_source}.<br>
            • <b>Access Metric:</b> Population with at least Basic service level.
            </div>
            """, unsafe_allow_html=True)
            
        else:
            st.info("No data available for Equity Analysis.")

    # --- Step 6: Access Transition Report (Population Flow Summary) ---
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

    # --- Step 8: Data Quality & Alerts Section (Footer) ---
    st.markdown("---")
    st.markdown("<div class='section-header'>⚠️ Data Quality & Alerts</div>", unsafe_allow_html=True)
    
    # Define alerts (based on known data gaps in current dashboard version)
    alerts = [
        "⚠️ Metered connections data unavailable",
        "⚠️ Active service provider count pending"
    ]
    
    # Check if Financial Data is missing (used for Low-Income classification)
    if df_fin.empty or 'propoor_popn' not in df_fin.columns:
        alerts.append("⚠️ Low-income area classification in progress")
    
    if alerts:
        st.markdown(f"""
        <div style='background-color: #fefce8; border: 1px solid #fde047; border-radius: 8px; padding: 16px; margin-bottom: 16px;'>
            <h4 style='color: #854d0e; margin-top: 0; font-size: 16px; margin-bottom: 8px;'>Data Gaps Detected</h4>
            <ul style='color: #a16207; margin-bottom: 0; padding-left: 20px;'>
                {''.join([f"<li style='margin-bottom: 4px;'>{alert}</li>" for alert in alerts])}
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
    # Footer with Timestamp and Sources
    st.markdown(f"""
    <div style='font-size: 12px; color: #6b7280; margin-top: 24px; border-top: 1px solid #e5e7eb; padding-top: 16px;'>
        <div style='display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;'>
            <div>
                <strong>Data Sources:</strong> Utility Master Database, National Census (2020), Municipal Records
            </div>
            <div>
                <strong>Last Updated:</strong> {pd.Timestamp.now().strftime('%Y-%m-%d')}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
