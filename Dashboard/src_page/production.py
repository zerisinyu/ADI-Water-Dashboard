import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
from datetime import datetime
from utils import (
    KPI,
    chart_card,
    DATA_DIR,
    filter_df_by_user_access,
    validate_selected_country,
    get_user_country_filter,
    render_kpi_row,
    render_page_header,
    render_section_header,
    render_empty_state,
    render_standardized_filters,
    apply_standard_filters,
    get_month_number,
)
from charts import (
    DATA_SERIES,
    DATA_WATER,
    STATUS_GOOD,
    STATUS_WARNING,
    STATUS_CRITICAL,
    apply_axis_percent,
    style_fig,
)
from data.metrics import per_capita_consumption

# Required columns for schema validation
PRODUCTION_REQUIRED_COLS = ['country', 'zone', 'source', 'production_m3']


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


@st.cache_data
def _load_billing_consumption():
    """
    Real monthly billed consumption (m³) per country/zone, used to compute
    Non-Revenue Water against production. Replaces the previous synthetic
    (np.random) consumption series so NRW reflects actual metered volume.
    """
    from data.database import query
    try:
        df = query(
            "SELECT date, country, zone, consumption_m3 "
            "FROM billing WHERE date IS NOT NULL"
        )
    except Exception:
        return pd.DataFrame(columns=["date", "country", "zone", "consumption_m3"])
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["consumption_m3"] = pd.to_numeric(df["consumption_m3"], errors="coerce").fillna(0)
    df = df.dropna(subset=["date"])
    df["_month"] = df["date"].dt.to_period("M")
    return df


@st.cache_data
def _load_population_by_year():
    """Real population served per country/year from water access data."""
    from data.database import query
    try:
        df = query("SELECT country, year, zone, popn_total FROM w_access")
    except Exception:
        return pd.DataFrame(columns=["country", "year", "zone", "popn_total"])
    if df.empty:
        return df
    df["popn_total"] = pd.to_numeric(df["popn_total"], errors="coerce")
    return df


def _population_for_rows(ts_df, selected_country, selected_zones):
    """
    Map a real annual population total onto each row of ``ts_df`` by year.
    Returns a Series aligned to ts_df.index (NaN where population is unknown).
    """
    pop = _load_population_by_year()
    if pop.empty or "year" not in ts_df.columns and "date_dt" not in ts_df.columns:
        return pd.Series([float("nan")] * len(ts_df), index=ts_df.index)
    if selected_country and selected_country != "All":
        pop = pop[pop["country"].str.lower() == selected_country.lower()]
    if selected_zones and "zone" in pop.columns:
        _zl = [z.lower() for z in selected_zones]
        pop = pop[pop["zone"].str.lower().isin(_zl)]
    if pop.empty:
        return pd.Series([float("nan")] * len(ts_df), index=ts_df.index)
    pop_by_year = pop.groupby("year")["popn_total"].sum()
    years = ts_df["date_dt"].dt.year if "date_dt" in ts_df.columns else ts_df["year"]
    return years.map(pop_by_year).astype(float)

def scene_production():
    """
    Production Manager Dashboard - Redesigned.
    Focus: Plant Uptime, Extraction Optimization, Source Sustainability.
    """
    
    render_page_header(
        "Production & Operations",
        eyebrow="Operations",
        subtitle="Source-level production, NRW, and operational metrics.",
        icon="factory",
        badges=[{"label": "Daily", "kind": "neutral"}],
    )

    # ============================================================================
    # DATA INITIALIZATION (Before UI elements)
    # ============================================================================
    
    # Initialize session state for data BEFORE expander to ensure data is available
    if 'production_data' not in st.session_state:
        st.session_state.production_data = None
    if 'production_default_data_loaded' not in st.session_state:
        st.session_state.production_default_data_loaded = False

    # AUTO-LOAD DEFAULT DATA ON FIRST PAGE LOAD (silently, outside expander)
    if not st.session_state.production_default_data_loaded:
        try:
            st.session_state.production_data = pd.read_csv(DATA_DIR / 'production.csv')
            st.session_state.production_default_data_loaded = True
        except Exception as e:
            st.session_state.production_default_data_loaded = True  # Prevent repeated attempts
    
    # ============================================================================
    # DATA IMPORT SECTION (Collapsed by default)
    # ============================================================================
    
    with st.expander("Data Import", expanded=False):
        # Show current data status
        if st.session_state.production_data is not None:
            st.success(f"Production data loaded: {len(st.session_state.production_data)} records")
        else:
            st.warning("No production data loaded")

        # Tab for different import methods
        import_tab1, import_tab2 = st.tabs(["Upload Custom Files", "Default Data"])

        with import_tab1:
            st.markdown("**Production Data**")
            production_file = st.file_uploader(
                "Upload Production Data CSV",
                type=['csv', 'xlsx'],
                key="production_upload",
                help="Required columns: country, zone, source, date_YYMMDD, production_m3, service_hours"
            )

            if production_file:
                try:
                    if production_file.name.endswith('.csv'):
                        uploaded_prod = pd.read_csv(production_file)
                    else:
                        uploaded_prod = pd.read_excel(production_file)
                    
                    # Schema validation
                    is_valid, missing, warning = validate_upload_schema(uploaded_prod, PRODUCTION_REQUIRED_COLS, "Production Data")
                    if not is_valid:
                        st.warning(warning)
                    else:
                        st.session_state.production_data = uploaded_prod
                        st.success(f"✓ Loaded {len(st.session_state.production_data)} production records")
                except Exception as e:
                    st.error(f"Error loading production data: {e}")

        with import_tab2:
            st.info("Using default production data from repository")
            if st.button("Reload Default Data", key="reload_production_default"):
                with st.spinner("Reloading default data..."):
                    try:
                        st.session_state.production_data = pd.read_csv(DATA_DIR / 'production.csv')
                        st.success(f"✓ Reloaded {len(st.session_state.production_data)} production records")
                    except Exception as e:
                        st.error(f"Error loading default data: {e}")

    # --- Load Data ---
    # Use session state data if available, otherwise use load_production_data()
    if st.session_state.production_data is not None:
        df_prod = st.session_state.production_data.copy()
        # Apply preprocessing for session state data
        cols_to_numeric = ['production_m3', 'service_hours']
        for col in cols_to_numeric:
            if col in df_prod.columns:
                if df_prod[col].dtype == 'object':
                    df_prod[col] = df_prod[col].astype(str).str.replace(r'[$,]', '', regex=True)
                df_prod[col] = pd.to_numeric(df_prod[col], errors='coerce').fillna(0)
        
        if 'date_YYMMDD' in df_prod.columns:
            df_prod['date_dt'] = pd.to_datetime(df_prod['date_YYMMDD'], format='%Y/%m/%d', errors='coerce')
        elif 'date' in df_prod.columns:
            df_prod['date_dt'] = pd.to_datetime(df_prod['date'], errors='coerce')
        
        if 'date_dt' in df_prod.columns:
            df_prod['year'] = df_prod['date_dt'].dt.year.astype('Int64')
            df_prod['month'] = df_prod['date_dt'].dt.month.astype('Int64')
            df_prod['day'] = df_prod['date_dt'].dt.day.astype('Int64')
        
        # Clean zone column to ensure matching works
        if 'zone' in df_prod.columns:
            df_prod['zone'] = df_prod['zone'].astype(str).str.strip()

        # Apply access control filtering
        df_prod = filter_df_by_user_access(df_prod, "country")
    else:
        df_prod = load_production_data()
    
    if df_prod.empty:
        st.warning("Production data not available.")
        return

    # --- Standardized Filters (AUDC Dictionary Compliant) ---
    filters = render_standardized_filters(
        df=df_prod,
        page="production",
        key_prefix="prod",
        country_col="country",
        zone_col="zone",
        year_col="year",
        show_period=True,
        show_zone=False, # We use a custom multiselect for zone on this page
        show_year=True,
        show_month=True  # Production data is Monthly/Daily
    )
    
    # Extract filter values
    view_type = filters['period']
    selected_country = filters['country']
    selected_zone = filters['zone']
    selected_year = filters['year']
    selected_month_name = filters.get('month', 'All')
    selected_month = get_month_number(selected_month_name)
    if selected_month is None:
        selected_month = 'All'
    
    # Production-specific: Zone multiselect and Unit toggle
    f3, f4 = st.columns([2, 1.5])
    
    with f3:
        # Zone/City Filter (multiselect for production)
        available_zones = []
        if selected_country != "All":
            if 'country' in df_prod.columns and 'zone' in df_prod.columns:
                available_zones = sorted(df_prod[df_prod['country'].str.lower() == selected_country.lower()]['zone'].unique().tolist())
        else:
            if 'zone' in df_prod.columns:
                available_zones = sorted(df_prod['zone'].unique().tolist())
        
        selected_zones = st.multiselect(
            "Zone/City (Multi-select)",
            available_zones,
            key="prod_zone_multiselect",
            placeholder="Select Zones"
        )
        
    with f4:
        # Unit Toggle
        unit_mode = st.radio(
            "Unit",
            ["Metric (m³)", "Imperial (gal)", "Percentage"],
            horizontal=True,
            key="prod_unit_toggle"
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
    
    # Apply standard filters (country, year, month)
    df_p_filt = apply_standard_filters(df_p_filt, filters, year_col='year', month_col='month')
        
    # Apply Zone Filter (multiselect - case-insensitive)
    if selected_zones and 'zone' in df_p_filt.columns:
        selected_zones_lower = [z.lower() for z in selected_zones]
        df_p_filt = df_p_filt[df_p_filt['zone'].str.lower().isin(selected_zones_lower)]

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
    render_section_header("Morning output check", eyebrow="Daily volumes", icon="wb_sunny")

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

    # Status classifications
    svc_kind = "positive" if avg_svc_hours >= 20 else ("neutral" if avg_svc_hours >= 12 else "negative")
    util_kind = "positive" if cap_utilization < 90 else "negative"

    # ---- Sparkline series (daily aggregates, last ~14 days) ----------------
    def _daily_series(df, col, agg="sum", n=14):
        if df is None or df.empty or col not in df.columns or "date_dt" not in df.columns:
            return []
        try:
            grouped = df.groupby(df["date_dt"].dt.date)[col].agg(agg).sort_index()
            return [float(v) for v in grouped.tail(n).tolist() if v is not None and not pd.isna(v)]
        except Exception:
            return []

    prod_spark = _daily_series(df_p_filt, "production_m3", "sum")
    svc_spark  = _daily_series(df_p_filt, "service_hours", "mean")
    src_spark  = []
    try:
        if "date_dt" in df_p_filt.columns and "production_m3" in df_p_filt.columns:
            grp = df_p_filt[df_p_filt["production_m3"] > 0].groupby(df_p_filt["date_dt"].dt.date)["source"].nunique()
            src_spark = [float(v) for v in grp.tail(14).tolist()]
    except Exception:
        pass
    util_spark = []
    try:
        if total_estimated_capacity > 0:
            daily_total = df_p_filt.groupby(df_p_filt["date_dt"].dt.date)["production_m3"].sum()
            util_series = (daily_total / total_estimated_capacity * 100).tail(14)
            util_spark = [float(v) for v in util_series.tolist() if v is not None and not pd.isna(v)]
    except Exception:
        pass

    # ---- Consumption per capita (l/c/d) — AUDC Production indicator ---------
    # Real billed consumption over the filtered window ÷ population served ÷ days.
    lcd_value = None
    try:
        _bill = _load_billing_consumption()
        if not _bill.empty:
            if selected_country and selected_country != "All":
                _bill = _bill[_bill["country"].str.lower() == selected_country.lower()]
            if selected_zones and "zone" in _bill.columns:
                _zl = [z.lower() for z in selected_zones]
                _bill = _bill[_bill["zone"].str.lower().isin(_zl)]
        _months_in_scope = df_p_filt["date_dt"].dt.to_period("M").unique()
        if not _bill.empty and len(_months_in_scope) > 0:
            _bill = _bill[_bill["_month"].isin(_months_in_scope)]
        _total_cons_m3 = float(_bill["consumption_m3"].sum()) if not _bill.empty else 0.0
        _pop = _population_for_rows(df_p_filt, selected_country, selected_zones)
        _pop_val = float(_pop.dropna().iloc[0]) if _pop.notna().any() else 0.0
        _span = df_p_filt["date_dt"].max() - df_p_filt["date_dt"].min()
        _days = max(int(_span.days) + 1, 1)
        lcd_value = per_capita_consumption(_total_cons_m3, _pop_val, _days)
    except Exception:
        lcd_value = None
    lcd_display = f"{lcd_value:.0f}" if lcd_value is not None else "—"
    # 50–100 l/c/d is the basic-to-adequate band (JMP); flag extremes.
    if lcd_value is None:
        lcd_kind = "neutral"
    elif lcd_value < 50:
        lcd_kind = "negative"
    elif lcd_value <= 150:
        lcd_kind = "positive"
    else:
        lcd_kind = "neutral"

    render_kpi_row([
        KPI("Total production", val_display,
            delta=unit_label_card,
            delta_kind="neutral",
            icon="water_drop",
            sparkline=prod_spark),
        KPI("Avg service hours", f"{avg_svc_hours:.1f}",
            delta="Target 24h",
            delta_kind=svc_kind,
            icon="schedule",
            footnote="hrs / day",
            sparkline=svc_spark),
        KPI("Active sources", f"{active_sources} / {total_sources_count}",
            delta="Online yesterday",
            delta_kind="neutral",
            icon="hub",
            sparkline=src_spark),
        KPI("Capacity utilisation", f"{cap_utilization:.1f}%",
            delta="of design capacity (est.)",
            delta_kind=util_kind,
            icon="bolt",
            sparkline=util_spark),
        KPI("Consumption per capita", lcd_display,
            delta="l/c/d",
            delta_kind=lcd_kind,
            icon="local_drink",
            footnote="Billed volume ÷ population served"),
    ])

    # Alerts
    low_svc_sources = df_latest[df_latest['service_hours'] < 12]['source'].tolist()
    if low_svc_sources:
        st.warning(f"Low supply alert · sources below 12 hrs yesterday: {', '.join(low_svc_sources)}")

    # ============================================================================
    # TABBED ANALYSIS SECTIONS
    # ============================================================================

    render_section_header("Production analysis", eyebrow="Deep dive")
    
    prod_tab1, prod_tab2, prod_tab3 = st.tabs(["Infrastructure", "Source analysis", "Trends & forecasting"])
    
    # ============================================================================
    # TAB 1: Treatment Infrastructure Performance
    # ============================================================================
    with prod_tab1:
        render_section_header("Treatment infrastructure performance", icon="water")
        st.markdown("Water Treatment Plants (WTP) and Faecal Sludge Management (FSM) metrics.")
        
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

        st.caption("⚠️ Data gap · FSTP utilisation data unavailable.")

    # ============================================================================
    # TAB 2: Source Balancing Act (Extraction Analysis)
    # ============================================================================
    with prod_tab2:
        render_section_header("Source balancing", icon="tune")
        st.markdown("Extraction analysis and source performance metrics.")
        
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
            
            # Use bar chart for better readability when daily data is dense
            if view_type == "Daily" and len(prod_trend) > 60:
                # Switch to line chart for cleaner visualization with many data points
                fig_mix = px.line(prod_trend, x=x_axis, y='volume_display', color='source',
                                  labels={'volume_display': y_label, x_axis: 'Date'},
                                  color_discrete_sequence=px.colors.qualitative.Safe)
                fig_mix.update_traces(mode='lines')
            else:
                # Use stacked bar chart for clearer comparison
                fig_mix = px.bar(prod_trend, x=x_axis, y='volume_display', color='source',
                                 labels={'volume_display': y_label, x_axis: 'Date'},
                                 color_discrete_sequence=px.colors.qualitative.Safe,
                                 barmode='stack')
            
            fig_mix.update_layout(
                height=350, 
                margin=dict(l=0, r=0, t=10, b=60), 
                legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"),
                xaxis_tickangle=-45
            )
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

    # ============================================================================
    # TAB 3: Production Trends & Forecasting
    # ============================================================================
    with prod_tab3:
        render_section_header("Production trends & forecasting", icon="show_chart")
        st.markdown("Advanced analytics with time series visualization and forecasting.")

        # --- Data Preparation for Time Series ---
        import numpy as np
    
    # Aggregate to daily total across all selected sources/zones
    ts_df = df_p_filt.groupby('date_dt')['volume_display'].sum().reset_index()
    ts_df = ts_df.sort_values('date_dt')
    
    if not ts_df.empty:
        # --- Real consumption & NRW (replaces former synthetic np.random series) ---
        # Pull actual billed consumption and distribute each month's real total
        # across days in proportion to that day's production. This keeps the
        # daily chart smooth while NRW aggregates to the true monthly figure.
        bill = _load_billing_consumption()
        if not bill.empty:
            if selected_country and selected_country != "All" and "country" in bill.columns:
                bill = bill[bill["country"].str.lower() == selected_country.lower()]
            if selected_zones and "zone" in bill.columns:
                _zl = [z.lower() for z in selected_zones]
                bill = bill[bill["zone"].str.lower().isin(_zl)]

        ts_df["_month"] = ts_df["date_dt"].dt.to_period("M")
        if not bill.empty:
            cons_monthly = bill.groupby("_month")["consumption_m3"].sum() * conversion_factor
        else:
            cons_monthly = pd.Series(dtype=float)
        has_real_consumption = not cons_monthly.empty

        prod_per_month = ts_df.groupby("_month")["volume_display"].transform("sum")
        day_share = (ts_df["volume_display"] / prod_per_month).fillna(0)
        month_cons = ts_df["_month"].map(cons_monthly).astype(float)
        ts_df["consumption"] = (month_cons * day_share).fillna(0)

        # NRW = produced − consumed; clip at 0 (billing lag can push monthly
        # consumption above production in individual periods).
        ts_df["nrw"] = (ts_df["volume_display"] - ts_df["consumption"]).clip(lower=0)

        # Population served — real annual figure from access data (held flat
        # within a year), left as NaN when unavailable rather than fabricated.
        ts_df["population"] = _population_for_rows(ts_df, selected_country, selected_zones)

        if not has_real_consumption:
            st.caption(
                "⚠️ No billed-consumption data for this selection — "
                "consumption and NRW are unavailable."
            )

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
            legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"),
            height=550,
            margin=dict(l=20, r=20, t=60, b=80)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available for trend analysis.")

    # ============================================================================
    # STRATEGIC PLANNING SECTION
    # ============================================================================
    
    st.markdown("---")
    render_section_header("Strategic planning", eyebrow="Forward look")
    
    plan_tab1, plan_tab2 = st.tabs(["Resource Sustainability", "Downtime Logger"])
    
    with plan_tab1:
        sp1, sp2 = st.columns([1, 1])
        
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
            
            fig_gauge.update_layout(height=300, margin=dict(l=20, r=20, t=30, b=20))
            st.plotly_chart(fig_gauge, use_container_width=True)
            st.caption("*Note: Resource limit estimated for demonstration.*")
        
        with sp2:
            st.markdown("**Resource Sustainability Insights**")
            if extraction_rate < 70:
                st.success(f"Extraction rate is sustainable at {extraction_rate:.1f}%")
            elif extraction_rate < 90:
                st.warning(f"Extraction rate at {extraction_rate:.1f}% - monitor closely")
            else:
                st.error(f"🔴 Critical extraction rate at {extraction_rate:.1f}% - action required")
            
            st.markdown("""
            **Recommendations:**
            - Monitor groundwater levels regularly
            - Consider alternative water sources
            - Implement demand-side management
            - Review infrastructure capacity
            """)
    
    with plan_tab2:
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

    # ============================================================================
    # DATA EXPORT SECTION
    # ============================================================================
    
    st.markdown("---")
    render_section_header("Data export", icon="download")
    
    export_tab1, export_tab2 = st.tabs(["Production Data", "Calculated Metrics"])
    
    # TAB 1: PRODUCTION DATA EXPORT
    with export_tab1:
        st.markdown("**Export filtered production data**")
        
        # Display options
        show_all_cols = st.checkbox("Show all columns", value=False, key="show_all_prod")
        
        if show_all_cols:
            display_df = df_p_filt
        else:
            key_columns = ['country', 'zone', 'source', 'date_dt', 'production_m3', 'service_hours', 'year', 'month']
            display_df = df_p_filt[[col for col in key_columns if col in df_p_filt.columns]]
        
        st.dataframe(display_df, use_container_width=True, height=400)
        
        # Export options
        export_col1, export_col2, export_col3 = st.columns(3)
        
        with export_col1:
            csv_data = df_p_filt.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download as CSV",
                data=csv_data,
                file_name=f"production_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_prod_csv"
            )
        
        with export_col2:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_p_filt.to_excel(writer, sheet_name='Production Data', index=False)
            buffer.seek(0)
            
            st.download_button(
                label="📥 Download as Excel",
                data=buffer,
                file_name=f"production_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_prod_excel"
            )
        
        with export_col3:
            json_str = df_p_filt.to_json(orient='records', indent=2, default_handler=str)
            st.download_button(
                label="📥 Download as JSON",
                data=json_str,
                file_name=f"production_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="download_prod_json"
            )
    
    # TAB 2: CALCULATED METRICS EXPORT
    with export_tab2:
        st.markdown("**All calculated production metrics in one file**")
        st.info("This file contains all derived metrics calculated from the raw data for easy analysis and reporting.")
        
        # Source-Level Metrics
        source_metrics = df_p_filt.groupby('source').agg({
            'production_m3': ['sum', 'mean', 'max', 'min'],
            'service_hours': ['mean', 'max', 'min']
        }).reset_index()
        source_metrics.columns = ['_'.join(col).strip('_') for col in source_metrics.columns.values]
        source_metrics['metric_type'] = 'Source Summary'
        
        # Zone-Level Metrics (if zone column exists)
        zone_metrics = pd.DataFrame()
        if 'zone' in df_p_filt.columns:
            zone_metrics = df_p_filt.groupby('zone').agg({
                'production_m3': ['sum', 'mean'],
                'service_hours': ['mean']
            }).reset_index()
            zone_metrics.columns = ['_'.join(col).strip('_') for col in zone_metrics.columns.values]
            zone_metrics['metric_type'] = 'Zone Summary'
        
        # Overall Summary Metrics
        total_production = df_p_filt['production_m3'].sum()
        avg_daily_production = df_p_filt['production_m3'].mean()
        avg_service_hours = df_p_filt['service_hours'].mean()
        max_daily_production = df_p_filt['production_m3'].max()
        min_daily_production = df_p_filt['production_m3'].min()
        total_days = df_p_filt['date_dt'].nunique() if 'date_dt' in df_p_filt.columns else 0
        
        summary_metrics = pd.DataFrame({
            'Metric': [
                'Total Production (m³)',
                'Average Daily Production (m³)',
                'Max Daily Production (m³)',
                'Min Daily Production (m³)',
                'Average Service Hours',
                'Total Days Recorded',
                'Number of Sources',
                'Number of Zones',
                'Report Generated',
                'Data Period'
            ],
            'Value': [
                f"{total_production:,.2f}",
                f"{avg_daily_production:,.2f}",
                f"{max_daily_production:,.2f}",
                f"{min_daily_production:,.2f}",
                f"{avg_service_hours:.2f}",
                f"{total_days:,}",
                f"{df_p_filt['source'].nunique() if 'source' in df_p_filt.columns else 0}",
                f"{df_p_filt['zone'].nunique() if 'zone' in df_p_filt.columns else 0}",
                pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                f"{df_p_filt['date_dt'].min().strftime('%Y-%m-%d') if 'date_dt' in df_p_filt.columns else 'N/A'} to {df_p_filt['date_dt'].max().strftime('%Y-%m-%d') if 'date_dt' in df_p_filt.columns else 'N/A'}"
            ]
        })
        
        # Display source metrics table
        st.subheader("Source-Level Metrics")
        st.dataframe(source_metrics, use_container_width=True, height=200)
        
        # Display zone metrics if available
        if not zone_metrics.empty:
            st.subheader("Zone-Level Metrics")
            st.dataframe(zone_metrics, use_container_width=True, height=200)
        
        # Display summary metrics
        st.subheader("Overall Summary Metrics")
        st.dataframe(summary_metrics, use_container_width=True, height=250)
        
        # Export calculated metrics
        export_metric_col1, export_metric_col2, export_metric_col3 = st.columns(3)
        
        with export_metric_col1:
            # Combined metrics CSV
            combined_metrics_list = [
                source_metrics.assign(metric_category='Source_Level'),
                summary_metrics.assign(metric_category='Overall_Summary')
            ]
            if not zone_metrics.empty:
                combined_metrics_list.insert(1, zone_metrics.assign(metric_category='Zone_Level'))
            
            combined_metrics = pd.concat(combined_metrics_list, ignore_index=True, sort=False)
            
            csv_metrics = combined_metrics.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Metrics as CSV",
                data=csv_metrics,
                file_name=f"production_metrics_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key="download_prod_metrics_csv"
            )
        
        with export_metric_col2:
            # Excel with multiple sheets
            buffer_metrics = io.BytesIO()
            with pd.ExcelWriter(buffer_metrics, engine='openpyxl') as writer:
                source_metrics.to_excel(writer, sheet_name='Source_Metrics', index=False)
                if not zone_metrics.empty:
                    zone_metrics.to_excel(writer, sheet_name='Zone_Metrics', index=False)
                summary_metrics.to_excel(writer, sheet_name='Summary_Metrics', index=False)
            buffer_metrics.seek(0)
            
            st.download_button(
                label="📥 Download Metrics as Excel",
                data=buffer_metrics,
                file_name=f"production_metrics_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_prod_metrics_excel"
            )
        
        with export_metric_col3:
            # JSON export for metrics
            import json
            metrics_json = {
                'source_metrics': source_metrics.to_dict(orient='records'),
                'zone_metrics': zone_metrics.to_dict(orient='records') if not zone_metrics.empty else [],
                'summary_metrics': summary_metrics.to_dict(orient='records'),
                'generated_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            json_str_metrics = json.dumps(metrics_json, indent=2, default=str)
            st.download_button(
                label="📥 Download Metrics as JSON",
                data=json_str_metrics,
                file_name=f"production_metrics_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="download_prod_metrics_json"
            )

