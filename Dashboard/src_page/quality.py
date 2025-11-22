import io
from datetime import datetime
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import prepare_service_data as _prepare_service_data, DATA_DIR

def load_extra_data():
    """Load billing, financial services, and production data for the quality dashboard."""
    billing_path = DATA_DIR / "billing.csv"
    fin_path = DATA_DIR / "financial_services.csv"
    prod_path = DATA_DIR / "production.csv"
    
    df_billing = pd.DataFrame()
    df_fin = pd.DataFrame()
    df_prod = pd.DataFrame()
    
    if billing_path.exists():
        df_billing = pd.read_csv(billing_path, low_memory=False)
        # Parse dates
        if 'date_MMYY' in df_billing.columns:
            df_billing['date'] = pd.to_datetime(df_billing['date_MMYY'], format='%b/%y', errors='coerce')
        df_billing['year'] = df_billing['date'].dt.year
        df_billing['month'] = df_billing['date'].dt.month
    
    if fin_path.exists():
        df_fin = pd.read_csv(fin_path)
        if 'date_MMYY' in df_fin.columns:
            df_fin['date'] = pd.to_datetime(df_fin['date_MMYY'], format='%b/%y', errors='coerce')
        df_fin['year'] = df_fin['date'].dt.year
        df_fin['month'] = df_fin['date'].dt.month

    if prod_path.exists():
        df_prod = pd.read_csv(prod_path)
        if 'date_YYMMDD' in df_prod.columns:
            df_prod['date'] = pd.to_datetime(df_prod['date_YYMMDD'], format='%Y/%m/%d', errors='coerce')
        df_prod['year'] = df_prod['date'].dt.year
        df_prod['month'] = df_prod['date'].dt.month
        
    return df_billing, df_fin, df_prod

def scene_quality():
    """
    Service Quality & Reliability scene - Redesigned based on User Journey.
    """
    # Load data
    service_data = _prepare_service_data()
    df_service = service_data["full_data"]
    df_billing, df_fin, df_prod = load_extra_data()

    # --- 1. Filters (Retrieved from Sidebar/Session State) ---
    selected_country = st.session_state.get("selected_country", "All")
    selected_zone = st.session_state.get("selected_zone", "All")
    selected_year = st.session_state.get("selected_year")
    selected_month_name = st.session_state.get("selected_month", "All")

    # Map month name to number
    month_map = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    selected_month = month_map.get(selected_month_name) if selected_month_name != 'All' else 'All'

    # --- Apply Filters ---
    # Service Data
    df_s_filt = df_service.copy()
    if selected_country != 'All': df_s_filt = df_s_filt[df_s_filt['country'] == selected_country]
    if selected_zone != 'All': df_s_filt = df_s_filt[df_s_filt['zone'] == selected_zone]
    if selected_year: df_s_filt = df_s_filt[df_s_filt['year'] == selected_year]
    if selected_month != 'All': df_s_filt = df_s_filt[df_s_filt['month'] == selected_month]

    # Billing Data (No Zone/City usually, but check columns)
    df_b_filt = df_billing.copy()
    if not df_b_filt.empty:
        if selected_country != 'All' and 'country' in df_b_filt.columns:
            # Case-insensitive filtering
            df_b_filt = df_b_filt[df_b_filt['country'].str.lower() == selected_country.lower()]
        # Billing often lacks city/zone, so we don't filter by them to avoid empty data
        # unless we are sure. For now, we filter by year.
        if 'year' in df_b_filt.columns and selected_year:
            df_b_filt = df_b_filt[df_b_filt['year'] == selected_year]
        if selected_month != 'All' and 'month' in df_b_filt.columns:
            df_b_filt = df_b_filt[df_b_filt['month'] == selected_month]

    # Financial Data
    df_f_filt = df_fin.copy()
    if not df_f_filt.empty:
        if selected_country != 'All' and 'country' in df_f_filt.columns:
            # Case-insensitive filtering
            df_f_filt = df_f_filt[df_f_filt['country'].str.lower() == selected_country.lower()]
        if 'year' in df_f_filt.columns and selected_year:
            df_f_filt = df_f_filt[df_f_filt['year'] == selected_year]
        if selected_month != 'All' and 'month' in df_f_filt.columns:
            df_f_filt = df_f_filt[df_f_filt['month'] == selected_month]

    # Production Data
    df_p_filt = df_prod.copy()
    if not df_p_filt.empty:
        if selected_country != 'All' and 'country' in df_p_filt.columns:
            # Case-insensitive filtering
            df_p_filt = df_p_filt[df_p_filt['country'].str.lower() == selected_country.lower()]
        if 'year' in df_p_filt.columns and selected_year:
            df_p_filt = df_p_filt[df_p_filt['year'] == selected_year]
        if selected_month != 'All' and 'month' in df_p_filt.columns:
            df_p_filt = df_p_filt[df_p_filt['month'] == selected_month]

    if df_s_filt.empty:
        st.warning("⚠️ No service data available for selected filters")
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

    # --- Step 1: The "Morning Coffee" Check (Scorecard) ---
    st.markdown("<div class='section-header'>☕ Daily Briefing <span style='font-size:14px;color:#6b7280;font-weight:400'>| High-Level Assessment</span></div>", unsafe_allow_html=True)
    
    # Calculations
    # 1. Water Quality Compliance
    total_tests = df_s_filt['tests_conducted_chlorine'].sum()
    passed_tests = df_s_filt['test_passed_chlorine'].sum()
    compliance_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    # 2. Service Hours (from Production)
    avg_service_hours = df_p_filt['service_hours'].mean() if not df_p_filt.empty and 'service_hours' in df_p_filt.columns else 0
    
    # 3. Complaint Resolution
    total_complaints = df_s_filt['complaints'].sum()
    total_resolved = df_s_filt['resolved'].sum()
    resolution_rate = (total_resolved / total_complaints * 100) if total_complaints > 0 else 0
    
    # 4. Testing Adherence
    required_tests = df_s_filt['tests_chlorine'].sum() # Assuming 'tests_chlorine' is the target/required count
    adherence_rate = (total_tests / required_tests * 100) if required_tests > 0 else 0

    # Render Scorecard
    sc1, sc2, sc3, sc4 = st.columns(4)
    
    metrics = [
        ("Water Quality Compliance", f"{compliance_rate:.1f}%", 98, "%"),
        ("Avg Service<br>Hours", f"{avg_service_hours:.1f}", 18.5, "hrs/day"),
        ("Complaint<br>Resolution", f"{resolution_rate:.1f}%", 85, "%"),
        ("Testing<br>Adherence", f"{adherence_rate:.1f}%", 100, "%")
    ]
    
    for col, (label, value, target, unit) in zip([sc1, sc2, sc3, sc4], metrics):
        val_num = float(value.strip('%'))
        delta = val_num - target
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

    # --- Step 2: The Deep Dive (Quality) ---
    st.markdown("<div class='section-header'>🔍 Quality Deep Dive <span style='font-size:14px;color:#6b7280;font-weight:400'>| Investigating Issues</span></div>", unsafe_allow_html=True)
    
    q_col1, q_col2 = st.columns(2)
    
    with q_col1:
        #st.markdown("<div class='chart-container'>", unsafe_allow_html=True)
        st.markdown("**Testing Performance: Required vs Conducted vs Passed**")
        
        # Determine grouping
        if selected_country == 'All':
            group_col = 'country'
        elif selected_zone == 'All':
            group_col = 'zone'
        else:
            group_col = None

        # Prepare Data
        metrics_cols = ['tests_chlorine', 'tests_conducted_chlorine', 'test_passed_chlorine']
        
        if selected_month == 'All':
            # Average of monthly sums
            if group_col:
                # Group by entity AND month first to get monthly totals, then average
                monthly_sums = df_s_filt.groupby([group_col, 'month'])[metrics_cols].sum().reset_index()
                chart_data = monthly_sums.groupby(group_col)[metrics_cols].mean().reset_index()
                title_suffix = "(Monthly Average)"
            else:
                # Group by month first, then average
                monthly_sums = df_s_filt.groupby('month')[metrics_cols].sum().reset_index()
                # Create a single row DataFrame for consistency
                means = monthly_sums[metrics_cols].mean()
                chart_data = pd.DataFrame([means])
                chart_data['Label'] = selected_zone # Dummy column for y-axis
                group_col = 'Label' 
                title_suffix = "(Monthly Average)"
        else:
            # Specific month sums
            if group_col:
                chart_data = df_s_filt.groupby(group_col)[metrics_cols].sum().reset_index()
                title_suffix = f"({selected_month_name})"
            else:
                sums = df_s_filt[metrics_cols].sum()
                chart_data = pd.DataFrame([sums])
                chart_data['Label'] = selected_zone
                group_col = 'Label'
                title_suffix = f"({selected_month_name})"

        # Calculate Rates for annotation
        # Avoid division by zero
        chart_data['conduct_rate'] = (chart_data['tests_conducted_chlorine'] / chart_data['tests_chlorine']).fillna(0) * 100
        chart_data['pass_rate'] = (chart_data['test_passed_chlorine'] / chart_data['tests_conducted_chlorine']).fillna(0) * 100

        # Create Figure
        fig_perf = go.Figure()
        
        # 1. Required
        fig_perf.add_trace(go.Bar(
            y=chart_data[group_col],
            x=chart_data['tests_chlorine'],
            name='Required',
            orientation='h',
            marker_color='#94a3b8',
            text=chart_data['tests_chlorine'].apply(lambda x: f"{x:.0f}"),
            textposition='auto'
        ))
        
        # 2. Conducted
        fig_perf.add_trace(go.Bar(
            y=chart_data[group_col],
            x=chart_data['tests_conducted_chlorine'],
            name='Conducted',
            orientation='h',
            marker_color='#3b82f6',
            text=chart_data.apply(lambda row: f"{row['tests_conducted_chlorine']:.0f} ({row['conduct_rate']:.1f}%)", axis=1),
            textposition='auto'
        ))
        
        # 3. Passed
        fig_perf.add_trace(go.Bar(
            y=chart_data[group_col],
            x=chart_data['test_passed_chlorine'],
            name='Passed',
            orientation='h',
            marker_color='#10b981',
            text=chart_data.apply(lambda row: f"{row['test_passed_chlorine']:.0f} ({row['pass_rate']:.1f}%)", axis=1),
            textposition='auto'
        ))

        fig_perf.update_layout(
            height=300 + (len(chart_data) * 20 if len(chart_data) > 5 else 0), # Dynamic height
            margin=dict(l=0, r=0, t=30, b=0),
            barmode='group',
            legend=dict(orientation="h", y=1.1),
            title=dict(text=f"Testing Performance {title_suffix}", font=dict(size=14)),
            xaxis_title="Number of Tests"
        )
        
        st.plotly_chart(fig_perf, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with q_col2:
        #st.markdown("<div class='chart-container'>", unsafe_allow_html=True)
        st.markdown("**Contaminant Trends: Chlorine vs E. Coli Pass Rate**")
        
        if selected_month == 'All':
            # Line Chart with Range Slider (Multi-year view for YoY comparison)
            # Use df_service (unfiltered by year) but filtered by country/zone
            df_chart = df_service.copy()
            if selected_country != 'All':
                df_chart = df_chart[df_chart['country'] == selected_country]
            if selected_zone != 'All':
                df_chart = df_chart[df_chart['zone'] == selected_zone]
            
            ts_quality = df_chart.groupby('date').agg({
                'test_passed_chlorine': 'sum',
                'tests_conducted_chlorine': 'sum',
                'tests_passed_ecoli': 'sum',
                'test_conducted_ecoli': 'sum'
            }).reset_index()
            
            ts_quality['Chlorine %'] = (ts_quality['test_passed_chlorine'] / ts_quality['tests_conducted_chlorine'] * 100).fillna(0)
            ts_quality['E. Coli %'] = (ts_quality['tests_passed_ecoli'] / ts_quality['test_conducted_ecoli'] * 100).fillna(0)
            
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(x=ts_quality['date'], y=ts_quality['Chlorine %'], name='Chlorine', line=dict(color='#3b82f6', width=2)))
            fig_trend.add_trace(go.Scatter(x=ts_quality['date'], y=ts_quality['E. Coli %'], name='E. Coli', line=dict(color='#ef4444', width=2)))
            
            fig_trend.update_layout(
                height=300, 
                margin=dict(l=0, r=0, t=0, b=0), 
                legend=dict(orientation="h", y=1.1),
                xaxis=dict(
                    rangeslider=dict(visible=True),
                    type="date",
                    range=[f"{selected_year}-01-01", f"{selected_year}-12-31"]
                )
            )
            st.plotly_chart(fig_trend, use_container_width=True)
            
        else:
            # Bar Charts (Specific Month)
            if selected_country == 'All':
                # Compare Countries
                group_col = 'country'
            elif selected_zone == 'All':
                # Compare Zones
                group_col = 'zone'
            else:
                # Specific Zone
                group_col = None

            if group_col:
                # Grouped Bar Chart
                bar_data = df_s_filt.groupby(group_col).agg({
                    'test_passed_chlorine': 'sum',
                    'tests_conducted_chlorine': 'sum',
                    'tests_passed_ecoli': 'sum',
                    'test_conducted_ecoli': 'sum'
                }).reset_index()
                
                bar_data['Chlorine %'] = (bar_data['test_passed_chlorine'] / bar_data['tests_conducted_chlorine'] * 100).fillna(0)
                bar_data['E. Coli %'] = (bar_data['tests_passed_ecoli'] / bar_data['test_conducted_ecoli'] * 100).fillna(0)
                
                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(x=bar_data[group_col], y=bar_data['Chlorine %'], name='Chlorine', marker_color='#3b82f6'))
                fig_bar.add_trace(go.Bar(x=bar_data[group_col], y=bar_data['E. Coli %'], name='E. Coli', marker_color='#ef4444'))
                
                fig_bar.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0), barmode='group', legend=dict(orientation="h", y=1.1))
                st.plotly_chart(fig_bar, use_container_width=True)
                
            else:
                # Single Zone Bar Chart
                t_pass_cl = df_s_filt['test_passed_chlorine'].sum()
                t_cond_cl = df_s_filt['tests_conducted_chlorine'].sum()
                t_pass_ec = df_s_filt['tests_passed_ecoli'].sum()
                t_cond_ec = df_s_filt['test_conducted_ecoli'].sum()
                
                rate_cl = (t_pass_cl / t_cond_cl * 100) if t_cond_cl > 0 else 0
                rate_ec = (t_pass_ec / t_cond_ec * 100) if t_cond_ec > 0 else 0
                
                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(x=['Chlorine', 'E. Coli'], y=[rate_cl, rate_ec], marker_color=['#3b82f6', '#ef4444']))
                fig_bar.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0), showlegend=False, yaxis_title="Pass Rate (%)")
                st.plotly_chart(fig_bar, use_container_width=True)
        
        st.markdown("</div>", unsafe_allow_html=True)

    # --- Step 3: Geographic Isolation (Zonal Analysis) ---
    st.markdown("<div class='section-header'>🗺️ Geographic Isolation <span style='font-size:14px;color:#6b7280;font-weight:400'>| Zonal Analysis</span></div>", unsafe_allow_html=True)
    
    z_col1, z_col2 = st.columns(2)
    
    # Group by Zone
    zone_agg = df_s_filt.groupby('zone').agg({
        'w_supplied': 'sum',
        'complaints': 'sum',
        'resolved': 'sum'
    }).reset_index()
    
    with z_col1:
        #st.markdown("<div class='chart-container'>", unsafe_allow_html=True)
        st.markdown("**Water Supply Distribution by Zone**")
        # Using w_supplied as proxy for service intensity since service_hours is not available by zone
        fig_zone_supply = px.bar(zone_agg.sort_values('w_supplied'), x='w_supplied', y='zone', orientation='h',
                                 color='w_supplied', color_continuous_scale='Blues')
        fig_zone_supply.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0), xaxis_title="Volume Supplied (m³)")
        st.plotly_chart(fig_zone_supply, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with z_col2:
        #st.markdown("<div class='chart-container'>", unsafe_allow_html=True)
        st.markdown("**Complaints vs Resolution by Zone**")
        
        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(x=zone_agg['zone'], y=zone_agg['complaints'], name='Complaints', marker_color='#f59e0b'))
        fig_comp.add_trace(go.Bar(x=zone_agg['zone'], y=zone_agg['resolved'], name='Resolved', marker_color='#10b981'))
        
        fig_comp.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0), barmode='group', legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig_comp, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # --- Step 4: The Sanitation Check ---
    st.markdown("<div class='section-header'>🚽 Sanitation Check <span style='font-size:14px;color:#6b7280;font-weight:400'>| The 'Forgotten' Half</span></div>", unsafe_allow_html=True)
    
    s_col1, s_col2 = st.columns(2)
    
    with s_col1:
        #st.markdown("<div class='chart-container'>", unsafe_allow_html=True)
        st.markdown("**Wastewater Treatment Efficiency**")
        
        ww_metrics = df_s_filt.agg({
            'ww_collected': 'sum',
            'ww_treated': 'sum',
            'ww_reused': 'sum'
        }).reset_index()
        ww_metrics.columns = ['Stage', 'Volume']
        
        fig_funnel = go.Figure(go.Funnel(
            y=ww_metrics['Stage'],
            x=ww_metrics['Volume'],
            textinfo="value+percent initial",
            marker=dict(color=["#3b82f6", "#6366f1", "#8b5cf6"])
        ))
        fig_funnel.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig_funnel, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with s_col2:
        #st.markdown("<div class='chart-container'>", unsafe_allow_html=True)
        st.markdown("**Sewer Health: Blockages**")
        
        # Blockages from financial data
        total_blocks = df_f_filt['blocks'].sum() if not df_f_filt.empty else 0
        
        # Trend if possible
        if not df_f_filt.empty:
            blocks_trend = df_f_filt.groupby('date')['blocks'].sum().reset_index()
            fig_blocks = px.line(blocks_trend, x='date', y='blocks', markers=True)
            fig_blocks.update_traces(line_color='#ef4444')
            fig_blocks.update_layout(height=220, margin=dict(l=0, r=0, t=0, b=0), yaxis_title="Blockages")
            
            st.metric("Total Blockages (Selected Period)", f"{total_blocks:,.0f}", help="Total sewer blockages reported")
            st.plotly_chart(fig_blocks, use_container_width=True)
        else:
            st.info("No blockage data available for selected filters.")
            
        st.markdown("</div>", unsafe_allow_html=True)

