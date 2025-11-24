import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import DATA_DIR

@st.cache_data
def load_production_data():
    """Load production data for the dashboard."""
    prod_path = DATA_DIR / "production.csv"
    df_prod = pd.DataFrame()
    
    if prod_path.exists():
        try:
            df_prod = pd.read_csv(prod_path)
            
            # Ensure numeric columns
            cols_to_numeric = ['production_m3', 'service_hours']
            for col in cols_to_numeric:
                if col in df_prod.columns:
                    if df_prod[col].dtype == 'object':
                        df_prod[col] = df_prod[col].astype(str).str.replace(r'[$,]', '', regex=True)
                    df_prod[col] = pd.to_numeric(df_prod[col], errors='coerce').fillna(0)

            # Date parsing
            if 'date_YYMMDD' in df_prod.columns:
                df_prod['date_dt'] = pd.to_datetime(df_prod['date_YYMMDD'], format='%Y/%m/%d', errors='coerce')
            elif 'date' in df_prod.columns:
                df_prod['date_dt'] = pd.to_datetime(df_prod['date'], errors='coerce')
                
            if 'date_dt' in df_prod.columns:
                df_prod['year'] = df_prod['date_dt'].dt.year.astype('Int64')  # Convert to Int64 for consistency
                df_prod['month'] = df_prod['date_dt'].dt.month.astype('Int64')
                df_prod['day'] = df_prod['date_dt'].dt.day.astype('Int64')
        except Exception as e:
            st.error(f"Error loading production data: {e}")
            
    return df_prod

def scene_production():
    """
    Production Manager Dashboard - Redesigned.
    Focus: Plant Uptime, Extraction Optimization, Source Sustainability.
    """
    # --- CSS Styling (Consistent with other pages) ---
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
        .metric-sub {
            font-size: 12px;
            color: #6b7280;
            margin-top: 4px;
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
        .alert-box {
            background-color: #fef2f2;
            border: 1px solid #fee2e2;
            border-radius: 6px;
            padding: 12px;
            color: #991b1b;
            font-size: 14px;
            margin-bottom: 16px;
        }
    </style>
    """, unsafe_allow_html=True)

    # --- Load Data ---
    df_prod = load_production_data()
    
    if df_prod.empty:
        st.warning("⚠️ Production data not available.")
        return

    # --- Filters (from Session State) ---
    selected_country = st.session_state.get("selected_country", "All")
    selected_year = st.session_state.get("selected_year")
    selected_month_name = st.session_state.get("selected_month", "All")

    month_map = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    selected_month = month_map.get(selected_month_name) if selected_month_name != 'All' else 'All'

    # --- Apply Filters ---
    df_p_filt = df_prod.copy()
    
    # Debug: Show available data info
    if 'date_dt' not in df_p_filt.columns:
        st.error("Date column not properly parsed. Please check the data format.")
        return
    
    # Remove rows with invalid dates
    df_p_filt = df_p_filt.dropna(subset=['date_dt'])
    
    if df_p_filt.empty:
        st.warning("No valid data after parsing dates.")
        return
    
    # Apply filters
    if selected_country != 'All' and 'country' in df_p_filt.columns:
        # Case-insensitive country comparison
        df_p_filt = df_p_filt[df_p_filt['country'].str.lower() == selected_country.lower()]
    if selected_year and 'year' in df_p_filt.columns:
        # Ensure year comparison uses same type
        df_p_filt = df_p_filt[df_p_filt['year'] == int(selected_year)]
    if selected_month != 'All' and 'month' in df_p_filt.columns:
        df_p_filt = df_p_filt[df_p_filt['month'] == int(selected_month)]

    if df_p_filt.empty:
        st.warning(f"No data available for the selected filters: Country={selected_country}, Year={selected_year}, Month={selected_month_name}")
        st.info(f"Available countries: {', '.join(df_prod['country'].unique().tolist())}")
        st.info(f"Available years: {', '.join(map(str, sorted(df_prod['year'].dropna().unique().tolist())))}")
        return

    # --- Step 1: The "Morning Output" Check (Scorecard) ---
    st.markdown("<div class='section-header'>☀️ Morning Output Check <span style='font-size:14px;color:#6b7280;font-weight:400'>| Daily Volumes</span></div>", unsafe_allow_html=True)

    # Calculations
    # Latest Date in Filtered Data (or "Yesterday" context)
    latest_date = df_p_filt['date_dt'].max()
    if pd.isna(latest_date):
        st.error("No valid dates found in the filtered data.")
        return
    df_latest = df_p_filt[df_p_filt['date_dt'] == latest_date]
    
    # 1. Total Production (Latest Day)
    total_prod_latest = df_latest['production_m3'].sum()
    
    # 2. Avg Service Hours (Latest Day)
    avg_svc_hours = df_latest['service_hours'].mean() if not df_latest.empty else 0
    
    # 3. Active Sources
    active_sources = df_latest[df_latest['production_m3'] > 0]['source'].nunique()
    total_sources_count = df_p_filt['source'].nunique()
    
    # 4. Design Capacity Utilization
    # Estimate capacity as max production observed per source in the filtered period * 1.1 (buffer)
    # This is a heuristic since we don't have the static capacity table.
    estimated_capacity_per_source = df_p_filt.groupby('source')['production_m3'].max() * 1.1
    total_estimated_capacity = estimated_capacity_per_source.sum()
    
    # Utilization for latest day
    # We need to sum capacity only for sources that exist in latest day? 
    # Or total system capacity? Usually total system capacity.
    cap_utilization = (total_prod_latest / total_estimated_capacity * 100) if total_estimated_capacity > 0 else 0

    # Render Scorecard
    sc1, sc2, sc3, sc4 = st.columns(4)
    
    with sc1:
        st.markdown(f"""
        <div class='metric-container'>
            <div class='metric-label'>Total Production</div>
            <div class='metric-value'>{total_prod_latest:,.0f}</div>
            <div class='metric-sub'>m³ on {latest_date.strftime('%b %d')}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with sc2:
        # Color code service hours
        svc_color = "delta-up" if avg_svc_hours >= 20 else ("delta-neutral" if avg_svc_hours >= 12 else "delta-down")
        st.markdown(f"""
        <div class='metric-container'>
            <div class='metric-label'>Avg Service Hours</div>
            <div class='metric-value'>{avg_svc_hours:.1f}</div>
            <div class='metric-delta {svc_color}'>Target: 24h</div>
        </div>
        """, unsafe_allow_html=True)
        
    with sc3:
        st.markdown(f"""
        <div class='metric-container'>
            <div class='metric-label'>Active Sources</div>
            <div class='metric-value'>{active_sources} <span style='font-size:16px;color:#6b7280'>/ {total_sources_count}</span></div>
            <div class='metric-sub'>Online Yesterday</div>
        </div>
        """, unsafe_allow_html=True)
        
    with sc4:
        util_color = "delta-up" if cap_utilization < 90 else "delta-down" # >90% might be straining
        st.markdown(f"""
        <div class='metric-container'>
            <div class='metric-label'>Capacity Utilization</div>
            <div class='metric-value'>{cap_utilization:.1f}%</div>
            <div class='metric-sub'>of Design Capacity (Est.)</div>
        </div>
        """, unsafe_allow_html=True)

    # Alerts
    low_svc_sources = df_latest[df_latest['service_hours'] < 12]['source'].tolist()
    if low_svc_sources:
        st.markdown(f"""
        <div class='alert-box'>
            ⚠️ <strong>Low Supply Alert:</strong> The following sources had less than 12 hours of service yesterday: {', '.join(low_svc_sources)}
        </div>
        """, unsafe_allow_html=True)

    # --- Step 2: The Source Balancing Act (Extraction Analysis) ---
    st.markdown("<div class='section-header'>⚖️ Source Balancing Act <span style='font-size:14px;color:#6b7280;font-weight:400'>| Extraction Analysis</span></div>", unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("**Production Mix (Filtered Period)**")
        # Group by date and source
        daily_prod = df_p_filt.groupby(['date_dt', 'source'])['production_m3'].sum().reset_index()
        
        if daily_prod.empty:
            st.info("No production data available for visualization.")
        else:
            fig_mix = px.area(daily_prod, x='date_dt', y='production_m3', color='source',
                              labels={'production_m3': 'Volume (m³)', 'date_dt': 'Date'},
                              color_discrete_sequence=px.colors.qualitative.Safe)
            fig_mix.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0), legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig_mix, use_container_width=True)
        
    with c2:
        st.markdown("**Source Performance Leaderboard**")
        # Aggregated stats
        source_stats = df_p_filt.groupby('source').agg({
            'production_m3': 'sum',
            'service_hours': 'mean'
        }).reset_index()
        
        if source_stats.empty:
            st.info("No source performance data available.")
        else:
            fig_perf = px.bar(source_stats, x='production_m3', y='source', 
                              color='service_hours',
                              title="Total Volume vs Avg Service Hours",
                              labels={'production_m3': 'Total Volume (m³)', 'service_hours': 'Avg Hours/Day'},
                              color_continuous_scale='RdYlGn',
                              orientation='h')
            fig_perf.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_perf, use_container_width=True)

    # --- Step 3: The Intermittency Investigation (Reliability) ---
    st.markdown("<div class='section-header'>🔌 Intermittency Investigation <span style='font-size:14px;color:#6b7280;font-weight:400'>| Service Reliability</span></div>", unsafe_allow_html=True)
    
    st.markdown("**Service Hours Heatmap**")
    # Pivot for heatmap
    # X = Day of Month (or Date), Y = Source
    
    # If data spans multiple months, X should be Date.
    heatmap_data = df_p_filt.pivot_table(index='source', columns='date_dt', values='service_hours', aggfunc='mean')
    
    if heatmap_data.empty or heatmap_data.shape[0] == 0:
        st.info("No service hours data available for heatmap.")
    else:
        fig_heat = go.Figure(data=go.Heatmap(
            z=heatmap_data.values,
            x=heatmap_data.columns,
            y=heatmap_data.index,
            colorscale='RdYlGn', # Red to Green
            zmin=0, zmax=24,
            colorbar=dict(title='Hours')
        ))
        
        fig_heat.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig_heat, use_container_width=True)

    # --- Step 4: Strategic Planning (Resource Availability) ---
    st.markdown("<div class='section-header'>🔭 Strategic Planning <span style='font-size:14px;color:#6b7280;font-weight:400'>| Resource Sustainability</span></div>", unsafe_allow_html=True)
    
    sp1, sp2 = st.columns([1, 2])
    
    with sp1:
        # Resource Extraction Rate
        # Simulated Resource Limit (e.g., 1.5x total annual production of the max year)
        # In reality, this comes from 'water_resources' in national accounts.
        total_annual_prod = df_p_filt['production_m3'].sum()
        
        # Placeholder for Total Renewable Resources
        # Assuming a value for demo purposes if not available
        estimated_resources = total_annual_prod * 1.45 
        
        extraction_rate = (total_annual_prod / estimated_resources * 100) if estimated_resources > 0 else 0
        
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = extraction_rate,
            title = {'text': "Resource Extraction Rate"},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "#3b82f6"},
                'steps': [
                    {'range': [0, 70], 'color': "#d1fae5"},
                    {'range': [70, 90], 'color': "#fed7aa"},
                    {'range': [90, 100], 'color': "#fee2e2"}],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90}}))
        
        fig_gauge.update_layout(height=250, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_gauge, use_container_width=True)
        st.caption("*Note: Resource limit estimated for demonstration.*")

    with sp2:
        st.markdown("**Downtime Logger**")
        with st.form("downtime_log"):
            c_log1, c_log2 = st.columns(2)
            with c_log1:
                log_date = st.date_input("Date")
                log_source = st.selectbox("Source", df_p_filt['source'].unique())
            with c_log2:
                log_reason = st.selectbox("Reason", ["Power Outage", "Pump Failure", "Pipe Burst", "Chemical Shortage", "Maintenance", "Other"])
                log_duration = st.number_input("Duration (Hours)", min_value=0.0, max_value=24.0, step=0.5)
            
            log_notes = st.text_area("Additional Notes")
            
            submitted = st.form_submit_button("Log Downtime Event")
            if submitted:
                st.success(f"Logged: {log_source} - {log_reason} on {log_date}")

