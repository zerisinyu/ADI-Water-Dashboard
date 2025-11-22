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

    # --- Step 1: The "SDG" Check (Strategic Targets) ---
    st.markdown("<div class='section-header'>🎯 SDG Check <span style='font-size:14px;color:#6b7280;font-weight:400'>| Strategic Targets</span></div>", unsafe_allow_html=True)

    # Calculations
    # 1. Municipal Water Coverage
    # Assuming municipal_coverage is a count of people covered
    total_pop_w = df_w_filt['popn_total'].sum()
    muni_cov_count = df_w_filt['municipal_coverage'].sum()
    muni_cov_rate = (muni_cov_count / total_pop_w * 100) if total_pop_w > 0 else 0

    # 2. Safely Managed Water
    safely_managed_w_count = df_w_filt['w_safely_managed'].sum()
    safely_managed_w_rate = (safely_managed_w_count / total_pop_w * 100) if total_pop_w > 0 else 0

    # 3. Open Defecation Rate
    total_pop_s = df_s_filt['popn_total'].sum()
    open_def_count = df_s_filt['open_def'].sum()
    open_def_rate = (open_def_count / total_pop_s * 100) if total_pop_s > 0 else 0

    # 4. Sewer Connections
    # Service data is monthly. We should take the latest snapshot for each zone/city in the selected year.
    # Or if we filtered by year, we can take the max value per zone (assuming growth).
    if not df_svc_filt.empty:
        # Group by zone and take max sewer_connections and max households (to be safe)
        svc_agg = df_svc_filt.groupby(['zone']).agg({
            'sewer_connections': 'max',
            'households': 'max'
        }).reset_index()
        total_sewer_conn = svc_agg['sewer_connections'].sum()
        total_hh = svc_agg['households'].sum()
        sewer_conn_rate = (total_sewer_conn / total_hh * 100) if total_hh > 0 else 0
    else:
        sewer_conn_rate = 0

    # Render Scorecard
    sc1, sc2, sc3, sc4 = st.columns(4)
    
    metrics = [
        ("Municipal Water Coverage", f"{muni_cov_rate:.1f}%", 75, "%"), # Target example
        ("Safely Managed Water", f"{safely_managed_w_rate:.1f}%", 50, "%"),
        ("Open Defecation Rate", f"{open_def_rate:.1f}%", 0, "%"), # Target 0
        ("Sewer Connections", f"{sewer_conn_rate:.1f}%", 15, "%")
    ]
    
    for col, (label, value, target, unit) in zip([sc1, sc2, sc3, sc4], metrics):
        val_num = float(value.strip('%'))
        delta = val_num - target
        
        # For Open Defecation, lower is better
        if "Open Defecation" in label:
            delta_cls = "delta-up" if delta <= 0 else "delta-down" # Green if below target (0)
            icon = "↓" if delta <= 0 else "↑"
        else:
            delta_cls = "delta-up" if delta >= 0 else "delta-down"
            icon = "↑" if delta >= 0 else "↓"
            
        with col:
            st.markdown(f"""
            <div class='metric-container'>
                <div class='metric-label'>{label}</div>
                <div class='metric-value'>{value}</div>
                <div class='metric-delta {delta_cls}'>
                    {icon} {abs(delta):.1f}{unit} vs Target
                </div>
            </div>
            """, unsafe_allow_html=True)

    # --- Step 2: The "Ladder" Analysis (Quality of Access) ---
    st.markdown("<div class='section-header'>🪜 Ladder Analysis <span style='font-size:14px;color:#6b7280;font-weight:400'>| Quality of Access</span></div>", unsafe_allow_html=True)
    
    l_col1, l_col2 = st.columns(2)
    
    with l_col1:
        st.markdown("**Water Access Ladder**")
        
        # Aggregate counts for the ladder
        w_ladder_cols = ['surface_water', 'w_unimproved', 'w_limited', 'w_basic', 'w_safely_managed']
        w_ladder_labels = ['Surface Water', 'Unimproved', 'Limited', 'Basic', 'Safely Managed']
        w_colors = ['#ef4444', '#f97316', '#eab308', '#60a5fa', '#1e3a8a'] # Red, Orange, Yellow, Light Blue, Dark Blue
        
        w_agg = df_w_filt[w_ladder_cols].sum().reset_index()
        w_agg.columns = ['Category', 'Count']
        w_agg['Category'] = w_agg['Category'].replace(dict(zip(w_ladder_cols, w_ladder_labels)))
        
        # Calculate percentages for display
        total_w = w_agg['Count'].sum()
        w_agg['Percentage'] = (w_agg['Count'] / total_w * 100) if total_w > 0 else 0
        
        # Create stacked bar (single bar)
        # To make a stacked bar, we need a dummy x-axis or just use 'Category' as color and a single X
        w_agg['Type'] = 'Water Access'
        
        fig_w = px.bar(w_agg, x='Type', y='Percentage', color='Category', 
                       color_discrete_map=dict(zip(w_ladder_labels, w_colors)),
                       category_orders={'Category': w_ladder_labels[::-1]}, # Reverse order for stack
                       text=w_agg['Percentage'].apply(lambda x: f"{x:.1f}%"))
        
        fig_w.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0), xaxis_title=None, yaxis_title="Percentage (%)")
        st.plotly_chart(fig_w, use_container_width=True)

    with l_col2:
        st.markdown("**Sanitation Access Ladder**")
        
        # Aggregate counts for the ladder
        s_ladder_cols = ['open_def', 's_unimproved', 's_limited', 's_basic', 's_safely_managed']
        s_ladder_labels = ['Open Defecation', 'Unimproved', 'Limited', 'Basic', 'Safely Managed']
        s_colors = ['#ef4444', '#f97316', '#eab308', '#60a5fa', '#1e3a8a']
        
        s_agg = df_s_filt[s_ladder_cols].sum().reset_index()
        s_agg.columns = ['Category', 'Count']
        s_agg['Category'] = s_agg['Category'].replace(dict(zip(s_ladder_cols, s_ladder_labels)))
        
        total_s = s_agg['Count'].sum()
        s_agg['Percentage'] = (s_agg['Count'] / total_s * 100) if total_s > 0 else 0
        
        s_agg['Type'] = 'Sanitation Access'
        
        fig_s = px.bar(s_agg, x='Type', y='Percentage', color='Category',
                       color_discrete_map=dict(zip(s_ladder_labels, s_colors)),
                       category_orders={'Category': s_ladder_labels[::-1]},
                       text=s_agg['Percentage'].apply(lambda x: f"{x:.1f}%"))
        
        fig_s.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0), xaxis_title=None, yaxis_title="Percentage (%)")
        st.plotly_chart(fig_s, use_container_width=True)

    # --- Step 3: The Equity Check (Zonal Disparities) ---
    st.markdown("<div class='section-header'>⚖️ Equity Check <span style='font-size:14px;color:#6b7280;font-weight:400'>| Zonal Disparities</span></div>", unsafe_allow_html=True)
    
    e_col1, e_col2 = st.columns(2)
    
    with e_col1:
        st.markdown("**Municipal Coverage by Zone**")
        
        # Group by Zone
        zone_cov = df_w_filt.groupby('zone').agg({
            'municipal_coverage': 'sum',
            'popn_total': 'sum'
        }).reset_index()
        
        zone_cov['Coverage %'] = (zone_cov['municipal_coverage'] / zone_cov['popn_total'] * 100).fillna(0)
        
        fig_zone = px.bar(zone_cov.sort_values('Coverage %'), x='Coverage %', y='zone', orientation='h',
                          color='Coverage %', color_continuous_scale='Blues')
        fig_zone.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0), xaxis_title="Municipal Coverage (%)")
        st.plotly_chart(fig_zone, use_container_width=True)

    with e_col2:
        st.markdown("**Pro-Poor Overlay: Coverage vs Vulnerability**")
        
        # Need to map Zones to Cities to link with Financial Data (Pro-Poor)
        # Create mapping from Service Data
        if not df_service.empty:
            zone_city_map = df_service[['zone', 'city']].drop_duplicates().set_index('zone')['city'].to_dict()
            
            # Add City to Water Data
            df_w_city = df_w_filt.copy()
            df_w_city['city'] = df_w_city['zone'].map(zone_city_map)
            
            # Aggregate Water Data by City
            city_cov = df_w_city.groupby('city').agg({
                'municipal_coverage': 'sum',
                'popn_total': 'sum'
            }).reset_index()
            city_cov['Coverage %'] = (city_cov['municipal_coverage'] / city_cov['popn_total'] * 100).fillna(0)
            
            # Aggregate Financial Data by City (Pro-Poor Pop)
            # Take average pro-poor pop for the year
            if not df_f_filt.empty:
                city_fin = df_f_filt.groupby('city')['propoor_popn'].mean().reset_index()
                
                # Merge
                merged_equity = pd.merge(city_cov, city_fin, on='city', how='inner')
                
                if not merged_equity.empty:
                    # Calculate Pro-Poor % (Pro-Poor Pop / Total Pop) - Approximation
                    # Note: propoor_popn is a count.
                    merged_equity['Pro-Poor %'] = (merged_equity['propoor_popn'] / merged_equity['popn_total'] * 100).fillna(0)
                    
                    fig_scatter = px.scatter(merged_equity, x='Pro-Poor %', y='Coverage %', 
                                             text='city', size='popn_total',
                                             color='city', size_max=40)
                    fig_scatter.update_traces(textposition='top center')
                    fig_scatter.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0),
                                              xaxis_title="Pro-Poor Population (%)",
                                              yaxis_title="Municipal Coverage (%)")
                    st.plotly_chart(fig_scatter, use_container_width=True)
                else:
                    st.info("Insufficient data overlap between Service and Financial datasets for Pro-Poor analysis.")
            else:
                st.info("No financial data available for Pro-Poor analysis.")
        else:
            st.info("Service data unavailable for mapping zones to cities.")
