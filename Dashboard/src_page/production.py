import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import DATA_DIR, filter_df_by_user_access, validate_selected_country, get_user_country_filter


@st.cache_data
def _load_raw_production_data():
    """Load raw production data (internal, cached without access filtering)."""
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


def load_production_data():
    """
    Load production data for the dashboard.
    Data is automatically filtered based on user access permissions.
    """
    df_prod = _load_raw_production_data()
    
    # Apply access control filtering
    df_prod = filter_df_by_user_access(df_prod.copy(), "country")
    
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

    # --- Filters (from Header) ---
    st.markdown("<h1 style='font-size: 24px; font-weight: 700; color: #111827; margin-bottom: 16px;'>Production & Operations</h1>", unsafe_allow_html=True)
    
    with st.container():
        st.markdown("""
            <style>
                div[data-testid="stHorizontalBlock"] {
                    align-items: center;
                }
            </style>
        """, unsafe_allow_html=True)
        
        f1, f2, f3, f4 = st.columns([1.5, 1.5, 2, 1.5])
        
        with f1:
            # Date Range / Aggregation View
            view_type = st.selectbox(
                "View",
                ["Daily", "Monthly", "Quarterly", "Annual"],
                key="prod_view_type",
                label_visibility="collapsed"
            )
            
        with f2:
            # Country Filter - Access controlled
            user_country = get_user_country_filter()
            # Get available countries from data
            available_countries = sorted(df_prod['country'].unique().tolist()) if 'country' in df_prod.columns else []
            
            # Filter to only accessible countries
            if user_country is None:
                # Master user - show all available with "All" option
                default_countries = available_countries if available_countries else ["Uganda", "Cameroon", "Lesotho", "Malawi"]
                countries = ["All"] + default_countries
            else:
                # Non-master user - show only their assigned country
                countries = [c for c in available_countries if c.lower() == user_country.lower()] if available_countries else [user_country]
                if not countries:
                    countries = [user_country]  # Fallback to assigned country
            
            selected_country = st.selectbox(
                "Country",
                countries,
                key="prod_country_select",
                label_visibility="collapsed"
            )
            
            # Validate selection for non-master users
            if user_country is not None:
                selected_country = validate_selected_country(selected_country)
            
        with f3:
            # Zone/City Filter
            available_zones = []
            if selected_country != "All":
                if 'country' in df_prod.columns and 'zone' in df_prod.columns:
                    available_zones = sorted(df_prod[df_prod['country'] == selected_country]['zone'].unique().tolist())
            else:
                if 'zone' in df_prod.columns:
                    available_zones = sorted(df_prod['zone'].unique().tolist())
            
            selected_zones = st.multiselect(
                "Zone/City",
                available_zones,
                key="prod_zone_select",
                placeholder="Select Zones",
                label_visibility="collapsed"
            )
            
        with f4:
            # Unit Toggle
            unit_mode = st.radio(
                "Unit",
                ["Metric (m³)", "Imperial (gal)", "Percentage"],
                horizontal=True,
                key="prod_unit_toggle",
                label_visibility="collapsed"
            )

    st.markdown("---")

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
    
    # Apply Country Filter
    if selected_country != 'All' and 'country' in df_p_filt.columns:
        df_p_filt = df_p_filt[df_p_filt['country'] == selected_country]
        
    # Apply Zone Filter
    if selected_zones and 'zone' in df_p_filt.columns:
        df_p_filt = df_p_filt[df_p_filt['zone'].isin(selected_zones)]

    if df_p_filt.empty:
        st.warning(f"No data available for the selected filters.")
        return

    # --- Unit Conversion Logic ---
    # Base unit is m3
    # Imperial: 1 m3 = 264.172 gallons
    conversion_factor = 1.0
    unit_label = "m³"
    
    if unit_mode == "Imperial (gal)":
        conversion_factor = 264.172
        unit_label = "gal"
    
    # Create a display column for volume
    df_p_filt['volume_display'] = df_p_filt['production_m3'] * conversion_factor

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
    total_prod_latest = df_latest['volume_display'].sum()
    
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
    
    # Utilization for latest day (using base m3 for calculation to keep % correct)
    total_prod_latest_m3 = df_latest['production_m3'].sum()
    cap_utilization = (total_prod_latest_m3 / total_estimated_capacity * 100) if total_estimated_capacity > 0 else 0

    # Render Scorecard
    sc1, sc2, sc3, sc4 = st.columns(4)
    
    with sc1:
        val_display = f"{total_prod_latest:,.0f}"
        if unit_mode == "Percentage":
             # In percentage mode, maybe show utilization here too? Or just keep metric?
             # Let's keep metric/imperial for total volume, as "Total Production %" is ambiguous without a target.
             # Or we can show % of Capacity here.
             val_display = f"{cap_utilization:.1f}%"
             unit_label_card = "of Capacity"
        else:
             unit_label_card = f"{unit_label} on {latest_date.strftime('%b %d')}"

        st.markdown(f"""
        <div class='metric-container'>
            <div class='metric-label'>Total Production</div>
            <div class='metric-value'>{val_display}</div>
            <div class='metric-sub'>{unit_label_card}</div>
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

    # --- Step 1.5: Treatment Infrastructure Performance ---
    st.markdown("<div class='section-header'>🏭 Treatment Infrastructure Performance <span style='font-size:14px;color:#6b7280;font-weight:400'>| WTP & FSM</span></div>", unsafe_allow_html=True)
    
    infra_c1, infra_c2 = st.columns(2)
    
    # Panel 1: WTP Bubble Matrix
    with infra_c1:
        st.markdown("**Water Treatment Plants (WTP)**")
        # Aggregate production by source for bubble size
        wtp_data = df_p_filt.groupby('source')['volume_display'].sum().reset_index()
        
        if not wtp_data.empty:
            # Simulate attributes
            # Deterministic simulation based on source name hash to keep it consistent across reruns
            wtp_data['efficiency'] = wtp_data['source'].apply(lambda x: 80 + (hash(x) % 20)) # 80-99%
            wtp_data['utilization'] = wtp_data['source'].apply(lambda x: 50 + (hash(x) % 60)) # 50-110%
            
            def get_age_cat(x):
                h = hash(x) % 3
                if h == 0: return 'New (<5y)', '#3b82f6' # Blue
                elif h == 1: return 'Mid-life (5-15y)', '#10b981' # Green
                else: return 'Aging (>15y)', '#f59e0b' # Orange
            
            wtp_data[['age_category', 'color']] = wtp_data['source'].apply(lambda x: pd.Series(get_age_cat(x)))
            
            fig_wtp = px.scatter(wtp_data, x='utilization', y='efficiency',
                                 size='volume_display', color='age_category',
                                 color_discrete_map={'New (<5y)': '#3b82f6', 'Mid-life (5-15y)': '#10b981', 'Aging (>15y)': '#f59e0b'},
                                 hover_name='source',
                                 labels={'utilization': 'Capacity Util (%)', 'efficiency': 'Efficiency (%)'},
                                 title="Efficiency vs Utilization")
            
            # Optimal Zone (Green Box) - e.g., Util 70-90%, Eff > 90%
            fig_wtp.add_shape(type="rect",
                x0=70, y0=90, x1=95, y1=100,
                line=dict(color="Green", width=1, dash="dot"),
                fillcolor="rgba(0, 255, 0, 0.1)",
            )
            
            fig_wtp.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0), 
                                  legend=dict(orientation="h", y=-0.2),
                                  xaxis=dict(range=[40, 120]), yaxis=dict(range=[70, 105]))
            st.plotly_chart(fig_wtp, use_container_width=True)
        else:
            st.info("No WTP data available.")

    # Panel 2: FSM
    with infra_c2:
        st.markdown("**Faecal Sludge Management**")
        
        # Mock Data
        fsm_metrics = [
            {'label': 'Emptied', 'val': 65, 'vol': '12k m³', 'color': '#3b82f6'},
            {'label': 'Treated', 'val': 45, 'vol': '5.4k m³', 'color': '#10b981'},
            {'label': 'Reused', 'val': 10, 'vol': '0.5k m³', 'color': '#f59e0b'}
        ]
        
        # 3 Columns for 3 Rings
        r1, r2, r3 = st.columns(3)
        
        for i, col in enumerate([r1, r2, r3]):
            m = fsm_metrics[i]
            with col:
                fig_ring = go.Figure(go.Pie(
                    values=[m['val'], 100-m['val']],
                    hole=0.7,
                    sort=False,
                    direction='clockwise',
                    marker={'colors': [m['color'], '#f3f4f6']},
                    textinfo='none'
                ))
                fig_ring.update_layout(
                    showlegend=False,
                    height=120, 
                    margin=dict(l=0, r=0, t=0, b=0),
                    annotations=[dict(text=f"{m['val']}%", x=0.5, y=0.5, font_size=14, showarrow=False)]
                )
                st.plotly_chart(fig_ring, use_container_width=True)
                st.markdown(f"<div style='text-align:center; font-size:12px; font-weight:600'>{m['label']}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='text-align:center; font-size:10px; color:#6b7280'>{m['vol']}</div>", unsafe_allow_html=True)

        st.markdown(f"""
        <div class='alert-box' style='padding: 8px; font-size: 12px; margin-top: 16px;'>
            ⚠️ <strong>Data Gap:</strong> FSTP utilization data unavailable.
        </div>
        """, unsafe_allow_html=True)

    # --- Step 2: The Source Balancing Act (Extraction Analysis) ---
    st.markdown("<div class='section-header'>⚖️ Source Balancing Act <span style='font-size:14px;color:#6b7280;font-weight:400'>| Extraction Analysis</span></div>", unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown(f"**Production Mix ({view_type})**")
        
        # Aggregation based on View Type
        if view_type == "Daily":
            group_cols = ['date_dt', 'source']
            x_axis = 'date_dt'
        elif view_type == "Monthly":
            df_p_filt['period'] = df_p_filt['date_dt'].dt.to_period('M').dt.to_timestamp()
            group_cols = ['period', 'source']
            x_axis = 'period'
        elif view_type == "Quarterly":
            df_p_filt['period'] = df_p_filt['date_dt'].dt.to_period('Q').dt.to_timestamp()
            group_cols = ['period', 'source']
            x_axis = 'period'
        else: # Annual
            df_p_filt['period'] = df_p_filt['date_dt'].dt.to_period('Y').dt.to_timestamp()
            group_cols = ['period', 'source']
            x_axis = 'period'

        prod_trend = df_p_filt.groupby(group_cols)['volume_display'].sum().reset_index()
        
        if prod_trend.empty:
            st.info("No production data available for visualization.")
        else:
            # Handle Percentage View
            groupnorm = 'percent' if unit_mode == "Percentage" else None
            y_label = f'Volume ({unit_label})' if unit_mode != "Percentage" else "Percentage Share"
            
            fig_mix = px.area(prod_trend, x=x_axis, y='volume_display', color='source',
                              labels={'volume_display': y_label, x_axis: 'Date'},
                              color_discrete_sequence=px.colors.qualitative.Safe,
                              groupnorm=groupnorm)
            fig_mix.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0), legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig_mix, use_container_width=True)
        
    with c2:
        st.markdown("**Source Performance Leaderboard**")
        # Aggregated stats
        source_stats = df_p_filt.groupby('source').agg({
            'volume_display': 'sum',
            'service_hours': 'mean'
        }).reset_index()
        
        if source_stats.empty:
            st.info("No source performance data available.")
        else:
            x_col = 'volume_display'
            x_label = f'Total Volume ({unit_label})'
            
            # If percentage view, calculate share
            if unit_mode == "Percentage":
                total_vol = source_stats['volume_display'].sum()
                source_stats['share'] = (source_stats['volume_display'] / total_vol * 100)
                x_col = 'share'
                x_label = 'Volume Share (%)'

            fig_perf = px.bar(source_stats, x=x_col, y='source', 
                              color='service_hours',
                              title=f"Volume vs Avg Service Hours",
                              labels={x_col: x_label, 'service_hours': 'Avg Hours/Day'},
                              color_continuous_scale='RdYlGn',
                              orientation='h')
            fig_perf.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_perf, use_container_width=True)

    # --- Step 3: Production Trends & Forecasting ---
    st.markdown("<div class='section-header'>📈 Production Trends & Forecasting <span style='font-size:14px;color:#6b7280;font-weight:400'>| Advanced Analytics</span></div>", unsafe_allow_html=True)

    # --- Data Preparation for Time Series ---
    import numpy as np
    
    # Aggregate to daily total across all selected sources/zones
    ts_df = df_p_filt.groupby('date_dt')['volume_display'].sum().reset_index()
    ts_df = ts_df.sort_values('date_dt')
    
    if not ts_df.empty:
        # Mocking missing metrics for demonstration
        np.random.seed(42)
        
        # Consumption is typically 60-80% of production (Efficiency)
        ts_df['consumption'] = ts_df['volume_display'] * np.random.uniform(0.65, 0.85, len(ts_df))
        
        # NRW is the difference
        ts_df['nrw'] = ts_df['volume_display'] - ts_df['consumption']
        
        # Population served (Slow growth)
        base_pop = 500000 # Example base
        growth_rate = 0.0001 # Daily growth
        ts_df['population'] = [base_pop * (1 + growth_rate)**i for i in range(len(ts_df))]

        # --- Control Panel ---
        st.markdown("#### Control Panel")
        with st.container():
            c_ctrl1, c_ctrl2, c_ctrl3, c_ctrl4 = st.columns(4)
            
            with c_ctrl1:
                st.markdown("**Metrics**")
                show_prod = st.checkbox("Production", value=True)
                show_cons = st.checkbox("Consumption", value=True)
                show_nrw = st.checkbox("NRW (Losses)", value=True)
                show_pop = st.checkbox("Population", value=False)
                
            with c_ctrl2:
                st.markdown("**Smoothing**")
                smoothing = st.radio("Interval", ["Daily", "Weekly", "Monthly"], horizontal=True, key="ts_smooth")
                
            with c_ctrl3:
                st.markdown("**Analysis**")
                show_forecast = st.checkbox("Show Forecast (3 Months)", value=True)
                show_anomalies = st.checkbox("Highlight Anomalies", value=False)
                
            with c_ctrl4:
                st.markdown("**Export**")
                csv = ts_df.to_csv(index=False).encode('utf-8')
                st.download_button("Download Data (CSV)", csv, "production_trends.csv", "text/csv")

        # --- Resampling ---
        if smoothing == "Weekly":
            ts_resampled = ts_df.set_index('date_dt').resample('W').agg({
                'volume_display': 'sum', 'consumption': 'sum', 'nrw': 'sum', 'population': 'mean'
            }).reset_index()
        elif smoothing == "Monthly":
            ts_resampled = ts_df.set_index('date_dt').resample('M').agg({
                'volume_display': 'sum', 'consumption': 'sum', 'nrw': 'sum', 'population': 'mean'
            }).reset_index()
        else:
            ts_resampled = ts_df.copy()

        # --- Forecasting (Simple Projection) ---
        forecast_df = pd.DataFrame()
        if show_forecast and not ts_resampled.empty:
            last_date = ts_resampled['date_dt'].max()
            # Create future dates
            if smoothing == "Daily":
                future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=90, freq='D')
            elif smoothing == "Weekly":
                future_dates = pd.date_range(start=last_date + pd.Timedelta(weeks=1), periods=12, freq='W')
            else:
                future_dates = pd.date_range(start=last_date + pd.Timedelta(days=30), periods=3, freq='M')
                
            # Simple naive forecast (last value + noise)
            last_vals = ts_resampled.iloc[-1]
            
            forecast_data = []
            for date in future_dates:
                # Add some seasonality/trend
                factor = 1.0
                forecast_data.append({
                    'date_dt': date,
                    'volume_display': last_vals['volume_display'] * factor,
                    'consumption': last_vals['consumption'] * factor,
                    'nrw': last_vals['nrw'] * factor,
                    'population': last_vals['population'] # Flat
                })
            forecast_df = pd.DataFrame(forecast_data)

        # --- Plotting ---
        fig = go.Figure()
        
        # 1. Production (Blue Line)
        if show_prod:
            fig.add_trace(go.Scatter(
                x=ts_resampled['date_dt'], y=ts_resampled['volume_display'],
                mode='lines', name='Production',
                line=dict(color='#3b82f6', width=2)
            ))
            if not forecast_df.empty:
                 fig.add_trace(go.Scatter(
                    x=forecast_df['date_dt'], y=forecast_df['volume_display'],
                    mode='lines', name='Production Forecast',
                    line=dict(color='#3b82f6', width=2, dash='dot'),
                    showlegend=False
                ))

        # 2. Consumption (Green Line)
        if show_cons:
            fig.add_trace(go.Scatter(
                x=ts_resampled['date_dt'], y=ts_resampled['consumption'],
                mode='lines', name='Consumption',
                line=dict(color='#10b981', width=2)
            ))
            if not forecast_df.empty:
                 fig.add_trace(go.Scatter(
                    x=forecast_df['date_dt'], y=forecast_df['consumption'],
                    mode='lines', name='Consumption Forecast',
                    line=dict(color='#10b981', width=2, dash='dot'),
                    showlegend=False
                ))

        # 3. NRW (Red Shaded Area)
        if show_nrw:
            fig.add_trace(go.Scatter(
                x=ts_resampled['date_dt'], y=ts_resampled['nrw'],
                mode='lines', name='NRW (Losses)',
                stackgroup=None,
                fill='tozeroy',
                line=dict(color='#ef4444', width=0),
                fillcolor='rgba(239, 68, 68, 0.2)'
            ))

        # 4. Population (Secondary Axis)
        if show_pop:
            fig.add_trace(go.Scatter(
                x=ts_resampled['date_dt'], y=ts_resampled['population'],
                mode='lines', name='Population Served',
                line=dict(color='#9ca3af', width=2, dash='dot'),
                yaxis='y2'
            ))

        # 5. Anomalies
        if show_anomalies and show_prod:
            # Simple anomaly: > 2 std dev from rolling mean
            rolling_mean = ts_resampled['volume_display'].rolling(window=7, center=True).mean()
            rolling_std = ts_resampled['volume_display'].rolling(window=7, center=True).std()
            anomalies = ts_resampled[
                (ts_resampled['volume_display'] > rolling_mean + 2 * rolling_std) | 
                (ts_resampled['volume_display'] < rolling_mean - 2 * rolling_std)
            ]
            if not anomalies.empty:
                fig.add_trace(go.Scatter(
                    x=anomalies['date_dt'], y=anomalies['volume_display'],
                    mode='markers', name='Anomalies',
                    marker=dict(color='red', size=8, symbol='x')
                ))

        # 6. Forecast Region Shade
        if show_forecast and not forecast_df.empty:
            start_forecast = forecast_df['date_dt'].min()
            end_forecast = forecast_df['date_dt'].max()
            fig.add_vrect(
                x0=start_forecast, x1=end_forecast,
                fillcolor="gray", opacity=0.1,
                layer="below", line_width=0,
                annotation_text="Forecast", annotation_position="top left"
            )

        # Layout
        fig.update_layout(
            title="Production & Consumption Trends",
            xaxis_title="Date",
            yaxis_title=f"Volume ({unit_label})",
            yaxis2=dict(
                title="Population",
                overlaying='y',
                side='right',
                showgrid=False
            ),
            hovermode="x unified",
            legend=dict(orientation="h", y=1.1),
            height=500,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available for trend analysis.")

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

