import io
from datetime import datetime
import os
import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import (
    prepare_service_data as _prepare_service_data, 
    DATA_DIR, 
    filter_df_by_user_access, 
    validate_selected_country, 
    get_user_country_filter,
    render_section_header,
    render_domain_pill,
    render_empty_state,
    render_standardized_filters,
    apply_standard_filters,
    get_month_number
)

# Required columns for schema validation
SERVICE_REQUIRED_COLS = ['country', 'zone', 'year', 'month']


def _safe_year_filter(df: pd.DataFrame, year_col: str, year_value) -> pd.DataFrame:
    """Filter DataFrame by year, handling int/string type mismatches.
    
    Args:
        df: DataFrame to filter
        year_col: Name of the year column
        year_value: Year value to filter by (can be int or string)
    
    Returns:
        Filtered DataFrame
    """
    if year_value is None or df.empty or year_col not in df.columns:
        return df
    try:
        year_int = int(year_value)
        return df[df[year_col] == year_int]
    except (ValueError, TypeError):
        return df[df[year_col] == year_value]


def validate_upload_schema(df: pd.DataFrame, required_cols: list, file_type: str) -> tuple:
    """Validate that uploaded data has required columns.
    
    Returns:
        tuple: (is_valid, missing_columns, warning_message)
    """
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        return False, missing, f"❌ {file_type} is missing required columns: {', '.join(missing)}"
    return True, [], None


@st.cache_data
def _load_raw_extra_data():
    """Load raw billing, financial services, and production data (internal, cached)."""
    billing_path = DATA_DIR / "billing.csv"
    fin_path = DATA_DIR / "all_fin_service.csv"
    prod_path = DATA_DIR / "production.csv"
    nat_path = DATA_DIR / "all_nationalacc.csv"
    
    df_billing = pd.DataFrame()
    df_fin = pd.DataFrame()
    df_prod = pd.DataFrame()
    df_national = pd.DataFrame()
    
    if billing_path.exists():
        df_billing = pd.read_csv(billing_path, low_memory=False)
        # Parse dates
        if 'date' in df_billing.columns:
            df_billing['date'] = pd.to_datetime(df_billing['date'], errors='coerce')
            df_billing['year'] = df_billing['date'].dt.year
            df_billing['month'] = df_billing['date'].dt.month
        elif 'date_MMYY' in df_billing.columns:
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

    if nat_path.exists():
        df_national = pd.read_csv(nat_path)
        
    return df_billing, df_fin, df_prod, df_national


def load_extra_data():
    """
    Load billing, financial services, and production data for the quality dashboard.
    Data is automatically filtered based on user access permissions.
    """
    df_billing, df_fin, df_prod, df_national = _load_raw_extra_data()
    
    # Apply access control filtering
    df_billing = filter_df_by_user_access(df_billing.copy(), "country")
    df_fin = filter_df_by_user_access(df_fin.copy(), "country")
    df_prod = filter_df_by_user_access(df_prod.copy(), "country")
    df_national = filter_df_by_user_access(df_national.copy(), "country")
    
    return df_billing, df_fin, df_prod, df_national

def scene_quality():
    """
    Service Quality & Reliability scene - Redesigned based on User Journey.
    """
    
    # ============================================================================
    # PAGE TITLE
    # ============================================================================
    
    st.markdown("## 🛠️ Service Quality & Reliability")
    st.markdown(
        f"<div style='color: #6b7280; font-size: 0.85rem; margin-bottom: 16px;'>"
        f"<span class='granularity-badge granularity-monthly'>Monthly</span> "
        f"<span style='margin-left: 8px;'>Water quality, continuity, and service performance metrics</span>"
        f"</div>",
        unsafe_allow_html=True
    )
    
    # ============================================================================
    # DATA INITIALIZATION (Before UI elements)
    # ============================================================================
    
    # Initialize session state for data BEFORE expander to ensure data is available
    if 'quality_service_data' not in st.session_state:
        st.session_state.quality_service_data = None
    if 'quality_default_data_loaded' not in st.session_state:
        st.session_state.quality_default_data_loaded = False

    # AUTO-LOAD DEFAULT DATA ON FIRST PAGE LOAD (silently, outside expander)
    if not st.session_state.quality_default_data_loaded:
        try:
            st.session_state.quality_service_data = pd.read_csv(DATA_DIR / 'sw_service.csv')
            st.session_state.quality_default_data_loaded = True
        except Exception as e:
            st.session_state.quality_default_data_loaded = True  # Prevent repeated attempts
    
    # ============================================================================
    # DATA IMPORT SECTION (Collapsed by default)
    # ============================================================================
    
    with st.expander("📁 Data Import", expanded=False):
        st.markdown("""
        <style>
            .upload-section {
                background: #f9fafb;
                border: 2px dashed #d1d5db;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 20px;
            }
        </style>
        """, unsafe_allow_html=True)

        # Show current data status
        if st.session_state.quality_service_data is not None:
            st.success(f"✅ Service data loaded: {len(st.session_state.quality_service_data)} records")
        else:
            st.warning("⚠️ No service data loaded")

        # Tab for different import methods
        import_tab1, import_tab2 = st.tabs(["📤 Upload Custom Files", "📋 Default Data"])

        with import_tab1:
            st.markdown("**Service Quality Data**")
            service_file = st.file_uploader(
                "Upload Service Data CSV",
                type=['csv', 'xlsx'],
                key="quality_service_upload",
                help="Required columns: country, zone, year, month, tests_conducted_chlorine, test_passed_chlorine, complaints, resolved, etc."
            )

            if service_file:
                try:
                    if service_file.name.endswith('.csv'):
                        uploaded_service = pd.read_csv(service_file)
                    else:
                        uploaded_service = pd.read_excel(service_file)
                    
                    # Schema validation
                    is_valid, missing, warning = validate_upload_schema(uploaded_service, SERVICE_REQUIRED_COLS, "Service Data")
                    if not is_valid:
                        st.warning(warning)
                    else:
                        st.session_state.quality_service_data = uploaded_service
                        st.success(f"✓ Loaded {len(st.session_state.quality_service_data)} service records")
                except Exception as e:
                    st.error(f"Error loading service data: {e}")

        with import_tab2:
            st.info("📌 Using default service data from repository")
            if st.button("🔄 Reload Default Data", key="reload_quality_default"):
                with st.spinner("Reloading default data..."):
                    try:
                        st.session_state.quality_service_data = pd.read_csv(DATA_DIR / 'sw_service.csv')
                        st.success(f"✓ Reloaded {len(st.session_state.quality_service_data)} service records")
                    except Exception as e:
                        st.error(f"Error loading default data: {e}")

    # Load data (use session state if available, otherwise use default loading)
    if st.session_state.quality_service_data is not None:
        # Use custom service data from session state
        raw_data = st.session_state.quality_service_data.copy()
        # Ensure date column is proper datetime
        if 'date' in raw_data.columns:
            # Convert string date like "Jan 2020" to datetime
            raw_data['date'] = pd.to_datetime(raw_data['date'], format='%b %Y', errors='coerce')
            # If that fails, try creating from year/month
            if raw_data['date'].isna().all() and 'year' in raw_data.columns and 'month' in raw_data.columns:
                raw_data['date'] = pd.to_datetime(
                    raw_data['year'].astype(str) + '-' + raw_data['month'].astype(str).str.zfill(2) + '-01'
                )
        elif 'year' in raw_data.columns and 'month' in raw_data.columns:
            raw_data['date'] = pd.to_datetime(
                raw_data['year'].astype(str) + '-' + raw_data['month'].astype(str).str.zfill(2) + '-01'
            )
        raw_data = raw_data.sort_values('date') if 'date' in raw_data.columns else raw_data
        service_data = {"full_data": filter_df_by_user_access(raw_data, "country")}
        df_service = service_data["full_data"]
    else:
        service_data = _prepare_service_data()
        df_service = service_data["full_data"]
    
    df_billing, df_fin, df_prod, df_national = load_extra_data()

    # --- Header Section ---
    header_container = st.container()
    
    # --- Standardized Filters (AUDC Dictionary Compliant) ---
    filters = render_standardized_filters(
        df=df_service,
        page="quality",
        key_prefix="quality",
        country_col="country",
        zone_col="zone",
        year_col="year",
        show_period=True,
        show_zone=True,
        show_year=True,
        show_month=True  # Quality data is Monthly
    )
    
    # Extract filter values
    view_type = filters['period']
    selected_country = filters['country']
    selected_zone = filters['zone']
    selected_year = filters['year']
    selected_month_name = filters.get('month', 'All')  # Keep the name for display
    selected_month = get_month_number(selected_month_name)
    if selected_month is None:
        selected_month = 'All'
    
    # Service Type Toggle (Quality-specific)
    service_type = st.radio("Service Type", ["Water", "Sanitation", "Both"], horizontal=True, key="service_type_toggle_quality")

    # --- Apply Filters using standardized helper ---
    df_s_filt = apply_standard_filters(df_service, filters, year_col='year', month_col='month')
    df_b_filt = apply_standard_filters(df_billing, filters, year_col='year', month_col='month') if not df_billing.empty else df_billing
    df_f_filt = apply_standard_filters(df_fin, filters, year_col='year', month_col='month') if not df_fin.empty else df_fin
    df_p_filt = apply_standard_filters(df_prod, filters, year_col='year', month_col='month') if not df_prod.empty else df_prod
    
    # National Data (Annual - uses date_YY column)
    df_n_filt = df_national.copy()
    if not df_n_filt.empty:
        if selected_country != 'All' and 'country' in df_n_filt.columns:
            df_n_filt = df_n_filt[df_n_filt['country'].str.lower() == selected_country.lower()]
        if 'date_YY' in df_n_filt.columns and selected_year:
            df_n_filt = _safe_year_filter(df_n_filt, 'date_YY', selected_year)

    # --- Populate Header with Export Button ---
    with header_container:
        h_col1, h_col2 = st.columns([6, 1])
        with h_col1:
            st.markdown("<h1 style='font-size: 24px; font-weight: 700; color: #111827; margin-bottom: 16px;'>Service & Quality</h1>", unsafe_allow_html=True)
        with h_col2:
            st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True) # Spacer for alignment
            csv = df_s_filt.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Export CSV",
                data=csv,
                file_name=f"quality_data_{selected_country}_{selected_year}.csv",
                mime="text/csv",
                key="export_btn_quality"
            )

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
            font-size: 24px;
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
        .delta-warn { color: #d97706; }
        
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
    
    # --- Calculations ---

    # 1. Water Quality Compliance
    passed_cl = df_s_filt['test_passed_chlorine'].sum()
    conducted_cl = df_s_filt['tests_conducted_chlorine'].sum()
    passed_ec = df_s_filt['tests_passed_ecoli'].sum()
    conducted_ec = df_s_filt['test_conducted_ecoli'].sum()
    
    rate_cl = (passed_cl / conducted_cl * 100) if conducted_cl > 0 else 0
    rate_ec = (passed_ec / conducted_ec * 100) if conducted_ec > 0 else 0
    
    total_passed = passed_cl + passed_ec
    total_conducted = conducted_cl + conducted_ec
    compliance_rate = (total_passed / total_conducted * 100) if total_conducted > 0 else 0
    
    # 2. Service Continuity
    avg_service_hours = df_p_filt['service_hours'].mean() if not df_p_filt.empty and 'service_hours' in df_p_filt.columns else 0
    
    # 3. Complaint Resolution
    total_complaints = df_s_filt['complaints'].sum()
    total_resolved = df_s_filt['resolved'].sum()
    resolution_rate = (total_resolved / total_complaints * 100) if total_complaints > 0 else 0
    
    avg_res_time = df_n_filt['complaint_resolution'].mean() if not df_n_filt.empty and 'complaint_resolution' in df_n_filt.columns else None
    
    # 4. Network Performance (Blockages)
    total_blocks = df_f_filt['blocks'].sum() if not df_f_filt.empty and 'blocks' in df_f_filt.columns else 0
    # Sewer length is annual, take max or sum depending on context. Assuming sum of lengths of selected cities.
    # If multiple cities selected, sum their lengths. If one city, max is fine (it's constant per year usually).
    # Let's sum unique city lengths if possible, or just sum all rows if filtered by year.
    # df_f_filt is already filtered by year.
    total_sewer_length = df_f_filt['sewer_length'].sum() if not df_f_filt.empty and 'sewer_length' in df_f_filt.columns else 0
    # Note: financial data is monthly, so sewer_length might be repeated. We should take max per city then sum.
    if not df_f_filt.empty and 'sewer_length' in df_f_filt.columns and 'city' in df_f_filt.columns:
        total_sewer_length = df_f_filt.groupby('city')['sewer_length'].max().sum()
    
    blocks_per_100km = (total_blocks / total_sewer_length * 100) if total_sewer_length > 0 else 0
    
    # 5. Asset Health
    asset_health_score = df_n_filt['asset_health'].mean() if not df_n_filt.empty and 'asset_health' in df_n_filt.columns else None

    # --- Render Cards with Domain-Specific Styling ---
    c1, c2, c3, c4, c5 = st.columns(5)
    
    # Card 1: Water Quality (Water Domain)
    with c1:
        color_cls = "delta-up" if compliance_rate > 95 else ("delta-warn" if compliance_rate >= 85 else "delta-down")
        color_hex = "#16A34A" if compliance_rate > 95 else ("#EAB308" if compliance_rate >= 85 else "#DC2626")
        alert_icon = "⚠️" if compliance_rate < 95 else "✅"
        
        st.markdown(f"""
        <div class='metric-container scorecard-water'>
            <div>
                <div class='domain-pill domain-pill-water' style='margin-bottom: 6px;'>💧 Water</div>
                <div class='metric-label'>Water Quality {alert_icon}</div>
                <div class='metric-value' style='color: {color_hex}'>{compliance_rate:.1f}%</div>
                <div class='metric-sub'>Samples meeting stds</div>
            </div>
            <div class='metric-delta delta-neutral' style='font-size: 11px;'>
                Cl: {rate_cl:.1f}% | E.coli: {rate_ec:.1f}%
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    # Card 2: Service Continuity (Water Domain)
    with c2:
        st.markdown(f"""
        <div class='metric-container scorecard-water'>
            <div>
                <div class='domain-pill domain-pill-water' style='margin-bottom: 6px;'>💧 Water</div>
                <div class='metric-label'>Service Continuity</div>
                <div class='metric-value metric-value-water'>{avg_service_hours:.1f} <span style='font-size:14px'>hrs/day</span></div>
            </div>
            <div class='metric-delta delta-neutral'>
                Target: 24 hours
                <br>24x7 Supply: N/A
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    # Card 3: Complaint Resolution
    with c3:
        # Sparkline for resolution rate
        if not df_s_filt.empty:
            monthly_res = df_s_filt.groupby('month').apply(
                lambda x: (x['resolved'].sum() / x['complaints'].sum() * 100) if x['complaints'].sum() > 0 else 0
            ).reset_index(name='rate')
            
            # Create a simple sparkline using plotly
            fig_spark = go.Figure(go.Scatter(
                x=monthly_res['month'], 
                y=monthly_res['rate'], 
                mode='lines', 
                line=dict(color='#60a5fa', width=2),
                fill='tozeroy',
                fillcolor='rgba(96, 165, 250, 0.1)'
            ))
            fig_spark.update_layout(
                height=30, margin=dict(l=0, r=0, t=0, b=0), 
                xaxis=dict(visible=False), yaxis=dict(visible=False),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
            )
            
        res_time_str = f"{avg_res_time:.1f} days" if avg_res_time is not None else "N/A"
        
        st.markdown(f"""
        <div class='metric-container'>
            <div>
                <div class='metric-label'>Complaint Resolution</div>
                <div class='metric-value'>{resolution_rate:.1f}%</div>
                <div class='metric-sub'>Avg Time: {res_time_str}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if not df_s_filt.empty:
            st.plotly_chart(fig_spark, use_container_width=True, config={'displayModeBar': False})

    # Card 4: Network Performance
    with c4:
        # Inverse scale: Lower is better
        # Let's say < 10 is Green, 10-50 Yellow, > 50 Red (Arbitrary thresholds)
        net_color = "#16A34A" if blocks_per_100km < 10 else ("#EAB308" if blocks_per_100km < 50 else "#DC2626")
        
        st.markdown(f"""
        <div class='metric-container'>
            <div>
                <div class='metric-label'>Network Perf. 🔧</div>
                <div class='metric-value' style='color: {net_color}'>{blocks_per_100km:.1f}</div>
                <div class='metric-sub'>Blockages / 100km</div>
            </div>
            <div class='metric-delta delta-neutral'>
                Total: {total_blocks:,.0f} blocks
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Card 5: Asset Health
    with c5:
        if asset_health_score is not None:
            # Determine color and category
            if asset_health_score >= 75:
                health_cat = "Good"
                health_color = "#16A34A" # Green
            elif asset_health_score >= 50:
                health_cat = "Fair"
                health_color = "#EAB308" # Yellow
            else:
                health_cat = "Poor"
                health_color = "#DC2626" # Red
            
            st.markdown(f"""
            <div class='metric-container'>
                <div class='metric-label'>Asset Health</div>
                <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 10px;">
                    <div>
                        <div class='metric-value' style='color: {{health_color}}'>{{asset_health_score:.1f}}%</div>
                        <div class='metric-sub' style='color: {{health_color}}; font-weight: 600;'>{{health_cat}}</div>
                    </div>
                    <div style="position: relative; width: 60px; height: 60px; border-radius: 50%; background: conic-gradient({{health_color}} {{asset_health_score}}%, #f3f4f6 0);">
                        <div style="position: absolute; top: 6px; left: 6px; right: 6px; bottom: 6px; background: white; border-radius: 50%;"></div>
                    </div>
                </div>
                <div class='metric-delta delta-neutral' style="margin-top: auto;">
                    Annual Assessment
                </div>
            </div>
            """.format(health_color=health_color, asset_health_score=asset_health_score, health_cat=health_cat), unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class='metric-container'>
                <div class='metric-label'>Asset Health</div>
                <div class='metric-value' style='font-size: 16px; color: #9ca3af;'>Pending</div>
                <div class='metric-sub'>Annual assessment</div>
            </div>
            """, unsafe_allow_html=True)

    # ============================================================================
    # TABBED ANALYSIS SECTIONS
    # ============================================================================
    
    st.markdown("---")
    st.subheader("📊 Quality Analysis")
    
    quality_tab1, quality_tab2, quality_tab3 = st.tabs(["💧 Water Quality", "🚿 Sanitation", "📞 Customer Service"])
    
    # ============================================================================
    # TAB 1: Water Quality Deep Dive
    # ============================================================================
    with quality_tab1:
        st.markdown("### Water Quality Deep Dive")
        st.markdown("Water testing performance and contaminant trend analysis.")
        
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
                marker_color='#cbd5e1',
                text=chart_data['tests_chlorine'].apply(lambda x: f"{x:.0f}"),
                textposition='auto'
            ))
            
            # 2. Conducted
            fig_perf.add_trace(go.Bar(
                y=chart_data[group_col],
                x=chart_data['tests_conducted_chlorine'],
                name='Conducted',
                orientation='h',
                marker_color='#60a5fa',
                text=chart_data.apply(lambda row: f"{row['tests_conducted_chlorine']:.0f} (conducted rate {row['conduct_rate']:.1f}%)", axis=1),
                textposition='auto'
            ))
            
            # 3. Passed
            fig_perf.add_trace(go.Bar(
                y=chart_data[group_col],
                x=chart_data['test_passed_chlorine'],
                name='Passed',
                orientation='h',
                marker_color='#34d399',
                text=chart_data.apply(lambda row: f"{row['test_passed_chlorine']:.0f} (passed rate {row['pass_rate']:.1f}%)", axis=1),
                textposition='auto'
            ))

            fig_perf.update_layout(
                height=300 + (len(chart_data) * 20 if len(chart_data) > 5 else 0), # Dynamic height
                margin=dict(l=0, r=0, t=30, b=0),
                barmode='group',
                legend=dict(orientation="v", y=0.5, x=1.02, xanchor="left", yanchor="middle"),
                title=dict(text=f"{title_suffix}", font=dict(size=14)),
                xaxis_title="Number of Tests"
            )
            
            st.plotly_chart(fig_perf, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with q_col2:
            #st.markdown("<div class='chart-container'>", unsafe_allow_html=True)
            st.markdown("**Contaminant Trends: Chlorine vs E. Coli Pass Rate**")
            
            # Check if date column exists
            if 'date' not in df_service.columns:
                st.warning("⚠️ Date column not available for trend analysis")
            elif selected_month == 'All':
                # Line Chart with Range Slider (Multi-year view for YoY comparison)
                # Use df_service (unfiltered by year) but filtered by country/zone (case-insensitive)
                df_chart = df_service.copy()
                if selected_country != 'All':
                    df_chart = df_chart[df_chart['country'].str.lower() == selected_country.lower()]
                if selected_zone != 'All':
                    df_chart = df_chart[df_chart['zone'].str.lower() == selected_zone.lower()]
                
                if df_chart.empty:
                    st.info("No data available for selected filters")
                else:
                    ts_quality = df_chart.groupby('date').agg({
                        'test_passed_chlorine': 'sum',
                        'tests_conducted_chlorine': 'sum',
                        'tests_passed_ecoli': 'sum',
                        'test_conducted_ecoli': 'sum'
                    }).reset_index()
                    
                    ts_quality['Chlorine %'] = (ts_quality['test_passed_chlorine'] / ts_quality['tests_conducted_chlorine'] * 100).fillna(0)
                    ts_quality['E. Coli %'] = (ts_quality['tests_passed_ecoli'] / ts_quality['test_conducted_ecoli'] * 100).fillna(0)
                    
                    fig_trend = go.Figure()
                    fig_trend.add_trace(go.Scatter(
                        x=ts_quality['date'], 
                        y=ts_quality['Chlorine %'], 
                        name='Chlorine', 
                        line=dict(color='#60a5fa', width=2),
                        mode='lines',
                        hovertemplate='<b>Chlorine</b><br>Date: %{x|%b %Y}<br>Pass Rate: %{y:.1f}%<extra></extra>'
                    ))
                    fig_trend.add_trace(go.Scatter(
                        x=ts_quality['date'], 
                        y=ts_quality['E. Coli %'], 
                        name='E. Coli', 
                        line=dict(color='#f87171', width=2),
                        mode='lines',
                        hovertemplate='<b>E. Coli</b><br>Date: %{x|%b %Y}<br>Pass Rate: %{y:.1f}%<extra></extra>'
                    ))
                    
                    # Add WHO Threshold
                    fig_trend.add_hline(y=95, line_dash="dash", line_color="#4ade80", annotation_text="WHO Std (95%)", annotation_position="top right", annotation_font_color="#4ade80")

                    fig_trend.update_layout(
                        height=350,  # Increased height for better visibility
                        margin=dict(l=0, r=0, t=20, b=40), 
                        legend=dict(orientation="h", y=1.15, x=0.5, xanchor='center'),
                        xaxis=dict(
                            rangeslider=dict(visible=True, thickness=0.08),
                            type="date",
                            range=[f"{selected_year}-01-01", f"{selected_year}-12-31"] if selected_year else None,
                            tickformat='%b %Y',
                            dtick='M2',  # Show tick every 2 months for less clutter
                            showgrid=True,
                            gridcolor='rgba(128,128,128,0.1)'
                        ),
                        yaxis=dict(
                            title="Pass Rate (%)",
                            range=[0, 105],
                            showgrid=True,
                            gridcolor='rgba(128,128,128,0.1)'
                        ),
                        hovermode='x unified',
                        plot_bgcolor='rgba(250,250,250,0.3)'
                    )
                    st.plotly_chart(fig_trend, use_container_width=True)
                
            elif selected_month != 'All':
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
                    fig_bar.add_trace(go.Bar(x=bar_data[group_col], y=bar_data['Chlorine %'], name='Chlorine', marker_color='#60a5fa'))
                    fig_bar.add_trace(go.Bar(x=bar_data[group_col], y=bar_data['E. Coli %'], name='E. Coli', marker_color='#f87171'))
                    
                    # Add WHO Threshold
                    fig_bar.add_hline(y=95, line_dash="dash", line_color="#4ade80", annotation_text="WHO Std (95%)", annotation_position="top right", annotation_font_color="#4ade80")

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
                    fig_bar.add_trace(go.Bar(x=['Chlorine', 'E. Coli'], y=[rate_cl, rate_ec], marker_color=['#60a5fa', '#f87171']))
                    
                    # Add WHO Threshold
                    fig_bar.add_hline(y=95, line_dash="dash", line_color="#4ade80", annotation_text="WHO Std (95%)", annotation_position="top right", annotation_font_color="#4ade80")

                    fig_bar.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0), showlegend=False, yaxis_title="Pass Rate (%)")
                    st.plotly_chart(fig_bar, use_container_width=True)
            
            # Quality Alert Box
            # Calculate compliance per zone
            zone_compliance = df_s_filt.groupby('zone').apply(
                lambda x: ((x['test_passed_chlorine'].sum() + x['tests_passed_ecoli'].sum()) / 
                           (x['tests_conducted_chlorine'].sum() + x['test_conducted_ecoli'].sum()) * 100)
                if (x['tests_conducted_chlorine'].sum() + x['test_conducted_ecoli'].sum()) > 0 else 0
            )
            
            non_compliant_zones = zone_compliance[zone_compliance < 80]
            
            if not non_compliant_zones.empty:
                st.markdown("""
                <div style="background-color: #fee2e2; border: 1px solid #ef4444; border-radius: 8px; padding: 12px; margin-top: 16px;">
                    <div style="display: flex; align-items: center; gap: 8px; color: #b91c1c; font-weight: 600; margin-bottom: 8px;">
                        <span>⚠️ Quality Alert: Critical Compliance Issues</span>
                    </div>
                    <div style="font-size: 13px; color: #7f1d1d;">
                        The following zones have dropped below 80% compliance:
                        <ul style="margin: 4px 0 8px 20px; padding: 0;">
                """ + "".join([f"<li><b>{zone}</b>: {score:.1f}%</li>" for zone, score in non_compliant_zones.items()]) + """
                        </ul>
                        <b>Required Actions:</b>
                        <ul style="margin: 4px 0 0 20px; padding: 0;">
                            <li>Immediate flushing of distribution lines</li>
                            <li>Increase chlorine dosage at treatment plant</li>
                            <li>Deploy emergency water tankers if necessary</li>
                        </ul>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

    # ============================================================================
    # TAB 2: Sanitation Check
    # ============================================================================
    with quality_tab2:
        if service_type in ["Sanitation", "Both"]:
            st.markdown("### Sanitation Check")
            st.markdown("Wastewater treatment efficiency and sewer health metrics.")
            
            s_col1, s_col2 = st.columns(2)
        
            with s_col1:
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
                    marker=dict(color=["#60a5fa", "#818cf8", "#a78bfa"])
                ))
                fig_funnel.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig_funnel, use_container_width=True)

            with s_col2:
                st.markdown("**Sewer Health: Blockages**")
                
                # Blockages from financial data
                total_blocks = df_f_filt['blocks'].sum() if not df_f_filt.empty else 0
                
                # Trend if possible
                if not df_f_filt.empty:
                    blocks_trend = df_f_filt.groupby('date')['blocks'].sum().reset_index()
                    fig_blocks = px.line(blocks_trend, x='date', y='blocks', markers=True)
                    fig_blocks.update_traces(line_color='#f87171')
                    fig_blocks.update_layout(height=220, margin=dict(l=0, r=0, t=0, b=0), yaxis_title="Blockages")
                    
                    st.metric("Total Blockages (Selected Period)", f"{total_blocks:,.0f}", help="Total sewer blockages reported")
                    st.plotly_chart(fig_blocks, use_container_width=True)
                else:
                    st.info("No blockage data available for selected filters.")
        else:
            st.info("Select 'Sanitation' or 'Both' in the Service Type filter to view sanitation metrics.")

    # ============================================================================
    # TAB 3: Customer Service Performance
    # ============================================================================
    with quality_tab3:
        st.markdown("### Customer Service Performance")
        st.markdown("Complaints analysis and resolution efficiency.")
        
        # Since detailed complaint data is missing, we create a demo section with blurred background
        
        # Alert Box
        st.markdown("""
        <div style="background-color: #fefce8; border: 1px solid #fde047; border-radius: 8px; padding: 12px; margin-bottom: 16px; display: flex; align-items: center; gap: 10px;">
            <div style="font-size: 20px;">⚠️</div>
            <div style="color: #854d0e; font-size: 14px;">
                <strong>Data Unavailable:</strong> Detailed complaint categorization and resolution stage data is currently not being collected. 
                The visualizations below are a <strong>demonstration</strong> of the intended dashboard capabilities once data collection improves.
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Layout
        cs_col1, cs_col2, cs_col3 = st.columns([4, 3, 3])
        
        # --- Left: Complaints Analysis (Demo) ---
        with cs_col1:
            st.markdown("**Complaints Analysis (Demo)**")
            
            # Demo Data
            dates = pd.date_range(start='2024-01-01', periods=12, freq='M')
            demo_complaints = pd.DataFrame({
                'Date': dates,
                'No Water': [120, 135, 110, 140, 160, 155, 130, 125, 145, 150, 135, 120],
                'Low Pressure': [80, 85, 90, 95, 100, 110, 105, 100, 95, 90, 85, 80],
                'Quality Issues': [40, 35, 45, 50, 55, 60, 50, 45, 40, 35, 30, 25],
                'Billing': [60, 65, 70, 65, 60, 55, 60, 65, 70, 75, 80, 85],
                'Leakage': [30, 25, 30, 35, 40, 45, 40, 35, 30, 25, 20, 15]
            })
            
            # Toggle (Visual only for demo)
            st.radio("View Mode", ["Volume", "Percentage"], horizontal=True, label_visibility="collapsed", key="cs_demo_toggle", disabled=True)
            
            fig_complaints = go.Figure()
            fig_complaints.add_trace(go.Scatter(x=demo_complaints['Date'], y=demo_complaints['No Water'], mode='lines', stackgroup='one', name='No Water', line=dict(width=0.5, color='#60a5fa')))
            fig_complaints.add_trace(go.Scatter(x=demo_complaints['Date'], y=demo_complaints['Low Pressure'], mode='lines', stackgroup='one', name='Low Pressure', line=dict(width=0.5, color='#bfdbfe')))
            fig_complaints.add_trace(go.Scatter(x=demo_complaints['Date'], y=demo_complaints['Quality Issues'], mode='lines', stackgroup='one', name='Quality Issues', line=dict(width=0.5, color='#fdba74')))
            fig_complaints.add_trace(go.Scatter(x=demo_complaints['Date'], y=demo_complaints['Billing'], mode='lines', stackgroup='one', name='Billing', line=dict(width=0.5, color='#4ade80')))
            fig_complaints.add_trace(go.Scatter(x=demo_complaints['Date'], y=demo_complaints['Leakage'], mode='lines', stackgroup='one', name='Leakage', line=dict(width=0.5, color='#c084fc')))
            
            fig_complaints.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0), legend=dict(orientation="h", y=1.1))
            
            # Add No Data Annotation
            fig_complaints.add_annotation(
                text="NO DATA AVAILABLE",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=20, color="#374151"),
                bgcolor="rgba(255,255,255,0.7)",
                borderpad=10
            )
            
            # Apply blur effect via CSS injection on the specific element is hard, so we wrap in a div with style
            st.markdown('<div style="filter: blur(2px); opacity: 0.6; pointer-events: none;">', unsafe_allow_html=True)
            st.plotly_chart(fig_complaints, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # --- Center: Resolution Efficiency (Demo) ---
        with cs_col2:
            st.markdown("**Resolution Efficiency (Demo)**")
            
            fig_funnel = go.Figure(go.Funnel(
                y = ["Received", "Acknowledged", "In Progress", "Resolved", "Satisfied"],
                x = [1000, 950, 800, 750, 600],
                textinfo = "value+percent initial",
                marker = dict(color = ["#60a5fa", "#93c5fd", "#bfdbfe", "#dbeafe", "#eff6ff"])
            ))
            
            fig_funnel.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0))
            
            # Add No Data Annotation
            fig_funnel.add_annotation(
                text="NO DATA AVAILABLE",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=20, color="#374151"),
                bgcolor="rgba(255,255,255,0.7)",
                borderpad=10
            )
            
            st.markdown('<div style="filter: blur(2px); opacity: 0.6; pointer-events: none;">', unsafe_allow_html=True)
            st.plotly_chart(fig_funnel, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # --- Right: Service Speed Metrics (Demo) ---
        with cs_col3:
            st.markdown("**Service Speed (Demo)**")
            
            # Demo Box Plot Data
            y0 = [2, 3, 4, 4, 5, 6, 7, 8, 9] # No Water
            y1 = [1, 2, 2, 3, 3, 4, 5] # Leakage
            y2 = [5, 6, 7, 8, 9, 10, 12] # Billing
            
            fig_box = go.Figure()
            fig_box.add_trace(go.Box(y=y0, name='No Water', marker_color='#60a5fa'))
            fig_box.add_trace(go.Box(y=y1, name='Leakage', marker_color='#c084fc'))
            fig_box.add_trace(go.Box(y=y2, name='Billing', marker_color='#4ade80'))
            
            # Target Line
            fig_box.add_hline(y=3, line_dash="dash", line_color="#f87171", annotation_text="SLA Target (3 days)", annotation_position="bottom right")
            
            fig_box.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0), showlegend=False, yaxis_title="Days to Resolve")
            
            # Add No Data Annotation
            fig_box.add_annotation(
                text="NO DATA AVAILABLE",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=20, color="#374151"),
                bgcolor="rgba(255,255,255,0.7)",
                borderpad=10
            )
            
            st.markdown('<div style="filter: blur(2px); opacity: 0.6; pointer-events: none;">', unsafe_allow_html=True)
            st.plotly_chart(fig_box, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # ============================================================================
    # ORGANIZATIONAL CAPACITY SECTION (with tabs)
    # ============================================================================
    
    st.markdown("---")
    st.subheader("👥 Organizational Capacity")
    
    org_tab1, org_tab2, org_tab3 = st.tabs(["📊 Staff Metrics", "📋 Training Matrix", "📈 Diversity & Efficiency"])
    
    # Alert Box (shown once above all tabs)
    st.markdown("""
    <div style="background-color: #fefce8; border: 1px solid #fde047; border-radius: 8px; padding: 12px; margin-bottom: 16px; display: flex; align-items: center; gap: 10px;">
        <div style="font-size: 20px;">⚠️</div>
        <div style="color: #854d0e; font-size: 14px;">
            <strong>Data Unavailable:</strong> Detailed gender-disaggregated workforce data and training records are currently not being collected. 
            The visualizations below are a <strong>demonstration</strong> of the intended dashboard capabilities.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # TAB 1: Staff Metrics
    with org_tab1:
        st.markdown("**Staff Composition & Efficiency (Demo)**")
        
        # Demo Data
        staff_cats = ['Water Supply', 'Sanitation']
        total_staff = [150, 120]
        trained_staff = [90, 60]
        male_staff = [110, 100]
        female_staff = [40, 20]
        efficiency = [2.5, 4.1] # Staff per 1000 connections

        fig_staff = go.Figure()
        
        # Bars
        fig_staff.add_trace(go.Bar(x=staff_cats, y=total_staff, name='Total Staff', marker_color='#9ca3af'))
        fig_staff.add_trace(go.Bar(x=staff_cats, y=trained_staff, name='Trained', marker_color='#60a5fa'))
        fig_staff.add_trace(go.Bar(x=staff_cats, y=male_staff, name='Male', marker_color='#2563eb')) # Dark Blue
        fig_staff.add_trace(go.Bar(x=staff_cats, y=female_staff, name='Female', marker_color='#f472b6')) # Pink
        
        # Line Overlay (Secondary Y)
        fig_staff.add_trace(go.Scatter(
            x=staff_cats, y=efficiency, name='Efficiency (Staff/1000 conn)',
            mode='lines+markers', yaxis='y2', line=dict(color='#fbbf24', width=3)
        ))

        fig_staff.update_layout(
            height=350, margin=dict(l=0, r=0, t=20, b=0),
            barmode='group',
            legend=dict(orientation="h", y=1.1),
            yaxis2=dict(title="Staff/1000 Conn", overlaying='y', side='right', showgrid=False)
        )

        st.markdown('<div style="filter: blur(2px); opacity: 0.6; pointer-events: none;">', unsafe_allow_html=True)
        st.plotly_chart(fig_staff, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # TAB 2: Training Matrix
    with org_tab2:
        st.markdown("**Training Completion Matrix (Demo)**")
        
        # Demo Data
        header = ['Category', 'Q1', 'Q2', 'Q3', 'Q4']
        cells = [
            ['Technical Ops', 'Safety', 'Management', 'Soft Skills'], # Category
            ['15 (10M/5F)', '20 (15M/5F)', '5 (3M/2F)', '10 (5M/5F)'], # Q1
            ['12 (8M/4F)', '18 (14M/4F)', '6 (4M/2F)', '12 (6M/6F)'], # Q2
            ['18 (12M/6F)', '22 (18M/4F)', '4 (2M/2F)', '15 (8M/7F)'], # Q3
            ['10 (6M/4F)', '15 (12M/3F)', '8 (5M/3F)', '8 (4M/4F)']  # Q4
        ]
        
        # Heatmap coloring simulation (just random colors for demo)
        fill_colors = [
            ['#f3f4f6']*4, # Col 1
            ['#dbeafe', '#bfdbfe', '#dbeafe', '#bfdbfe'], # Q1
            ['#bfdbfe', '#93c5fd', '#bfdbfe', '#93c5fd'], # Q2
            ['#93c5fd', '#60a5fa', '#93c5fd', '#60a5fa'], # Q3
            ['#dbeafe', '#bfdbfe', '#dbeafe', '#bfdbfe']  # Q4
        ]

        fig_table = go.Figure(data=[go.Table(
            header=dict(values=header, fill_color='#f9fafb', align='left', font=dict(color='black', size=12)),
            cells=dict(values=cells, fill_color=fill_colors, align='left', font=dict(color='black', size=11), height=40)
        )])
        
        fig_table.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=0))

        # Add No Data Annotation
        fig_table.add_annotation(
            text="NO DATA AVAILABLE",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=20, color="#374151"),
            bgcolor="rgba(255,255,255,0.7)",
            borderpad=10
        )

        st.markdown('<div style="filter: blur(2px); opacity: 0.6; pointer-events: none;">', unsafe_allow_html=True)
        st.plotly_chart(fig_table, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # TAB 3: Diversity & Efficiency
    with org_tab3:
        st.markdown("**Diversity & Efficiency (Demo)**")
        
        div_col1, div_col2 = st.columns(2)
        
        with div_col1:
            # 1. Women in Decision Making (Ring Chart)
            current_pct = 18
            target_pct = 30
            
            fig_ring = go.Figure(go.Pie(
                values=[current_pct, 100-current_pct],
                labels=['Women', 'Other'],
                hole=0.7,
                marker_colors=['#f472b6', '#d1d5db'],
                textinfo='none',
                sort=False
            ))
            
            fig_ring.add_annotation(text=f"{current_pct}%", x=0.5, y=0.5, font_size=20, showarrow=False, font_weight='bold', font_color='#f472b6')
            fig_ring.add_annotation(text=f"Target: {target_pct}%", x=0.5, y=0.35, font_size=10, showarrow=False, font_color='#6b7280')
            
            fig_ring.update_layout(height=200, margin=dict(l=0, r=0, t=30, b=0), title=dict(text="Women in Leadership", font=dict(size=12), x=0.5, xanchor='center'))
            
            st.markdown('<div style="filter: blur(2px); opacity: 0.6; pointer-events: none;">', unsafe_allow_html=True)
            st.plotly_chart(fig_ring, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with div_col2:
            # 2. Staff Efficiency (Gauge)
            eff_val = 4.2
            
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = eff_val,
                title = {'text': "Staff / 1000 Conn", 'font': {'size': 12}},
                gauge = {
                    'axis': {'range': [0, 10], 'tickwidth': 1, 'tickcolor': "darkblue"},
                    'bar': {'color': "black", 'thickness': 0.0}, # Hide bar, use needle if possible, or just bar
                    'steps': [
                        {'range': [0, 3], 'color': "#4ade80"},
                        {'range': [3, 5], 'color': "#facc15"},
                        {'range': [5, 10], 'color': "#f87171"}
                    ],
                    'threshold': {
                        'line': {'color': "black", 'width': 4},
                        'thickness': 0.75,
                        'value': eff_val
                    }
                }
            ))
            
            fig_gauge.update_layout(height=140, margin=dict(l=20, r=20, t=30, b=0))
            
            st.markdown('<div style="filter: blur(2px); opacity: 0.6; pointer-events: none;">', unsafe_allow_html=True)
            st.plotly_chart(fig_gauge, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # ============================================================================
    # DATA EXPORT SECTION
    # ============================================================================
    
    st.markdown("---")
    st.markdown("<div class='section-header'>📦 Data Export</div>", unsafe_allow_html=True)
    
    export_tab1, export_tab2 = st.tabs(["📊 Service Data", "📈 Calculated Metrics"])
    
    # TAB 1: SERVICE DATA EXPORT
    with export_tab1:
        st.markdown("**Export filtered service data**")
        
        # Display options
        show_all_cols = st.checkbox("Show all columns", value=False, key="show_all_quality")
        
        if show_all_cols:
            display_df = df_s_filt
        else:
            key_columns = ['country', 'zone', 'year', 'month', 'tests_conducted_chlorine', 'test_passed_chlorine', 
                          'test_conducted_ecoli', 'tests_passed_ecoli', 'complaints', 'resolved']
            display_df = df_s_filt[[col for col in key_columns if col in df_s_filt.columns]]
        
        st.dataframe(display_df, use_container_width=True, height=400)
        
        # Export options
        export_col1, export_col2, export_col3 = st.columns(3)
        
        with export_col1:
            csv_data = df_s_filt.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download as CSV",
                data=csv_data,
                file_name=f"service_quality_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_quality_csv"
            )
        
        with export_col2:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_s_filt.to_excel(writer, sheet_name='Service Data', index=False)
            buffer.seek(0)
            
            st.download_button(
                label="📥 Download as Excel",
                data=buffer,
                file_name=f"service_quality_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_quality_excel"
            )
        
        with export_col3:
            json_str = df_s_filt.to_json(orient='records', indent=2, default_handler=str)
            st.download_button(
                label="📥 Download as JSON",
                data=json_str,
                file_name=f"service_quality_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="download_quality_json"
            )
    
    # TAB 2: CALCULATED METRICS EXPORT
    with export_tab2:
        st.markdown("**All calculated quality metrics in one file**")
        st.info("📌 This file contains all derived metrics calculated from the raw data for easy analysis and reporting.")
        
        # Zone-Level Metrics
        zone_metrics = pd.DataFrame()
        if 'zone' in df_s_filt.columns:
            zone_agg = df_s_filt.groupby('zone').agg({
                'tests_conducted_chlorine': 'sum',
                'test_passed_chlorine': 'sum',
                'test_conducted_ecoli': 'sum',
                'tests_passed_ecoli': 'sum',
                'complaints': 'sum',
                'resolved': 'sum'
            }).reset_index()
            
            # Calculate rates
            zone_agg['chlorine_compliance_rate'] = (zone_agg['test_passed_chlorine'] / zone_agg['tests_conducted_chlorine'] * 100).fillna(0)
            zone_agg['ecoli_compliance_rate'] = (zone_agg['tests_passed_ecoli'] / zone_agg['test_conducted_ecoli'] * 100).fillna(0)
            zone_agg['resolution_rate'] = (zone_agg['resolved'] / zone_agg['complaints'] * 100).fillna(0)
            zone_agg['metric_type'] = 'Zone Summary'
            zone_metrics = zone_agg
        
        # Monthly Trend Metrics
        monthly_metrics = pd.DataFrame()
        if 'year' in df_s_filt.columns and 'month' in df_s_filt.columns:
            monthly_agg = df_s_filt.groupby(['year', 'month']).agg({
                'tests_conducted_chlorine': 'sum',
                'test_passed_chlorine': 'sum',
                'complaints': 'sum',
                'resolved': 'sum'
            }).reset_index()
            
            monthly_agg['compliance_rate'] = (monthly_agg['test_passed_chlorine'] / monthly_agg['tests_conducted_chlorine'] * 100).fillna(0)
            monthly_agg['resolution_rate'] = (monthly_agg['resolved'] / monthly_agg['complaints'] * 100).fillna(0)
            monthly_agg['metric_type'] = 'Monthly Trend'
            monthly_metrics = monthly_agg
        
        # Overall Summary Metrics
        summary_metrics = pd.DataFrame({
            'Metric': [
                'Water Quality Compliance Rate (%)',
                'Chlorine Test Compliance (%)',
                'E.Coli Test Compliance (%)',
                'Total Complaints',
                'Total Resolved',
                'Complaint Resolution Rate (%)',
                'Average Service Hours',
                'Blocks per 100km Sewer',
                'Asset Health Score',
                'Total Tests Conducted (Chlorine)',
                'Total Tests Conducted (E.Coli)',
                'Report Generated',
                'Data Period'
            ],
            'Value': [
                f"{compliance_rate:.2f}",
                f"{rate_cl:.2f}",
                f"{rate_ec:.2f}",
                f"{total_complaints:,.0f}",
                f"{total_resolved:,.0f}",
                f"{resolution_rate:.2f}",
                f"{avg_service_hours:.2f}",
                f"{blocks_per_100km:.2f}",
                f"{asset_health_score:.2f}" if asset_health_score is not None else "N/A",
                f"{conducted_cl:,.0f}",
                f"{conducted_ec:,.0f}",
                pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                f"Year {selected_year}" if selected_year else "All Years"
            ]
        })
        
        # Display zone metrics if available
        if not zone_metrics.empty:
            st.subheader("Zone-Level Metrics")
            st.dataframe(zone_metrics, use_container_width=True, height=200)
        
        # Display monthly metrics if available
        if not monthly_metrics.empty:
            st.subheader("Monthly Trend Metrics")
            st.dataframe(monthly_metrics, use_container_width=True, height=200)
        
        # Display summary metrics
        st.subheader("Overall Summary Metrics")
        st.dataframe(summary_metrics, use_container_width=True, height=300)
        
        # Export calculated metrics
        export_metric_col1, export_metric_col2, export_metric_col3 = st.columns(3)
        
        with export_metric_col1:
            # Combined metrics CSV
            combined_metrics_list = [summary_metrics.assign(metric_category='Overall_Summary')]
            if not zone_metrics.empty:
                combined_metrics_list.insert(0, zone_metrics.assign(metric_category='Zone_Level'))
            if not monthly_metrics.empty:
                combined_metrics_list.insert(0, monthly_metrics.assign(metric_category='Monthly_Trend'))
            
            combined_metrics = pd.concat(combined_metrics_list, ignore_index=True, sort=False)
            
            csv_metrics = combined_metrics.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Metrics as CSV",
                data=csv_metrics,
                file_name=f"quality_metrics_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_quality_metrics_csv"
            )
        
        with export_metric_col2:
            # Excel with multiple sheets
            buffer_metrics = io.BytesIO()
            with pd.ExcelWriter(buffer_metrics, engine='openpyxl') as writer:
                if not zone_metrics.empty:
                    zone_metrics.to_excel(writer, sheet_name='Zone_Metrics', index=False)
                if not monthly_metrics.empty:
                    monthly_metrics.to_excel(writer, sheet_name='Monthly_Metrics', index=False)
                summary_metrics.to_excel(writer, sheet_name='Summary_Metrics', index=False)
            buffer_metrics.seek(0)
            
            st.download_button(
                label="📥 Download Metrics as Excel",
                data=buffer_metrics,
                file_name=f"quality_metrics_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_quality_metrics_excel"
            )
        
        with export_metric_col3:
            # JSON export for metrics
            metrics_json = {
                'zone_metrics': zone_metrics.to_dict(orient='records') if not zone_metrics.empty else [],
                'monthly_metrics': monthly_metrics.to_dict(orient='records') if not monthly_metrics.empty else [],
                'summary_metrics': summary_metrics.to_dict(orient='records'),
                'generated_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            json_str_metrics = json.dumps(metrics_json, indent=2, default=str)
            st.download_button(
                label="📥 Download Metrics as JSON",
                data=json_str_metrics,
                file_name=f"quality_metrics_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="download_quality_metrics_json"
            )

    # --- Step 7: Data Quality & Alerts Section (Footer) ---
    st.markdown("---")
    st.markdown("<div class='section-header'>⚠️ Data Quality & Alerts</div>", unsafe_allow_html=True)
    
    # Define alerts (based on known data gaps in current dashboard version)
    alerts = [
        "⚠️ Detailed complaint categorization data unavailable",
        "⚠️ Gender-disaggregated workforce data unavailable",
        "⚠️ Training records unavailable"
    ]
    
    # Check if Asset Health is missing
    if asset_health_score is None:
        alerts.append("⚠️ Asset health assessment pending")
    
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

