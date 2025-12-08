import io
import json
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from utils import prepare_access_data, prepare_service_data, DATA_DIR, filter_df_by_user_access, validate_selected_country

# Required columns for schema validation
WATER_ACCESS_REQUIRED_COLS = ['country', 'zone', 'year', 'popn_total']
SEWER_ACCESS_REQUIRED_COLS = ['country', 'zone', 'year', 'popn_total']

# Tab organization and chart mapping
TAB_STRUCTURE = {
    "Coverage Overview": {
        "icon": "📊",
        "description": "Water and sewer coverage metrics, service scorecards",
        "charts": ["scorecards", "ladder_analysis"]
    },
    "Growth Metrics": {
        "icon": "📈",
        "description": "Coverage trends, growth rates, expansion analysis",
        "charts": ["growth_trends", "coverage_sparklines"]
    },
    "Infrastructure Status": {
        "icon": "🏗️",
        "description": "Infrastructure assets, metering status, facilities",
        "charts": ["infrastructure_metrics", "asset_distribution"]
    },
    "Equity & Demographics": {
        "icon": "⚖️",
        "description": "Population served, access disparities, equity analysis",
        "charts": ["equity_check", "population_demographics"]
    },
    "Access Transitions": {
        "icon": "📊",
        "description": "Population movement analysis, service transitions",
        "charts": ["transition_report"]
    }
}


def validate_upload_schema(df: pd.DataFrame, required_cols: list, file_type: str) -> tuple:
    """Validate that uploaded data has required columns.
    
    Returns:
        tuple: (is_valid, missing_columns, warning_message)
    """
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        return False, missing, f"❌ {file_type} is missing required columns: {', '.join(missing)}"
    return True, [], None

def load_financial_data():
    """Load financial services data for the access dashboard."""
    fin_path = DATA_DIR / "all_fin_service.csv"
    df_fin = pd.DataFrame()
    
    if fin_path.exists():
        df_fin = pd.read_csv(fin_path)
        if 'date_MMYY' in df_fin.columns:
            df_fin['date'] = pd.to_datetime(df_fin['date_MMYY'], format='%b/%y', errors='coerce')
        df_fin['year'] = df_fin['date'].dt.year
        df_fin['month'] = df_fin['date'].dt.month
        
        # Apply access control filtering
        df_fin = filter_df_by_user_access(df_fin, "country")
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


def format_quarterly_label(date):
    """Convert date to quarterly format (e.g., '2020/Q1')."""
    quarter = (date.month - 1) // 3 + 1
    return f"{date.year}/Q{quarter}"


def apply_view_type_filter(df, view_type, date_col='date', year_col='year', month_col='month'):
    """Apply view_type filtering consistently across all charts.
    
    Args:
        df: DataFrame to filter
        view_type: 'Annual' or 'Quarterly'
        date_col: Column name for dates (if exists)
        year_col: Column name for years
        month_col: Column name for months (if exists)
    
    Returns:
        Filtered DataFrame and aggregation parameters
    """
    if view_type == "Annual":
        return df, {'freq': 'Y', 'agg_method': 'yearly'}
    else:  # Quarterly
        return df, {'freq': 'Q', 'agg_method': 'quarterly'}


def get_active_tab():
    """Get or initialize active tab in session state."""
    if "active_access_tab" not in st.session_state:
        st.session_state["active_access_tab"] = list(TAB_STRUCTURE.keys())[0]
    return st.session_state["active_access_tab"]


def set_active_tab(tab_name):
    """Set active tab in session state."""
    st.session_state["active_access_tab"] = tab_name


def render_tab_selector(selected_tab: str) -> str:
    """Render horizontal tab selector and return selected tab name."""
    tabs_list = list(TAB_STRUCTURE.keys())
    
    st.markdown("---")
    st.markdown("<h3 style='margin-top: 0; margin-bottom: 16px;'>Dashboard Sections</h3>", unsafe_allow_html=True)
    
    # Create horizontal tabs using columns
    cols = st.columns(len(tabs_list))
    
    for idx, (col, tab_name) in enumerate(zip(cols, tabs_list)):
        tab_info = TAB_STRUCTURE[tab_name]
        is_active = tab_name == selected_tab
        
        with col:
            # Style based on active state
            bg_color = "#e0e7ff" if is_active else "#f3f4f6"
            border_style = "3px solid #4f46e5" if is_active else "1px solid #d1d5db"
            text_color = "#4f46e5" if is_active else "#6b7280"
            font_weight = "700" if is_active else "600"
            
            if st.button(
                f"{tab_info['icon']} {tab_name}",
                key=f"tab_{tab_name}",
                use_container_width=True,
                help=tab_info['description']
            ):
                set_active_tab(tab_name)
                st.rerun()
            
            # Apply styling with markdown
            if is_active:
                st.markdown(
                    f"""<div style='background: {bg_color}; border: {border_style}; 
                    border-radius: 6px; padding: 8px; text-align: center; 
                    color: {text_color}; font-weight: {font_weight}; 
                    font-size: 13px; margin-top: -42px;'>
                    {tab_info['icon']} {tab_name}
                    </div>""",
                    unsafe_allow_html=True
                )
    
    return selected_tab


def render_coverage_overview_tab(df_water, df_sewer, df_service, df_fin, selected_country, selected_zone, selected_year, view_type):
    """Render Coverage Overview tab with scorecards and ladder analysis."""
    st.markdown("### 📊 Coverage Overview")
    st.markdown("Water and sewer coverage metrics, service scorecards, and access quality analysis.")
    
    # Key Performance Scorecards
    st.markdown("<div class='section-header'>📊 Key Performance Scorecards</div>", unsafe_allow_html=True)
    
    # ... [Rest of scorecards and ladder analysis code from original]
    # This will be populated from the existing code


def render_growth_metrics_tab(df_water, df_service, selected_country, selected_zone, view_type):
    """Render Growth Metrics tab with coverage trends and growth analysis."""
    st.markdown("### 📈 Growth Metrics")
    st.markdown("Coverage trends, growth rates, and expansion analysis.")
    
    # ... [Growth trends and sparklines code]


def render_infrastructure_tab(df_service, df_fin, selected_country, selected_zone, selected_year, view_type):
    """Render Infrastructure Status tab."""
    st.markdown("### 🏗️ Infrastructure Status")
    st.markdown("Infrastructure assets, metering status, and facility distribution.")
    
    # ... [Infrastructure metrics code]


def render_equity_demographics_tab(df_water, df_sewer, df_service, selected_country, selected_zone, selected_year, view_type):
    """Render Equity & Demographics tab."""
    st.markdown("### ⚖️ Equity & Demographics")
    st.markdown("Population served, access disparities, and equity analysis.")
    
    # ... [Equity check and population demographics code]


def render_transitions_tab(df_water, df_sewer, df_service, selected_country, selected_zone, selected_year, view_type):
    """Render Access Transitions tab."""
    st.markdown("### 📊 Access Transitions")
    st.markdown("Population movement analysis and service transitions.")
    
    # ... [Transition report code]

def scene_access():
    """
    Access & Coverage scene - Redesigned based on User Journey.
    Data access is restricted based on user permissions.
    """
    
    # ============================================================================
    # HEADER WITH DATA FRESHNESS
    # ============================================================================
    
    header_col1, header_col2 = st.columns([3, 1])
    with header_col1:
        st.markdown("## 🗺️ Access & Coverage")
    with header_col2:
        st.markdown(
            f"<div style='text-align: right; color: #6b7280; font-size: 0.85rem;'>"
            f"📅 Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            f"</div>",
            unsafe_allow_html=True
        )
    
    # ============================================================================
    # DATA INITIALIZATION (Before UI elements)
    # ============================================================================
    
    # Initialize session state for data BEFORE expander to ensure data is available
    if 'access_water_data' not in st.session_state:
        st.session_state.access_water_data = None
    if 'access_sewer_data' not in st.session_state:
        st.session_state.access_sewer_data = None
    if 'access_default_data_loaded' not in st.session_state:
        st.session_state.access_default_data_loaded = False

    # AUTO-LOAD DEFAULT DATA ON FIRST PAGE LOAD (silently, outside expander)
    if not st.session_state.access_default_data_loaded:
        try:
            st.session_state.access_water_data = pd.read_csv(DATA_DIR / 'w_access.csv')
            st.session_state.access_sewer_data = pd.read_csv(DATA_DIR / 's_access.csv')
            st.session_state.access_default_data_loaded = True
        except Exception as e:
            st.session_state.access_default_data_loaded = True  # Prevent repeated attempts
    
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
        if st.session_state.access_water_data is not None and st.session_state.access_sewer_data is not None:
            st.success(f"✅ Access data loaded: Water ({len(st.session_state.access_water_data)} records), Sewer ({len(st.session_state.access_sewer_data)} records)")
        else:
            st.warning("⚠️ No access data loaded")

        # Tab for different import methods
        import_tab1, import_tab2 = st.tabs(["📤 Upload Custom Files", "📋 Default Data"])

        with import_tab1:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Water Access Data**")
                water_file = st.file_uploader(
                    "Upload Water Access CSV",
                    type=['csv', 'xlsx'],
                    key="access_water_upload",
                    help="Required columns: country, zone, year, popn_total, municipal_coverage, safely_managed, etc."
                )

                if water_file:
                    try:
                        if water_file.name.endswith('.csv'):
                            uploaded_water = pd.read_csv(water_file)
                        else:
                            uploaded_water = pd.read_excel(water_file)
                        
                        # Schema validation
                        is_valid, missing, warning = validate_upload_schema(uploaded_water, WATER_ACCESS_REQUIRED_COLS, "Water Access Data")
                        if not is_valid:
                            st.warning(warning)
                        else:
                            st.session_state.access_water_data = uploaded_water
                            st.success(f"✓ Loaded {len(st.session_state.access_water_data)} water access records")
                    except Exception as e:
                        st.error(f"Error loading water data: {e}")
            
            with col2:
                st.markdown("**Sewer Access Data**")
                sewer_file = st.file_uploader(
                    "Upload Sewer Access CSV",
                    type=['csv', 'xlsx'],
                    key="access_sewer_upload",
                    help="Required columns: country, zone, year, popn_total, connections, safely_managed, etc."
                )

                if sewer_file:
                    try:
                        if sewer_file.name.endswith('.csv'):
                            uploaded_sewer = pd.read_csv(sewer_file)
                        else:
                            uploaded_sewer = pd.read_excel(sewer_file)
                        
                        # Schema validation
                        is_valid, missing, warning = validate_upload_schema(uploaded_sewer, SEWER_ACCESS_REQUIRED_COLS, "Sewer Access Data")
                        if not is_valid:
                            st.warning(warning)
                        else:
                            st.session_state.access_sewer_data = uploaded_sewer
                            st.success(f"✓ Loaded {len(st.session_state.access_sewer_data)} sewer access records")
                    except Exception as e:
                        st.error(f"Error loading sewer data: {e}")

        with import_tab2:
            st.info("📌 Using default access data from repository")
            if st.button("🔄 Reload Default Data", key="reload_access_default"):
                with st.spinner("Reloading default data..."):
                    try:
                        st.session_state.access_water_data = pd.read_csv(DATA_DIR / 'w_access.csv')
                        st.session_state.access_sewer_data = pd.read_csv(DATA_DIR / 's_access.csv')
                        st.success(f"✓ Reloaded water ({len(st.session_state.access_water_data)}) and sewer ({len(st.session_state.access_sewer_data)}) records")
                    except Exception as e:
                        st.error(f"Error loading default data: {e}")

    # Load data (use session state if available, otherwise use default loading)
    if st.session_state.access_water_data is not None and st.session_state.access_sewer_data is not None:
        # Use custom data from session state
        df_water = filter_df_by_user_access(st.session_state.access_water_data.copy(), "country")
        df_sewer = filter_df_by_user_access(st.session_state.access_sewer_data.copy(), "country")
    else:
        # Load data (already filtered by user access in prepare_* functions)
        access_data = prepare_access_data()
        df_water = access_data["water_full"]
        df_sewer = access_data["sewer_full"]
    
    service_data = prepare_service_data()
    df_service = service_data["full_data"]
    
    df_fin = load_financial_data()

    # --- Header Section ---
    header_container = st.container()
    
    # Get user access restrictions for filtering
    try:
        from auth import get_current_user, UserRole, get_allowed_countries
        user = get_current_user()
        allowed_countries = get_allowed_countries()
        is_master_user = user is not None and user.role == UserRole.MASTER_USER
    except ImportError:
        user = None
        allowed_countries = []
        is_master_user = True  # Default to no restrictions if auth not available
    
    # Filters Row
    filt_c1, filt_c2, filt_c3, filt_c4 = st.columns([2, 2, 2, 2])
    
    with filt_c1:
        st.markdown("<label style='font-size: 12px; font-weight: 600; color: #374151;'>View Period</label>", unsafe_allow_html=True)
        view_type = st.radio("View Period", ["Annual", "Quarterly"], horizontal=True, label_visibility="collapsed", key="view_type_toggle")
        
    with filt_c2:
        # Country Filter - Restricted based on user access
        if is_master_user:
            countries = ['All'] + sorted(df_water['country'].unique().tolist()) if 'country' in df_water.columns else ['All']
        else:
            # Non-master users can only see their assigned country
            countries = allowed_countries if allowed_countries else ['All']
        
        # Try to get default from session state if available
        default_country_idx = 0
        if "selected_country" in st.session_state:
            validated_country = validate_selected_country(st.session_state.selected_country)
            if validated_country in countries:
                default_country_idx = countries.index(validated_country)
        
        # Check if country selector should be locked
        is_country_locked = not is_master_user and len(countries) == 1
        
        if is_country_locked:
            # Show locked indicator
            st.markdown(f"""
            <div style='background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; 
                        padding: 10px 14px; display: flex; align-items: center; gap: 8px; margin-top: 24px;'>
                <span style='font-size: 1rem;'>🔒</span>
                <span style='font-weight: 600; color: #334155;'>{countries[0]}</span>
            </div>
            """, unsafe_allow_html=True)
            selected_country = countries[0]
        else:
            selected_country = st.selectbox("Country", countries, index=default_country_idx, key="access_country_select")
            # Validate the selection
            selected_country = validate_selected_country(selected_country)
        
    with filt_c3:
        # Zone Filter (dependent on country) - case-insensitive
        if selected_country != 'All':
            zones = ['All'] + sorted(df_water[df_water['country'].str.lower() == selected_country.lower()]['zone'].unique().tolist())
        else:
            zones = ['All'] + sorted(df_water['zone'].unique().tolist())
            
        default_zone_idx = 0
        if "selected_zone" in st.session_state and st.session_state.selected_zone in zones:
            default_zone_idx = zones.index(st.session_state.selected_zone)
            
        selected_zone = st.selectbox("Zone/City", zones, index=default_zone_idx, key="access_zone_select")
        
    with filt_c4:
        # Year Filter
        years = sorted(df_water['year'].unique().tolist(), reverse=True)
        default_year_idx = 0
        if "selected_year" in st.session_state and st.session_state.selected_year in years:
            default_year_idx = years.index(st.session_state.selected_year)
            
        selected_year = st.selectbox("Year", years, index=default_year_idx, key="access_year_select")

    # Map month name to number (for Service Data)
    selected_month_name = st.session_state.get("selected_month", "All")
    month_map = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    selected_month = month_map.get(selected_month_name) if selected_month_name != 'All' else 'All'

    # --- Apply Filters (case-insensitive for country/zone) ---
    # Helper function for safe year filtering
    def _safe_year_filter(df, year_col, year_value):
        if year_value is None or df.empty or year_col not in df.columns:
            return df
        try:
            year_int = int(year_value)
            return df[df[year_col] == year_int]
        except (ValueError, TypeError):
            return df[df[year_col] == year_value]

    # Water Data
    df_w_filt = df_water.copy()
    if selected_country != 'All': df_w_filt = df_w_filt[df_w_filt['country'].str.lower() == selected_country.lower()]
    if selected_zone != 'All': df_w_filt = df_w_filt[df_w_filt['zone'].str.lower() == selected_zone.lower()]
    if selected_year: df_w_filt = _safe_year_filter(df_w_filt, 'year', selected_year)

    # Sewer Data
    df_s_filt = df_sewer.copy()
    if selected_country != 'All': df_s_filt = df_s_filt[df_s_filt['country'].str.lower() == selected_country.lower()]
    if selected_zone != 'All': df_s_filt = df_s_filt[df_s_filt['zone'].str.lower() == selected_zone.lower()]
    if selected_year: df_s_filt = _safe_year_filter(df_s_filt, 'year', selected_year)

    # Service Data (Monthly)
    df_svc_filt = df_service.copy()
    if selected_country != 'All': df_svc_filt = df_svc_filt[df_svc_filt['country'].str.lower() == selected_country.lower()]
    if selected_zone != 'All': df_svc_filt = df_svc_filt[df_svc_filt['zone'].str.lower() == selected_zone.lower()]
    if selected_year: df_svc_filt = _safe_year_filter(df_svc_filt, 'year', selected_year)
    if selected_month != 'All': df_svc_filt = df_svc_filt[df_svc_filt['month'] == selected_month]

    # Financial Data (for Pro-Poor)
    df_f_filt = df_fin.copy()
    if selected_country != 'All' and 'country' in df_f_filt.columns:
        df_f_filt = df_f_filt[df_f_filt['country'].str.lower() == selected_country.lower()]
    if 'year' in df_f_filt.columns and selected_year:
        df_f_filt = _safe_year_filter(df_f_filt, 'year', selected_year)
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

    # ===== WATER SUPPLY COVERAGE CALCULATIONS =====
    # Behavior depends on view_type: "Annual" vs "Quarterly"
    
    if view_type == "Quarterly":
        # QUARTERLY VIEW: Aggregate water data quarterly (if monthly data available, else use annual data)
        # Water access data is typically annual, but we show the context as quarterly
        total_pop_w = df_w_filt['popn_total'].sum()
        muni_cov_count = df_w_filt['municipal_coverage'].sum()
        muni_supply_pct = (muni_cov_count / total_pop_w * 100) if total_pop_w > 0 else 0
        
        # QoQ Growth for Water Supply (comparing same quarter last year)
        if selected_year and selected_year > df_water['year'].min():
            last_year = selected_year - 1
            df_w_last = df_water.copy()
            if selected_country != 'All': df_w_last = df_w_last[df_w_last['country'].str.lower() == selected_country.lower()]
            if selected_zone != 'All': df_w_last = df_w_last[df_w_last['zone'].str.lower() == selected_zone.lower()]
            df_w_last = df_w_last[df_w_last['year'] == last_year]
            
            total_pop_w_last = df_w_last['popn_total'].sum()
            muni_cov_last = df_w_last['municipal_coverage'].sum()
            muni_supply_pct_last = (muni_cov_last / total_pop_w_last * 100) if total_pop_w_last > 0 else 0
            muni_yoy_growth = muni_supply_pct - muni_supply_pct_last
        else:
            muni_yoy_growth = 0
        water_comparison_label = "vs same quarter last year"
    else:
        # ANNUAL VIEW: Use annual aggregation
        total_pop_w = df_w_filt['popn_total'].sum()
        muni_cov_count = df_w_filt['municipal_coverage'].sum()
        muni_supply_pct = (muni_cov_count / total_pop_w * 100) if total_pop_w > 0 else 0
        
        # YoY Growth for Water Supply
        if selected_year and selected_year > df_water['year'].min():
            last_year = selected_year - 1
            df_w_last = df_water.copy()
            if selected_country != 'All': df_w_last = df_w_last[df_w_last['country'].str.lower() == selected_country.lower()]
            if selected_zone != 'All': df_w_last = df_w_last[df_w_last['zone'].str.lower() == selected_zone.lower()]
            df_w_last = df_w_last[df_w_last['year'] == last_year]
            
            total_pop_w_last = df_w_last['popn_total'].sum()
            muni_cov_last = df_w_last['municipal_coverage'].sum()
            muni_supply_pct_last = (muni_cov_last / total_pop_w_last * 100) if total_pop_w_last > 0 else 0
            muni_yoy_growth = muni_supply_pct - muni_supply_pct_last
        else:
            muni_yoy_growth = 0
        water_comparison_label = "vs last year"
    
    # Water: Households Covered & Population Served (from water access data)
    water_households = df_w_filt['households'].sum() / 1000  # Convert to K
    water_population = total_pop_w / 1000000  # Convert to M
    
    # ===== SEWER COVERAGE CALCULATIONS =====
    # Behavior depends on view_type: "Annual" vs "Quarterly"
    # Quarterly: Shows latest quarter's data only
    # Annual: Shows full year average
    
    if view_type == "Quarterly":
        # QUARTERLY VIEW: Show latest quarter's sewer data only
        if not df_svc_filt.empty and 'month' in df_svc_filt.columns:
            # Add quarter column for aggregation (Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec)
            df_svc_quarterly = df_service.copy()
            if selected_country != 'All': df_svc_quarterly = df_svc_quarterly[df_svc_quarterly['country'].str.lower() == selected_country.lower()]
            if selected_zone != 'All': df_svc_quarterly = df_svc_quarterly[df_svc_quarterly['zone'].str.lower() == selected_zone.lower()]
            
            # Calculate quarter from month: (month-1)//3 + 1 gives Q1=1, Q2=2, Q3=3, Q4=4
            df_svc_quarterly['quarter'] = ((df_svc_quarterly['month'] - 1) // 3) + 1
            
            # Filter for selected year if applicable
            if selected_year:
                df_svc_quarterly = df_svc_quarterly[df_svc_quarterly['year'] == selected_year]
            
            if not df_svc_quarterly.empty:
                # Get the latest quarter's data only
                latest_quarter = df_svc_quarterly['quarter'].max()
                df_q_latest = df_svc_quarterly[df_svc_quarterly['quarter'] == latest_quarter]
                
                # Calculate quarterly sewer coverage
                total_sewer_conn = df_q_latest['sewer_connections'].mean()  # Average within quarter
                total_hh_svc = df_q_latest['households'].max()
                sewer_conn_pct = (total_sewer_conn / total_hh_svc * 100) if total_hh_svc > 0 else 0
                
                # QoQ Growth - compare to same quarter last year
                if selected_year and selected_year > df_service['year'].min():
                    last_year = selected_year - 1
                    df_svc_last_year = df_service.copy()
                    if selected_country != 'All': df_svc_last_year = df_svc_last_year[df_svc_last_year['country'].str.lower() == selected_country.lower()]
                    if selected_zone != 'All': df_svc_last_year = df_svc_last_year[df_svc_last_year['zone'].str.lower() == selected_zone.lower()]
                    df_svc_last_year['quarter'] = ((df_svc_last_year['month'] - 1) // 3) + 1
                    df_svc_last_year = df_svc_last_year[(df_svc_last_year['year'] == last_year) & (df_svc_last_year['quarter'] == latest_quarter)]
                    
                    if not df_svc_last_year.empty:
                        total_sewer_conn_last = df_svc_last_year['sewer_connections'].mean()
                        total_hh_svc_last = df_svc_last_year['households'].max()
                        sewer_conn_pct_last = (total_sewer_conn_last / total_hh_svc_last * 100) if total_hh_svc_last > 0 else 0
                        sewer_growth = sewer_conn_pct - sewer_conn_pct_last
                    else:
                        sewer_growth = 0
                else:
                    sewer_growth = 0
                
                # Update label to show which quarter
                sewer_comparison_label = f"Q{latest_quarter} vs Q{latest_quarter} last year"
            else:
                sewer_conn_pct = 0
                sewer_growth = 0
                sewer_comparison_label = "vs same quarter last year"
        else:
            sewer_conn_pct = 0
            sewer_growth = 0
            sewer_comparison_label = "vs same quarter last year"
    else:
        # ANNUAL VIEW: Show full year average
        if not df_svc_filt.empty:
            # Use df_svc_filt which is already filtered by year
            total_sewer_conn = df_svc_filt['sewer_connections'].mean()  # Average across all months in year
            total_hh_svc = df_svc_filt['households'].max()
            sewer_conn_pct = (total_sewer_conn / total_hh_svc * 100) if total_hh_svc > 0 else 0
            
            # YoY Growth - compare to last year's average
            if selected_year and selected_year > df_service['year'].min():
                last_year = selected_year - 1
                df_svc_last_year = df_service.copy()
                if selected_country != 'All': df_svc_last_year = df_svc_last_year[df_svc_last_year['country'].str.lower() == selected_country.lower()]
                if selected_zone != 'All': df_svc_last_year = df_svc_last_year[df_svc_last_year['zone'].str.lower() == selected_zone.lower()]
                df_svc_last_year = df_svc_last_year[df_svc_last_year['year'] == last_year]
                
                if not df_svc_last_year.empty:
                    total_sewer_conn_last = df_svc_last_year['sewer_connections'].mean()
                    total_hh_svc_last = df_svc_last_year['households'].max()
                    sewer_conn_pct_last = (total_sewer_conn_last / total_hh_svc_last * 100) if total_hh_svc_last > 0 else 0
                    sewer_growth = sewer_conn_pct - sewer_conn_pct_last
                else:
                    sewer_growth = 0
            else:
                sewer_growth = 0
        else:
            sewer_conn_pct = 0
            sewer_growth = 0
        sewer_comparison_label = "vs last year"

    # --- Sparkline Data Calculations ---
    # Behavior depends on view_type: "Annual" vs "Quarterly"
    
    # Sparkline Data (Water Coverage Trend)
    df_w_trend = df_water.copy()
    if selected_country != 'All': df_w_trend = df_w_trend[df_w_trend['country'].str.lower() == selected_country.lower()]
    if selected_zone != 'All': df_w_trend = df_w_trend[df_w_trend['zone'].str.lower() == selected_zone.lower()]
    
    # Aggregate by year for water coverage trend (water data is annual)
    w_trend_agg = df_w_trend.groupby('year').agg({'municipal_coverage': 'sum', 'popn_total': 'sum'}).reset_index().sort_values('year')
    w_trend_agg['pct'] = (w_trend_agg['municipal_coverage'] / w_trend_agg['popn_total'] * 100).fillna(0)
    water_spark_data = w_trend_agg['pct'].tolist()

    # Sparkline Data (Sewer Coverage Trend)
    df_s_trend = df_service.copy()
    if selected_country != 'All': df_s_trend = df_s_trend[df_s_trend['country'].str.lower() == selected_country.lower()]
    if selected_zone != 'All': df_s_trend = df_s_trend[df_s_trend['zone'].str.lower() == selected_zone.lower()]
    
    if view_type == "Quarterly":
        # QUARTERLY VIEW: Aggregate to quarterly for sparkline
        if not df_s_trend.empty and 'month' in df_s_trend.columns:
            df_s_trend['quarter'] = ((df_s_trend['month'] - 1) // 3) + 1
            df_s_trend['year_quarter'] = df_s_trend['year'].astype(str) + '-Q' + df_s_trend['quarter'].astype(str)
            
            # Aggregate by year-quarter: average sewer connections, max households
            s_q_trend = df_s_trend.groupby(['year', 'quarter']).agg({
                'sewer_connections': 'mean',
                'households': 'max'
            }).reset_index()
            s_q_trend = s_q_trend.sort_values(['year', 'quarter'])
            
            # Calculate percentage for each quarter
            s_q_trend['pct'] = (s_q_trend['sewer_connections'] / s_q_trend['households'].replace(0, 1) * 100).fillna(0)
            
            # Take last 8 quarters for sparkline (2 years of quarterly data)
            s_q_trend = s_q_trend.tail(8)
            sewer_spark_data = s_q_trend['pct'].tolist()
        else:
            sewer_spark_data = []
    else:
        # ANNUAL VIEW: Aggregate to annual for sparkline
        if not df_s_trend.empty and 'month' in df_s_trend.columns:
            # Aggregate by year: average sewer connections, max households
            s_y_trend = df_s_trend.groupby(['year']).agg({
                'sewer_connections': 'mean',
                'households': 'max'
            }).reset_index()
            s_y_trend = s_y_trend.sort_values('year')
            
            # Calculate percentage for each year
            s_y_trend['pct'] = (s_y_trend['sewer_connections'] / s_y_trend['households'].replace(0, 1) * 100).fillna(0)
            
            sewer_spark_data = s_y_trend['pct'].tolist()
        else:
            sewer_spark_data = []

    # ===== DATA GAP PLACEHOLDERS =====
    # Metered Connections - DATA GAP: No metered connection data available
    metered_conn_pct = None  # Placeholder - data not available
    has_metered_data = False  # Flag to indicate data gap
    
    # Piped Water Supply - DATA GAP: No piped water supply data available  
    piped_water_pct = None  # Placeholder - data not available
    has_piped_data = False  # Flag to indicate data gap
    
    # Render Scorecard Cards
    kpi_c1, kpi_c2, kpi_c3, kpi_c4 = st.columns(4)
    
    # === Card 1: Water Supply Coverage ===
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
                <span style="color: #6b7280;">{water_comparison_label}</span>
            </div>
            <div style="margin-top: 12px;"></div>
        </div>
        """, unsafe_allow_html=True)
        if water_spark_data:
            st.plotly_chart(create_sparkline(water_spark_data, "#3b82f6"), use_container_width=True, config={'displayModeBar': False})
    
    # === Card 2: Sewer Coverage ===
    with kpi_c2:
        st.markdown(f"""
        <div class="metric-container">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div>
                    <div class="metric-label">Sewer Coverage</div>
                    <div class="metric-value">{sewer_conn_pct:.1f}%</div>
                </div>
                <div style="font-size: 24px;">🚽</div>
            </div>
            <div class="metric-delta">
                <span class="{'delta-up' if sewer_growth >= 0 else 'delta-down'}">
                    {sewer_growth:+.1f}%
                </span>
                <span style="color: #6b7280;">{sewer_comparison_label}</span>
            </div>
            <div style="margin-top: 12px;"></div>
        </div>
        """, unsafe_allow_html=True)
        if sewer_spark_data:
            st.plotly_chart(create_sparkline(sewer_spark_data, "#8b5cf6"), use_container_width=True, config={'displayModeBar': False})
    
    # === Card 3: % Metered Connections (DATA GAP - understated design) ===
    with kpi_c3:
        st.markdown(f"""
        <div class="metric-container" style="background-color: #f9fafb; border: 1px dashed #d1d5db;">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div>
                    <div class="metric-label" style="color: #9ca3af;">% Metered Connections</div>
                    <div class="metric-value" style="color: #9ca3af;">--</div>
                </div>
                <div style="font-size: 24px; opacity: 0.4;">📊</div>
            </div>
            <div style="margin-top: 8px; padding: 6px 8px; background-color: #fef3c7; border-radius: 4px; border-left: 3px solid #f59e0b;">
                <span style="font-size: 11px; color: #92400e;">Metered connection data required</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # === Card 4: Piped Water Supply (DATA GAP - understated design) ===
    with kpi_c4:
        st.markdown(f"""
        <div class="metric-container" style="background-color: #f9fafb; border: 1px dashed #d1d5db;">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div>
                    <div class="metric-label" style="color: #9ca3af;">Piped Water Supply</div>
                    <div class="metric-value" style="color: #9ca3af;">--</div>
                </div>
                <div style="font-size: 24px; opacity: 0.4;">🔧</div>
            </div>
            <div style="margin-top: 8px; padding: 6px 8px; background-color: #fef3c7; border-radius: 4px; border-left: 3px solid #f59e0b;">
                <span style="font-size: 11px; color: #92400e;">Piped water supply data required</span>
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
    
    # Filter data - use selected_year from global filter (case-insensitive)
    df_w_ladder = df_water.copy()
    df_s_ladder = df_sewer.copy()
    
    if selected_country != 'All': 
        df_w_ladder = df_w_ladder[df_w_ladder['country'].str.lower() == selected_country.lower()]
        df_s_ladder = df_s_ladder[df_s_ladder['country'].str.lower() == selected_country.lower()]
    if selected_zone != 'All': 
        df_w_ladder = df_w_ladder[df_w_ladder['zone'].str.lower() == selected_zone.lower()]
        df_s_ladder = df_s_ladder[df_s_ladder['zone'].str.lower() == selected_zone.lower()]
    
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
    
    # Color schemes - Updated based on user requirements
    # Water: Safely Managed -> Basic -> Limited -> Unimproved -> Surface Water
    water_colors = ['#088BCE', '#48BFE7', '#FDEE79', '#FFD94F', '#FFB02B']
    # Sanitation: Safely Managed -> Basic -> Limited -> Unimproved -> Open Defecation
    sanitation_colors = ['#349438', '#49B754', '#FDEE79', '#FFD94F', '#FFB02B']
    
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
            df_w_trend = df_w_trend[df_w_trend['country'].str.lower() == selected_country.lower()]
            df_s_trend = df_s_trend[df_s_trend['country'].str.lower() == selected_country.lower()]
        if selected_zone != 'All':
            df_w_trend = df_w_trend[df_w_trend['zone'].str.lower() == selected_zone.lower()]
            df_s_trend = df_s_trend[df_s_trend['zone'].str.lower() == selected_zone.lower()]
        
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
    
    # Chart Controls - Removed "Combined View" option
    trend_metric = st.radio(
        "Select Metric:", 
        ["Coverage (%)", "Growth Rate (%)"], 
        horizontal=True,
        key="trend_metric_selector",
        label_visibility="collapsed"
    )
    
    cg_col1, cg_col2 = st.columns([3, 1])
    
    with cg_col1:
        with st.spinner("📊 Loading growth trends data..."):
            # Prepare Water Data (Annual -> Quarterly Interpolation)
            df_w_growth = df_water.copy()
            if selected_country != 'All': df_w_growth = df_w_growth[df_w_growth['country'].str.lower() == selected_country.lower()]
            if selected_zone != 'All': df_w_growth = df_w_growth[df_w_growth['zone'].str.lower() == selected_zone.lower()]
            
            w_annual = df_w_growth.groupby('year').agg({'municipal_coverage': 'sum', 'popn_total': 'sum'}).reset_index()
            # Assume annual data is end of year
            w_annual['date'] = pd.to_datetime(w_annual['year'].astype(str) + '-12-31')
            w_annual = w_annual.set_index('date').sort_index()
            
            # Prepare Sewer Data (Monthly -> Quarterly)
            df_s_growth = df_service.copy()
            if selected_country != 'All': df_s_growth = df_s_growth[df_s_growth['country'].str.lower() == selected_country.lower()]
            if selected_zone != 'All': df_s_growth = df_s_growth[df_s_growth['zone'].str.lower() == selected_zone.lower()]
            
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
                w_q['quarter_label'] = w_q.index.map(format_quarterly_label)
                
                # Resample Sewer
                s_q = s_monthly.resample('Q').agg({'sewer_connections': 'last', 'households': 'last'})
                s_q['coverage_pct'] = (s_q['sewer_connections'] / s_q['households'] * 100).fillna(0)
                s_q['growth_rate'] = s_q['coverage_pct'].pct_change() * 100
                s_q['quarter_label'] = s_q.index.map(format_quarterly_label)
                
                # Plot
                fig_growth = go.Figure()
                
                # Colors
                color_water = '#2874A6'  # Water color
                color_sewer = '#1E8449'  # Sanitation color
                
                # Water Coverage
                if trend_metric == "Coverage (%)":
                    fig_growth.add_trace(go.Scatter(
                        x=w_q['quarter_label'], y=w_q['coverage_pct'],
                        name='Water Coverage',
                        mode='lines+markers',
                        line=dict(color=color_water, width=3),
                        marker=dict(size=6),
                        fill='tozeroy',
                        fillcolor='rgba(40, 116, 166, 0.1)',
                        hovertemplate='<b>Water Coverage</b><br>Quarter: %{x}<br>Coverage: %{y:.1f}%<extra></extra>'
                    ))
                    
                    # Sewer Coverage
                    fig_growth.add_trace(go.Scatter(
                        x=s_q['quarter_label'], y=s_q['coverage_pct'],
                        name='Sewer Coverage',
                        mode='lines+markers',
                        line=dict(color=color_sewer, width=3),
                        marker=dict(size=6),
                        fill='tozeroy',
                        fillcolor='rgba(30, 132, 73, 0.1)',
                        hovertemplate='<b>Sewer Coverage</b><br>Quarter: %{x}<br>Coverage: %{y:.1f}%<extra></extra>'
                    ))
                
                # Water Growth Rate
                if trend_metric == "Growth Rate (%)":
                    # Conditional colors: green for positive, red for negative
                    w_colors = [color_water if val >= 0 else '#F87171' for val in w_q['growth_rate']]
                    
                    fig_growth.add_trace(go.Bar(
                        x=w_q['quarter_label'], y=w_q['growth_rate'],
                        name='Water Growth Rate',
                        marker_color=w_colors,
                        hovertemplate='<b>Water Growth Rate</b><br>Quarter: %{x}<br>Growth: %{y:+.2f}%<extra></extra>'
                    ))
                    
                    # Sewer Growth Rate
                    s_colors = [color_sewer if val >= 0 else '#F87171' for val in s_q['growth_rate']]
                    
                    fig_growth.add_trace(go.Bar(
                        x=s_q['quarter_label'], y=s_q['growth_rate'],
                        name='Sewer Growth Rate',
                        marker_color=s_colors,
                        hovertemplate='<b>Sewer Growth Rate</b><br>Quarter: %{x}<br>Growth: %{y:+.2f}%<extra></extra>'
                    ))
                
                # Layout Updates - Improved for quarterly display
                layout_args = dict(
                    title=dict(text=f"Coverage Trends by Quarter: {trend_metric}", font=dict(size=16, color="#111827")),
                    xaxis=dict(
                        title="Quarter",
                        showgrid=True,
                        gridcolor='rgba(128,128,128,0.1)',
                        tickangle=-45
                    ),
                    yaxis=dict(
                        title="Percentage (%)" if trend_metric == "Coverage (%)" else "Growth Rate (%)",
                        showgrid=True,
                        gridcolor='rgba(128,128,128,0.1)',
                        zeroline=False
                    ),
                    hovermode='x unified',
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    height=450,
                    margin=dict(l=0, r=0, t=50, b=80),
                    plot_bgcolor='rgba(255,255,255,1)',
                    paper_bgcolor='rgba(255,255,255,1)',
                    barmode='group'
                )
                
                if trend_metric == "Coverage (%)":
                    layout_args['yaxis']['range'] = [0, 100]
                
                fig_growth.update_layout(**layout_args)
                
                st.plotly_chart(fig_growth, use_container_width=True)
            else:
                st.info("📊 Insufficient data for growth trends.")
            
    with cg_col2:
        st.markdown("""
        <div style="background-color: #f9fafb; padding: 16px; border-radius: 8px; height: 100%;">
            <h4 style="margin-top: 0; color: #111827;">📋 Analysis Notes</h4>
            <p style="font-size: 12px; color: #4b5563;">
                <strong>Quarterly Granularity:</strong> Data is aggregated and displayed at quarterly intervals (Q1-Q4 format).
            </p>
            <p style="font-size: 12px; color: #4b5563;">
                <strong>Water Coverage:</strong> Interpolated from annual data points using time-based methods.
            </p>
            <p style="font-size: 12px; color: #4b5563;">
                <strong>Sewer Coverage:</strong> Derived from monthly data aggregated to quarterly periods.
            </p>
            <p style="font-size: 12px; color: #4b5563;">
                <strong>Growth Rate:</strong> Shows quarter-over-quarter percentage change in coverage.
            </p>
        </div>
        """, unsafe_allow_html=True)

    # --- Step 4: Infrastructure Metrics Row ---
    st.markdown("<div class='section-header'>🏗️ Infrastructure Metrics</div>", unsafe_allow_html=True)
    
    inf_c1, inf_c2, inf_c3 = st.columns(3)
    
    with inf_c1:
        st.markdown("**Metering Status**")
        # Use real metering data from service data
        if not df_svc_filt.empty and 'metered' in df_svc_filt.columns and 'total_consumption' in df_svc_filt.columns:
            # Calculate metered vs non-metered consumption
            total_metered = df_svc_filt['metered'].sum()
            total_consumption = df_svc_filt['total_consumption'].sum()
            
            if total_consumption > 0:
                metered_pct = (total_metered / total_consumption) * 100
                non_metered_pct = 100 - metered_pct
                
                meter_fig = go.Figure(data=[go.Pie(
                    labels=['Metered', 'Non-metered'], 
                    values=[metered_pct, non_metered_pct], 
                    hole=.6,
                    marker_colors=['#3B82F6', '#9CA3AF'],
                    textinfo='percent',
                    textposition='outside'
                )])
                meter_fig.update_layout(
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                    margin=dict(l=20, r=20, t=0, b=40),
                    height=200,
                    annotations=[dict(
                        text=f"{metered_pct:.1f}%<br>Metered",
                        x=0.5, y=0.5,
                        showarrow=False,
                        font=dict(size=12, color="#1f2937")
                    )]
                )
                st.plotly_chart(meter_fig, use_container_width=True)
            else:
                # Fallback if no consumption data
                st.info("No consumption data available for metering analysis")
        else:
            # No metering data - show placeholder
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
            
            # Calculate appropriate x-axis range (add 10% padding)
            max_coverage = zone_cov['Coverage %'].max()
            x_max = max(max_coverage * 1.1, 10)  # At least 10%, with 10% padding
            
            fig_zone = px.bar(zone_cov.sort_values('Coverage %'), x='Coverage %', y='zone', orientation='h',
                              color='Coverage %', color_continuous_scale=[[0, '#fed7aa'], [0.5, '#fb923c'], [1, '#3b82f6']],
                              labels={'zone': 'Zone', 'Coverage %': 'Coverage (%)'})
            fig_zone.update_layout(
                height=350, 
                margin=dict(l=0, r=0, t=0, b=0), 
                xaxis_title="Municipal Coverage (%)",
                xaxis=dict(range=[0, x_max])  # Dynamic x-axis range
            )
            st.plotly_chart(fig_zone, use_container_width=True)
            
        else:
            # Show line chart for specific zone over time (2020-2024)
            st.markdown(f"**Municipal Coverage Trend - {selected_zone}**")
            
            zone_trend = df_water[df_water['zone'].str.lower() == selected_zone.lower()].groupby('year').agg({
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
        
        # Apply country and zone filters (case-insensitive)
        if selected_country != 'All':
            df_w_start = df_w_start[df_w_start['country'].str.lower() == selected_country.lower()]
            df_w_end = df_w_end[df_w_end['country'].str.lower() == selected_country.lower()]
            df_s_start = df_s_start[df_s_start['country'].str.lower() == selected_country.lower()]
            df_s_end = df_s_end[df_s_end['country'].str.lower() == selected_country.lower()]
        if selected_zone != 'All':
            df_w_start = df_w_start[df_w_start['zone'].str.lower() == selected_zone.lower()]
            df_w_end = df_w_end[df_w_end['zone'].str.lower() == selected_zone.lower()]
            df_s_start = df_s_start[df_s_start['zone'].str.lower() == selected_zone.lower()]
            df_s_end = df_s_end[df_s_end['zone'].str.lower() == selected_zone.lower()]
        
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

    # ============================================================================
    # DATA EXPORT SECTION
    # ============================================================================
    
    st.markdown("---")
    st.markdown("<div class='section-header'>📦 Data Export</div>", unsafe_allow_html=True)
    
    export_tab1, export_tab2, export_tab3 = st.tabs(["💧 Water Access Data", "🚽 Sewer Access Data", "📈 Calculated Metrics"])
    
    # TAB 1: WATER ACCESS DATA EXPORT
    with export_tab1:
        st.markdown("**Export filtered water access data**")
        
        # Display options
        show_all_cols_w = st.checkbox("Show all columns", value=False, key="show_all_water")
        
        if show_all_cols_w:
            display_df_w = df_w_filt
        else:
            key_columns_w = ['country', 'zone', 'year', 'popn_total', 'municipal_coverage', 'safely_managed', 
                            'basic', 'limited', 'unimproved', 'surface_water']
            display_df_w = df_w_filt[[col for col in key_columns_w if col in df_w_filt.columns]]
        
        st.dataframe(display_df_w, use_container_width=True, height=400)
        
        # Export options
        export_col1, export_col2, export_col3 = st.columns(3)
        
        with export_col1:
            csv_data_w = df_w_filt.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download as CSV",
                data=csv_data_w,
                file_name=f"water_access_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_water_csv"
            )
        
        with export_col2:
            buffer_w = io.BytesIO()
            with pd.ExcelWriter(buffer_w, engine='openpyxl') as writer:
                df_w_filt.to_excel(writer, sheet_name='Water Access Data', index=False)
            buffer_w.seek(0)
            
            st.download_button(
                label="📥 Download as Excel",
                data=buffer_w,
                file_name=f"water_access_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_water_excel"
            )
        
        with export_col3:
            json_str_w = df_w_filt.to_json(orient='records', indent=2, default_handler=str)
            st.download_button(
                label="📥 Download as JSON",
                data=json_str_w,
                file_name=f"water_access_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="download_water_json"
            )
    
    # TAB 2: SEWER ACCESS DATA EXPORT
    with export_tab2:
        st.markdown("**Export filtered sewer access data**")
        
        # Display options
        show_all_cols_s = st.checkbox("Show all columns", value=False, key="show_all_sewer")
        
        if show_all_cols_s:
            display_df_s = df_s_filt
        else:
            key_columns_s = ['country', 'zone', 'year', 'popn_total', 'connections', 'safely_managed', 
                            'basic', 'limited', 'unimproved', 'open_defecation']
            display_df_s = df_s_filt[[col for col in key_columns_s if col in df_s_filt.columns]]
        
        st.dataframe(display_df_s, use_container_width=True, height=400)
        
        # Export options
        export_col1_s, export_col2_s, export_col3_s = st.columns(3)
        
        with export_col1_s:
            csv_data_s = df_s_filt.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download as CSV",
                data=csv_data_s,
                file_name=f"sewer_access_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_sewer_csv"
            )
        
        with export_col2_s:
            buffer_s = io.BytesIO()
            with pd.ExcelWriter(buffer_s, engine='openpyxl') as writer:
                df_s_filt.to_excel(writer, sheet_name='Sewer Access Data', index=False)
            buffer_s.seek(0)
            
            st.download_button(
                label="📥 Download as Excel",
                data=buffer_s,
                file_name=f"sewer_access_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_sewer_excel"
            )
        
        with export_col3_s:
            json_str_s = df_s_filt.to_json(orient='records', indent=2, default_handler=str)
            st.download_button(
                label="📥 Download as JSON",
                data=json_str_s,
                file_name=f"sewer_access_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="download_sewer_json"
            )
    
    # TAB 3: CALCULATED METRICS EXPORT
    with export_tab3:
        st.markdown("**All calculated access metrics in one file**")
        st.info("📌 This file contains all derived metrics calculated from the raw data for easy analysis and reporting.")
        
        # Zone-Level Water Metrics
        water_zone_metrics = pd.DataFrame()
        if 'zone' in df_w_filt.columns and not df_w_filt.empty:
            water_zone_agg = df_w_filt.groupby('zone').agg({
                'popn_total': 'sum',
                'municipal_coverage': 'sum'
            }).reset_index()
            
            # Add safely_managed if exists
            if 'safely_managed' in df_w_filt.columns:
                water_zone_agg['safely_managed'] = df_w_filt.groupby('zone')['safely_managed'].sum().values
            
            water_zone_agg['coverage_rate'] = (water_zone_agg['municipal_coverage'] / water_zone_agg['popn_total'] * 100).fillna(0)
            water_zone_agg['metric_type'] = 'Water Zone Summary'
            water_zone_metrics = water_zone_agg
        
        # Zone-Level Sewer Metrics
        sewer_zone_metrics = pd.DataFrame()
        if 'zone' in df_s_filt.columns and not df_s_filt.empty:
            sewer_zone_agg = df_s_filt.groupby('zone').agg({
                'popn_total': 'sum'
            }).reset_index()
            
            # Add connections if exists
            if 'connections' in df_s_filt.columns:
                sewer_zone_agg['connections'] = df_s_filt.groupby('zone')['connections'].sum().values
                sewer_zone_agg['coverage_rate'] = (sewer_zone_agg['connections'] / sewer_zone_agg['popn_total'] * 100).fillna(0)
            
            if 'safely_managed' in df_s_filt.columns:
                sewer_zone_agg['safely_managed'] = df_s_filt.groupby('zone')['safely_managed'].sum().values
            
            sewer_zone_agg['metric_type'] = 'Sewer Zone Summary'
            sewer_zone_metrics = sewer_zone_agg
        
        # Overall Summary Metrics
        # Water metrics
        total_pop_water = df_w_filt['popn_total'].sum() if not df_w_filt.empty else 0
        muni_coverage_count = df_w_filt['municipal_coverage'].sum() if not df_w_filt.empty and 'municipal_coverage' in df_w_filt.columns else 0
        water_coverage_rate = (muni_coverage_count / total_pop_water * 100) if total_pop_water > 0 else 0
        
        # Sewer metrics
        total_pop_sewer = df_s_filt['popn_total'].sum() if not df_s_filt.empty else 0
        sewer_conn_count = df_s_filt['connections'].sum() if not df_s_filt.empty and 'connections' in df_s_filt.columns else 0
        sewer_coverage_rate = (sewer_conn_count / total_pop_sewer * 100) if total_pop_sewer > 0 else 0
        
        summary_metrics = pd.DataFrame({
            'Metric': [
                'Total Population (Water Data)',
                'Municipal Water Coverage (count)',
                'Water Coverage Rate (%)',
                'Total Population (Sewer Data)',
                'Sewer Connections (count)',
                'Sewer Coverage Rate (%)',
                'Number of Zones (Water)',
                'Number of Zones (Sewer)',
                'Report Generated',
                'Selected Year'
            ],
            'Value': [
                f"{total_pop_water:,.0f}",
                f"{muni_coverage_count:,.0f}",
                f"{water_coverage_rate:.2f}",
                f"{total_pop_sewer:,.0f}",
                f"{sewer_conn_count:,.0f}",
                f"{sewer_coverage_rate:.2f}",
                f"{df_w_filt['zone'].nunique() if 'zone' in df_w_filt.columns else 0}",
                f"{df_s_filt['zone'].nunique() if 'zone' in df_s_filt.columns else 0}",
                pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                f"{selected_year}" if selected_year else "All Years"
            ]
        })
        
        # Display water zone metrics if available
        if not water_zone_metrics.empty:
            st.subheader("Water Access - Zone-Level Metrics")
            st.dataframe(water_zone_metrics, use_container_width=True, height=200)
        
        # Display sewer zone metrics if available
        if not sewer_zone_metrics.empty:
            st.subheader("Sewer Access - Zone-Level Metrics")
            st.dataframe(sewer_zone_metrics, use_container_width=True, height=200)
        
        # Display summary metrics
        st.subheader("Overall Summary Metrics")
        st.dataframe(summary_metrics, use_container_width=True, height=250)
        
        # Export calculated metrics
        export_metric_col1, export_metric_col2, export_metric_col3 = st.columns(3)
        
        with export_metric_col1:
            # Combined metrics CSV
            combined_metrics_list = [summary_metrics.assign(metric_category='Overall_Summary')]
            if not water_zone_metrics.empty:
                combined_metrics_list.insert(0, water_zone_metrics.assign(metric_category='Water_Zone_Level'))
            if not sewer_zone_metrics.empty:
                combined_metrics_list.insert(0, sewer_zone_metrics.assign(metric_category='Sewer_Zone_Level'))
            
            combined_metrics = pd.concat(combined_metrics_list, ignore_index=True, sort=False)
            
            csv_metrics = combined_metrics.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Metrics as CSV",
                data=csv_metrics,
                file_name=f"access_metrics_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_access_metrics_csv"
            )
        
        with export_metric_col2:
            # Excel with multiple sheets
            buffer_metrics = io.BytesIO()
            with pd.ExcelWriter(buffer_metrics, engine='openpyxl') as writer:
                if not water_zone_metrics.empty:
                    water_zone_metrics.to_excel(writer, sheet_name='Water_Zone_Metrics', index=False)
                if not sewer_zone_metrics.empty:
                    sewer_zone_metrics.to_excel(writer, sheet_name='Sewer_Zone_Metrics', index=False)
                summary_metrics.to_excel(writer, sheet_name='Summary_Metrics', index=False)
            buffer_metrics.seek(0)
            
            st.download_button(
                label="📥 Download Metrics as Excel",
                data=buffer_metrics,
                file_name=f"access_metrics_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_access_metrics_excel"
            )
        
        with export_metric_col3:
            # JSON export for metrics
            metrics_json = {
                'water_zone_metrics': water_zone_metrics.to_dict(orient='records') if not water_zone_metrics.empty else [],
                'sewer_zone_metrics': sewer_zone_metrics.to_dict(orient='records') if not sewer_zone_metrics.empty else [],
                'summary_metrics': summary_metrics.to_dict(orient='records'),
                'generated_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            json_str_metrics = json.dumps(metrics_json, indent=2, default=str)
            st.download_button(
                label="📥 Download Metrics as JSON",
                data=json_str_metrics,
                file_name=f"access_metrics_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="download_access_metrics_json"
            )

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
