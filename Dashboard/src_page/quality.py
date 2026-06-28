import io
from datetime import datetime
import os
import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import (
    KPI,
    chart_card,
    prepare_service_data as _prepare_service_data,
    DATA_DIR,
    filter_df_by_user_access,
    validate_selected_country,
    get_user_country_filter,
    render_kpi_row,
    render_page_header,
    render_section_header,
    render_domain_pill,
    render_empty_state,
    render_no_data_panel,
    render_standardized_filters,
    apply_standard_filters,
    get_month_number,
)
from charts import (
    DATA_SERIES,
    DATA_WATER,
    DATA_SANITATION,
    STATUS_GOOD,
    STATUS_WARNING,
    STATUS_CRITICAL,
    SEQ_BLUE,
    apply_axis_percent,
    style_fig,
    style_bar,
    colorway,
)
from data.metrics import women_in_decision_making

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
    
    render_page_header(
        "Service Quality & Reliability",
        eyebrow="Performance",
        subtitle="Water quality, continuity, and service performance metrics.",
        icon="verified",
        badges=[{"label": "Monthly", "kind": "neutral"}],
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
    
    with st.expander("Data Import", expanded=False):
        # Show current data status
        if st.session_state.quality_service_data is not None:
            st.success(f"Service data loaded: {len(st.session_state.quality_service_data)} records")
        else:
            st.warning("No service data loaded")

        # Tab for different import methods
        import_tab1, import_tab2 = st.tabs(["Upload Custom Files", "Default Data"])

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
            st.info("Using default service data from repository")
            if st.button("Reload Default Data", key="reload_quality_default"):
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
        st.warning("No service data available for selected filters")
        return

    render_section_header("Daily briefing", eyebrow="High-level assessment", meta="Snapshot")

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

    # Compliance categorisation
    if compliance_rate > 95:
        comp_kind = "positive"
    elif compliance_rate >= 85:
        comp_kind = "neutral"
    else:
        comp_kind = "negative"

    # Network performance: lower is better
    if blocks_per_100km < 10:
        net_kind = "positive"
    elif blocks_per_100km < 50:
        net_kind = "neutral"
    else:
        net_kind = "negative"

    # Asset health categorisation
    if asset_health_score is not None:
        if asset_health_score >= 75:
            ah_kind, ah_cat = "positive", "Good"
        elif asset_health_score >= 50:
            ah_kind, ah_cat = "neutral", "Fair"
        else:
            ah_kind, ah_cat = "negative", "Poor"
        ah_value = f"{asset_health_score:.1f}%"
        ah_delta = ah_cat
    else:
        ah_kind = "neutral"
        ah_value = "Pending"
        ah_delta = "Annual assessment"

    res_time_str = f"{avg_res_time:.1f} days" if avg_res_time is not None else "N/A"

    # ---- Sparkline series (best-effort; empty lists render no spark) -------
    def _last_n_floats(values, n=12):
        try:
            cleaned = [float(v) for v in values if v is not None and not pd.isna(v)]
            return cleaned[-n:]
        except Exception:
            return []

    def _monthly_series(df, col, agg="mean"):
        if df.empty or col not in df.columns or "year" not in df.columns:
            return []
        try:
            month_col = "month" if "month" in df.columns else None
            keys = ["year", month_col] if month_col else ["year"]
            grouped = df.groupby([k for k in keys if k])[col].agg(agg).reset_index()
            grouped = grouped.sort_values(keys)
            return _last_n_floats(grouped[col].tolist())
        except Exception:
            return []

    wq_spark = []
    try:
        if not df_s_filt.empty and "tests_conducted_chlorine" in df_s_filt.columns:
            tmp = df_s_filt.copy()
            tmp["_total_passed"] = tmp.get("test_passed_chlorine", 0).fillna(0) + tmp.get("tests_passed_ecoli", 0).fillna(0)
            tmp["_total_conducted"] = tmp.get("tests_conducted_chlorine", 0).fillna(0) + tmp.get("test_conducted_ecoli", 0).fillna(0)
            tmp["_rate"] = (tmp["_total_passed"] / tmp["_total_conducted"].replace(0, 1) * 100).fillna(0)
            wq_spark = _monthly_series(tmp, "_rate", agg="mean")
    except Exception:
        pass
    cont_spark = _monthly_series(df_p_filt, "service_hours", agg="mean")
    res_spark = []
    try:
        if not df_s_filt.empty and "complaints" in df_s_filt.columns and "resolved" in df_s_filt.columns:
            tmp = df_s_filt.copy()
            tmp["_rate"] = (tmp["resolved"].fillna(0) / tmp["complaints"].replace(0, 1) * 100).fillna(0)
            res_spark = _monthly_series(tmp, "_rate", agg="mean")
    except Exception:
        pass
    net_spark = _monthly_series(df_f_filt, "blocks", agg="sum")

    render_kpi_row([
        KPI("Water quality",       f"{compliance_rate:.1f}%",
            delta=f"Cl {rate_cl:.0f}% · E.coli {rate_ec:.0f}%",
            delta_kind=comp_kind,
            icon="science",
            footnote="Samples meeting standards",
            metric_key="water_quality_compliance",
            sparkline=wq_spark),
        KPI("Service continuity",  f"{avg_service_hours:.1f} hrs/day",
            delta="Target 24h",
            delta_kind="neutral",
            icon="schedule",
            metric_key="service_continuity",
            sparkline=cont_spark),
        KPI("Complaint resolution", f"{resolution_rate:.1f}%",
            delta=f"Avg {res_time_str}",
            delta_kind="neutral",
            icon="support_agent",
            footnote="Of complaints resolved",
            sparkline=res_spark),
        KPI("Network performance", f"{blocks_per_100km:.1f}",
            delta=f"{total_blocks:,.0f} blocks total",
            delta_kind=net_kind,
            icon="hub",
            footnote="Blockages / 100 km · lower is better",
            sparkline=net_spark),
        KPI("Asset health", ah_value, delta=ah_delta, delta_kind=ah_kind,
            icon="construction",
            footnote="Annual assessment"),
    ])

    # ============================================================================
    # TABBED ANALYSIS SECTIONS
    # ============================================================================
    
    render_section_header("Quality analysis", eyebrow="Deep dive")
    
    quality_tab1, quality_tab2, quality_tab3 = st.tabs(["Water Quality", "Sanitation", "Customer Service"])
    
    # ============================================================================
    # TAB 1: Water Quality Deep Dive
    # ============================================================================
    with quality_tab1:
        render_section_header("Water quality deep dive", icon="water_drop")
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
                marker_color='#c3d8fb',
                text=chart_data['tests_chlorine'].apply(lambda x: f"{x:.0f}"),
                textposition='auto'
            ))
            
            # 2. Conducted
            fig_perf.add_trace(go.Bar(
                y=chart_data[group_col],
                x=chart_data['tests_conducted_chlorine'],
                name='Conducted',
                orientation='h',
                marker_color=DATA_WATER,
                text=chart_data.apply(lambda row: f"{row['tests_conducted_chlorine']:.0f} (conducted rate {row['conduct_rate']:.1f}%)", axis=1),
                textposition='auto'
            ))
            
            # 3. Passed
            fig_perf.add_trace(go.Bar(
                y=chart_data[group_col],
                x=chart_data['test_passed_chlorine'],
                name='Passed',
                orientation='h',
                marker_color=STATUS_GOOD,
                text=chart_data.apply(lambda row: f"{row['test_passed_chlorine']:.0f} (passed rate {row['pass_rate']:.1f}%)", axis=1),
                textposition='auto'
            ))

            fig_perf.update_layout(
                barmode='group',
                legend=dict(orientation="v", y=0.5, x=1.02, xanchor="left", yanchor="middle"),
                xaxis_title="Number of tests",
            )
            style_bar(fig_perf, title=title_suffix,
                      height=300 + (len(chart_data) * 20 if len(chart_data) > 5 else 0))

            st.plotly_chart(fig_perf, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with q_col2:
            #st.markdown("<div class='chart-container'>", unsafe_allow_html=True)
            st.markdown("**Contaminant Trends: Chlorine vs E. Coli Pass Rate**")
            
            # Check if date column exists
            if 'date' not in df_service.columns:
                st.warning("Date column not available for trend analysis")
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
                        line=dict(color=DATA_WATER, width=2),
                        mode='lines',
                        hovertemplate='<b>Chlorine</b><br>Date: %{x|%b %Y}<br>Pass Rate: %{y:.1f}%<extra></extra>'
                    ))
                    fig_trend.add_trace(go.Scatter(
                        x=ts_quality['date'], 
                        y=ts_quality['E. Coli %'], 
                        name='E. Coli', 
                        line=dict(color=STATUS_CRITICAL, width=2),
                        mode='lines',
                        hovertemplate='<b>E. Coli</b><br>Date: %{x|%b %Y}<br>Pass Rate: %{y:.1f}%<extra></extra>'
                    ))
                    
                    # Add WHO Threshold
                    fig_trend.add_hline(y=95, line_dash="dash", line_color=STATUS_GOOD, annotation_text="WHO Std (95%)", annotation_position="top right", annotation_font_color=STATUS_GOOD)

                    fig_trend.update_layout(
                        xaxis=dict(
                            rangeslider=dict(visible=True, thickness=0.08),
                            type="date",
                            range=[f"{selected_year}-01-01", f"{selected_year}-12-31"] if selected_year else None,
                            tickformat='%b %Y',
                            dtick='M2',  # Show tick every 2 months for less clutter
                        ),
                        yaxis=dict(title="Pass rate (%)", range=[0, 105]),
                        hovermode='x unified',
                    )
                    style_fig(fig_trend, height=350, legend_top=True)
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
                    fig_bar.add_trace(go.Bar(x=bar_data[group_col], y=bar_data['Chlorine %'], name='Chlorine', marker_color=DATA_WATER))
                    fig_bar.add_trace(go.Bar(x=bar_data[group_col], y=bar_data['E. Coli %'], name='E. Coli', marker_color=STATUS_CRITICAL))
                    
                    # Add WHO Threshold
                    fig_bar.add_hline(y=95, line_dash="dash", line_color=STATUS_GOOD, annotation_text="WHO Std (95%)", annotation_position="top right", annotation_font_color=STATUS_GOOD)

                    fig_bar.update_layout(barmode='group', yaxis_title="Pass rate (%)")
                    style_bar(fig_bar, height=320, legend_top=True, show_values=True, value_fmt="%{value:.0f}%")
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
                    fig_bar.add_trace(go.Bar(x=['Chlorine', 'E. Coli'], y=[rate_cl, rate_ec], marker_color=[DATA_WATER, STATUS_CRITICAL]))
                    
                    # Add WHO Threshold
                    fig_bar.add_hline(y=95, line_dash="dash", line_color=STATUS_GOOD, annotation_text="WHO Std (95%)", annotation_position="top right", annotation_font_color=STATUS_GOOD)

                    fig_bar.update_layout(yaxis_title="Pass rate (%)")
                    style_bar(fig_bar, height=300, show_legend=False, show_values=True, value_fmt="%{value:.0f}%")
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
                zone_list = "\n".join(f"- **{zone}**: {score:.1f}%" for zone, score in non_compliant_zones.items())
                st.error(
                    "**Quality alert — critical compliance issues**\n\n"
                    "The following zones have dropped below 80% compliance:\n\n"
                    f"{zone_list}\n\n"
                    "**Required actions:**\n\n"
                    "- Immediate flushing of distribution lines\n"
                    "- Increase chlorine dosage at treatment plant\n"
                    "- Deploy emergency water tankers if necessary"
                )

    # ============================================================================
    # TAB 2: Sanitation Check
    # ============================================================================
    with quality_tab2:
        if service_type in ["Sanitation", "Both"]:
            render_section_header("Sanitation check", icon="shower")
            st.markdown("Wastewater treatment efficiency and sewer health metrics.")

            # AUDC circular-economy indicators (real data: ww_collected/treated/reused)
            from data.metrics import wastewater_treatment_pct, water_reuse_pct
            _treat_pct = wastewater_treatment_pct(df_s_filt)
            _reuse_pct = water_reuse_pct(df_s_filt)
            sm1, sm2 = st.columns(2)
            sm1.metric(
                "Wastewater treated",
                f"{_treat_pct:.1f}%" if _treat_pct is not None else "—",
                help="Volume treated ÷ volume collected (AUDC indicator)",
            )
            sm2.metric(
                "Water recycled / reused",
                f"{_reuse_pct:.1f}%" if _reuse_pct is not None else "—",
                help="Wastewater reused ÷ total water supplied (SDG 6.3)",
            )

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
                    marker=dict(color=["#1d4ed8", "#3f74ea", "#84acf3"])  # sequential blue funnel
                ))
                style_fig(fig_funnel, height=300, show_legend=False)
                st.plotly_chart(fig_funnel, use_container_width=True)

            with s_col2:
                st.markdown("**Sewer Health: Blockages**")
                
                # Blockages from financial data
                total_blocks = df_f_filt['blocks'].sum() if not df_f_filt.empty else 0
                
                # Trend if possible
                if not df_f_filt.empty:
                    blocks_trend = df_f_filt.groupby('date')['blocks'].sum().reset_index()
                    fig_blocks = px.line(blocks_trend, x='date', y='blocks', markers=True)
                    fig_blocks.update_traces(line=dict(color=STATUS_CRITICAL, width=2.5))
                    fig_blocks.update_layout(yaxis_title="Blockages")
                    style_fig(fig_blocks, height=240)
                    
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
        render_section_header("Customer service performance", icon="support_agent")

        # Headline complaint resolution IS available (complaints / resolved) —
        # show the real metric, then a clean placeholder for the detailed
        # breakdowns that aren't collected yet (no blurred fake charts).
        cs1, cs2, cs3 = st.columns(3)
        cs1.metric("Complaints received", f"{int(total_complaints):,}", help="Total in selected period")
        cs2.metric("Resolved", f"{int(total_resolved):,}",
                   help="Complaints closed in selected period")
        cs3.metric("Resolution rate", f"{resolution_rate:.1f}%",
                   help="Resolved ÷ received")

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        render_no_data_panel(
            "Complaint detail not collected yet",
            "Category breakdowns (no water, low pressure, billing…), resolution-stage "
            "funnels, and time-to-resolve distributions will appear here once the "
            "utility captures complaint-level records. Today only totals are reported.",
            icon="support_agent",
        )

    # ============================================================================
    # ORGANIZATIONAL CAPACITY SECTION (with tabs)
    # ============================================================================
    
    st.markdown("---")
    render_section_header("Organisational capacity", eyebrow="People & training")
    
    org_tab1, org_tab2, org_tab3 = st.tabs(["Staff metrics", "Training matrix", "Diversity & efficiency"])

    # TAB 1: Staff Metrics — now built from REAL data:
    #   - w_staff / san_staff (financial services, monthly)
    #   - workforce / f_workforce (service data: sanitation decision-making)
    #   - staff per 1000 sewer connections (efficiency)
    with org_tab1:
        st.markdown("**Staff composition & efficiency**")

        water_staff = float(df_f_filt['w_staff'].mean()) if not df_f_filt.empty and 'w_staff' in df_f_filt.columns else 0.0
        san_staff = float(df_f_filt['san_staff'].mean()) if not df_f_filt.empty and 'san_staff' in df_f_filt.columns else 0.0

        # Women in decision-making (AUDC indicator) from service workforce data
        women_dm = women_in_decision_making(df_s_filt)

        # Staff per 1000 connections (efficiency) — sanitation staff vs sewer connections
        sewer_conn = float(df_s_filt['sewer_connections'].mean()) if not df_s_filt.empty and 'sewer_connections' in df_s_filt.columns else 0.0
        san_eff = (san_staff / sewer_conn * 1000) if sewer_conn > 0 else 0.0

        m1, m2, m3 = st.columns(3)
        m1.metric("Water supply staff", f"{water_staff:,.0f}", help="Avg monthly headcount (financial services data)")
        m2.metric("Sanitation staff", f"{san_staff:,.0f}", help="Avg monthly headcount")
        m3.metric(
            "Women in decision-making",
            f"{women_dm:.1f}%" if women_dm is not None else "—",
            help="Women ÷ total sanitation decision-making workforce (AUDC indicator)",
        )

        if water_staff > 0 or san_staff > 0:
            fig_staff = go.Figure()
            fig_staff.add_trace(go.Bar(
                x=['Water Supply', 'Sanitation'],
                y=[water_staff, san_staff],
                name='Total staff', marker_color=[DATA_WATER, DATA_SANITATION],
            ))
            fig_staff.add_trace(go.Scatter(
                x=['Sanitation'], y=[san_eff], name='Staff / 1000 connections',
                mode='markers+text', yaxis='y2',
                marker=dict(color=STATUS_WARNING, size=14),
                text=[f"{san_eff:.1f}"], textposition='top center',
            ))
            fig_staff.update_layout(
                yaxis=dict(title="Headcount"),
                yaxis2=dict(title="Staff/1000 conn", overlaying='y', side='right', showgrid=False),
            )
            style_bar(fig_staff, height=320, legend_top=True)
            st.plotly_chart(fig_staff, use_container_width=True)
        else:
            st.info("No workforce data available for the selected filters.")

        st.caption(
            "Note: gender-disaggregated *training* records (M/F trained) are not "
            "yet collected — see the Training matrix tab."
        )

    # TAB 2: Training Matrix
    with org_tab2:
        render_no_data_panel(
            "Training records not collected yet",
            "A by-category, by-quarter training-completion matrix with male/female "
            "splits will render here once the utility logs staff training events. "
            "Total trained-staff counts are available on the Governance page.",
            icon="school",
        )

    # TAB 3: Diversity & Efficiency
    with org_tab3:
        # These are REAL — reuse the figures already computed in Tab 1 rather
        # than the previous fabricated ring + gauge.
        de1, de2 = st.columns(2)
        de1.metric("Women in decision-making", f"{women_dm:.1f}%" if women_dm is not None else "—",
                   help="Women ÷ total sanitation decision-making workforce")
        de2.metric("Staff efficiency", f"{san_eff:.1f}" if sewer_conn > 0 else "—",
                   help="Sanitation staff per 1,000 connections (lower is leaner)")
        st.caption(
            "Targets: ≥30% women in decision-making (SDG 5.5); staffing efficiency "
            "benchmarked against IBNET peers."
        )

    # ============================================================================
    # DATA EXPORT SECTION
    # ============================================================================
    
    render_section_header("Data export", icon="download")

    export_tab1, export_tab2 = st.tabs(["Service Data", "Calculated Metrics"])
    
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
        st.info("This file contains all derived metrics calculated from the raw data for easy analysis and reporting.")
        
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
    render_section_header("Data quality & alerts", icon="warning")
    
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

