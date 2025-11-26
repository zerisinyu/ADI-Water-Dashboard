import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
from utils import prepare_service_data, DATA_DIR

@st.cache_data
def load_finance_data():
    """Load billing, financial services, and production data for the finance dashboard."""
    # Paths
    billing_path = DATA_DIR / "all_data - billing.csv"
    if not billing_path.exists():
        billing_path = DATA_DIR / "billing.csv"
    
    fin_path = DATA_DIR / "financial_services.csv"
    prod_path = DATA_DIR / "production.csv"
    
    df_billing = pd.DataFrame()
    df_fin = pd.DataFrame()
    df_prod = pd.DataFrame()
    
    # Load Billing
    if billing_path.exists():
        try:
            # Read only necessary columns to save memory if file is huge
            # We need: date, billed, paid, consumption_m3, customer_id, country (maybe)
            df_billing = pd.read_csv(billing_path, low_memory=False)
            
            # Ensure numeric columns are actually numeric
            cols_to_numeric = ['billed', 'paid', 'consumption_m3']
            for col in cols_to_numeric:
                if col in df_billing.columns:
                    if df_billing[col].dtype == 'object':
                        df_billing[col] = df_billing[col].astype(str).str.replace(r'[$,]', '', regex=True)
                    df_billing[col] = pd.to_numeric(df_billing[col], errors='coerce').fillna(0)

            # Date parsing
            if 'date' in df_billing.columns:
                df_billing['date_dt'] = pd.to_datetime(df_billing['date'], errors='coerce')
            elif 'date_MMYY' in df_billing.columns:
                df_billing['date_dt'] = pd.to_datetime(df_billing['date_MMYY'], format='%b/%y', errors='coerce')
            
            if 'date_dt' in df_billing.columns:
                df_billing['year'] = df_billing['date_dt'].dt.year
                df_billing['month'] = df_billing['date_dt'].dt.month
        except Exception as e:
            st.error(f"Error loading billing data: {e}")

    # Load Financial Services
    if fin_path.exists():
        try:
            df_fin = pd.read_csv(fin_path)
            
            # Ensure numeric columns
            cols_to_numeric_fin = ['sewer_billed', 'sewer_revenue', 'opex']
            for col in cols_to_numeric_fin:
                if col in df_fin.columns:
                    if df_fin[col].dtype == 'object':
                        df_fin[col] = df_fin[col].astype(str).str.replace(r'[$,]', '', regex=True)
                    df_fin[col] = pd.to_numeric(df_fin[col], errors='coerce').fillna(0)

            if 'date_MMYY' in df_fin.columns:
                df_fin['date_dt'] = pd.to_datetime(df_fin['date_MMYY'], format='%b/%y', errors='coerce')
            elif 'date' in df_fin.columns:
                df_fin['date_dt'] = pd.to_datetime(df_fin['date'], errors='coerce')
                
            if 'date_dt' in df_fin.columns:
                df_fin['year'] = df_fin['date_dt'].dt.year
                df_fin['month'] = df_fin['date_dt'].dt.month
        except Exception as e:
            st.error(f"Error loading financial data: {e}")

    # Load Production
    if prod_path.exists():
        try:
            df_prod = pd.read_csv(prod_path)
            
            # Ensure numeric columns
            cols_to_numeric_prod = ['production_m3']
            for col in cols_to_numeric_prod:
                if col in df_prod.columns:
                    if df_prod[col].dtype == 'object':
                        df_prod[col] = df_prod[col].astype(str).str.replace(r'[$,]', '', regex=True)
                    df_prod[col] = pd.to_numeric(df_prod[col], errors='coerce').fillna(0)

            if 'date_YYMMDD' in df_prod.columns:
                df_prod['date_dt'] = pd.to_datetime(df_prod['date_YYMMDD'], format='%Y/%m/%d', errors='coerce')
            elif 'date' in df_prod.columns:
                df_prod['date_dt'] = pd.to_datetime(df_prod['date'], errors='coerce')
                
            if 'date_dt' in df_prod.columns:
                df_prod['year'] = df_prod['date_dt'].dt.year
                df_prod['month'] = df_prod['date_dt'].dt.month
        except Exception as e:
            st.error(f"Error loading production data: {e}")
            
    return df_billing, df_fin, df_prod

def scene_finance():
    """
    Enhanced Financial Dashboard - Comprehensive Financial Analysis

    Features:
    - Import national and financial service data
    - Advanced billing, debt, and financial analysis
    - Interactive filters by country, city, date range
    - Export filtered/analyzed data
    - Upload custom data functionality
    """

    # Custom CSS
    st.markdown("""
    <style>
        .panel {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .metric-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            height: 100%;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
        }
        .status-good { background: #d1fae5; color: #065f46; }
        .status-warning { background: #fed7aa; color: #92400e; }
        .status-critical { background: #fee2e2; color: #991b1b; }
        .upload-section {
            background: #f9fafb;
            border: 2px dashed #d1d5db;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .filter-section {
            background: #f3f4f6;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
        }
        .info-box {
            background: #eff6ff;
            border-left: 4px solid #3b82f6;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
        }
        .success-box {
            background: #d1fae5;
            border-left: 4px solid #10b981;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
        }
    </style>
    """, unsafe_allow_html=True)

    # Header
    st.title("💰 Water Utility Financial Dashboard - Enhanced")
    st.markdown("**Comprehensive Financial Analysis with Real Data Integration**")

    # ============================================================================
    # DATA IMPORT SECTION
    # ============================================================================

    st.markdown('<div class="upload-section">', unsafe_allow_html=True)
    st.subheader("📁 Data Import")

    # Initialize session state for data
    if 'national_data' not in st.session_state:
        st.session_state.national_data = None
    if 'fin_service_data' not in st.session_state:
        st.session_state.fin_service_data = None

    # Tab for different import methods
    import_tab1, import_tab2 = st.tabs(["📤 Upload Files", "📋 Use Default Data"])

    with import_tab1:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**National Budget Data**")
            national_file = st.file_uploader(
                "Upload National Data CSV", 
                type=['csv', 'xlsx'],
                key="national_upload",
                help="Required columns: country, city, date_YY, budget_allocated, san_allocation, wat_allocation, staff_cost, etc."
            )

            if national_file:
                try:
                    if national_file.name.endswith('.csv'):
                        st.session_state.national_data = pd.read_csv(national_file)
                    else:
                        st.session_state.national_data = pd.read_excel(national_file)
                    st.success(f"✓ Loaded {len(st.session_state.national_data)} national records")
                except Exception as e:
                    st.error(f"Error loading national data: {e}")

        with col2:
            st.markdown("**Financial Service Data**")
            fin_service_file = st.file_uploader(
                "Upload Financial Service CSV",
                type=['csv', 'xlsx'],
                key="fin_service_upload",
                help="Required columns: country, city, date_MMYY, sewer_billed, sewer_revenue, opex, complaints, resolved, etc."
            )

            if fin_service_file:
                try:
                    if fin_service_file.name.endswith('.csv'):
                        st.session_state.fin_service_data = pd.read_csv(fin_service_file)
                    else:
                        st.session_state.fin_service_data = pd.read_excel(fin_service_file)
                    st.success(f"✓ Loaded {len(st.session_state.fin_service_data)} service records")
                except Exception as e:
                    st.error(f"Error loading financial service data: {e}")

    with import_tab2:
        st.info("📌 Using default demonstration data (Cameroon - Yaounde)")
        if st.button("Load Default Data"):
            # Load default data from the provided files inside the repository Data folder
            try:
                st.session_state.national_data = pd.read_csv(DATA_DIR / 'Master_Data_DontEdit.xlsx-all_national.csv')
                st.session_state.fin_service_data = pd.read_csv(DATA_DIR / 'Master_Data_DontEdit.xlsx-all_fin_service.csv')
                st.success(f"✓ Loaded {len(st.session_state.national_data)} national records and {len(st.session_state.fin_service_data)} service records")
            except Exception as e:
                st.error(f"Error loading default data: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

    # Check if data is loaded
    if st.session_state.national_data is None or st.session_state.fin_service_data is None:
        st.warning("⚠️ Please upload data files or load default data to continue")
        return

    # Get data from session state
    national_df = st.session_state.national_data.copy()
    fin_service_df = st.session_state.fin_service_data.copy()

    # ============================================================================
    # DATA PREPROCESSING
    # ============================================================================

    # Convert date columns
    try:
        fin_service_df['date_parsed'] = pd.to_datetime(fin_service_df['date_MMYY'], format='%b/%y', errors='coerce')
        fin_service_df['year'] = fin_service_df['date_parsed'].dt.year
        fin_service_df['month'] = fin_service_df['date_parsed'].dt.month
        fin_service_df['month_name'] = fin_service_df['date_parsed'].dt.strftime('%B')
    except:
        st.warning("Date parsing issue - some date features may not work")

    # Calculate derived metrics
    fin_service_df['collection_rate'] = (fin_service_df['sewer_revenue'] / fin_service_df['sewer_billed'] * 100).fillna(0)
    fin_service_df['debt'] = fin_service_df['sewer_billed'] - fin_service_df['sewer_revenue']
    fin_service_df['complaint_resolution_rate'] = (fin_service_df['resolved'] / fin_service_df['complaints'] * 100).fillna(0)
    fin_service_df['cost_recovery_ratio'] = (fin_service_df['sewer_revenue'] / fin_service_df['opex'] * 100).fillna(0)
    fin_service_df['total_staff'] = fin_service_df['san_staff'] + fin_service_df['w_staff']
    fin_service_df['revenue_per_staff'] = fin_service_df['sewer_revenue'] / fin_service_df['total_staff']

    # ============================================================================
    # FILTER SECTION
    # ============================================================================

    st.markdown('<div class="filter-section">', unsafe_allow_html=True)
    st.subheader("🔍 Data Filters")

    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)

    with filter_col1:
        countries = ['All'] + sorted(national_df['country'].unique().tolist())
        selected_country = st.selectbox("Country", countries)

    with filter_col2:
        if selected_country != 'All':
            cities = ['All'] + sorted(national_df[national_df['country'] == selected_country]['city'].unique().tolist())
        else:
            cities = ['All'] + sorted(national_df['city'].unique().tolist())
        selected_city = st.selectbox("City", cities)

    with filter_col3:
        years = sorted(national_df['date_YY'].unique().tolist())
        year_range = st.select_slider("Year Range", options=years, value=(min(years), max(years)))

    with filter_col4:
        if 'month' in fin_service_df.columns:
            months = ['All'] + list(range(1, 13))
            selected_month = st.selectbox("Month", months, format_func=lambda x: 'All' if x == 'All' else pd.to_datetime(f'2020-{x}-01').strftime('%B'))
        else:
            selected_month = 'All'

    st.markdown('</div>', unsafe_allow_html=True)

    # Apply filters
    national_filtered = national_df.copy()
    fin_service_filtered = fin_service_df.copy()

    if selected_country != 'All':
        national_filtered = national_filtered[national_filtered['country'] == selected_country]
        fin_service_filtered = fin_service_filtered[fin_service_filtered['country'] == selected_country]

    if selected_city != 'All':
        national_filtered = national_filtered[national_filtered['city'] == selected_city]
        fin_service_filtered = fin_service_filtered[fin_service_filtered['city'] == selected_city]

    national_filtered = national_filtered[
        (national_filtered['date_YY'] >= year_range[0]) & 
        (national_filtered['date_YY'] <= year_range[1])
    ]

    if 'year' in fin_service_filtered.columns:
        fin_service_filtered = fin_service_filtered[
            (fin_service_filtered['year'] >= year_range[0]) & 
            (fin_service_filtered['year'] <= year_range[1])
        ]

    if selected_month != 'All' and 'month' in fin_service_filtered.columns:
        fin_service_filtered = fin_service_filtered[fin_service_filtered['month'] == selected_month]

    # Display filter summary
    st.info(f"📊 Viewing: **{len(national_filtered)}** national records, **{len(fin_service_filtered)}** service records")

    # ============================================================================
    # KEY METRICS DASHBOARD
    # ============================================================================

    st.markdown("---")
    st.subheader("📈 Key Financial Metrics")

    # Calculate aggregate metrics
    total_budget = national_filtered['budget_allocated'].sum()
    total_billed = fin_service_filtered['sewer_billed'].sum()
    total_revenue = fin_service_filtered['sewer_revenue'].sum()
    total_debt = fin_service_filtered['debt'].sum()
    avg_collection_rate = fin_service_filtered['collection_rate'].mean()
    total_opex = fin_service_filtered['opex'].sum()

    metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)

    with metric_col1:
        st.metric("Total Budget", f"${total_budget/1e9:.2f}B", help="Total allocated budget")

    with metric_col2:
        st.metric("Total Billed", f"${total_billed/1e9:.2f}B", help="Total amount billed to customers")

    with metric_col3:
        st.metric("Revenue Collected", f"${total_revenue/1e9:.2f}B", help="Total revenue collected")

    with metric_col4:
        collection_status = "🟢" if avg_collection_rate >= 80 else "🟡" if avg_collection_rate >= 60 else "🔴"
        st.metric("Collection Rate", f"{avg_collection_rate:.1f}%", delta=f"{collection_status}")

    with metric_col5:
        st.metric("Outstanding Debt", f"${total_debt/1e9:.2f}B", delta="Monitor", delta_color="inverse")

    # ============================================================================
    # BILLING ANALYSIS
    # ============================================================================

    st.markdown("---")
    st.subheader("💵 Billing Analysis")

    billing_tab1, billing_tab2, billing_tab3 = st.tabs(["📊 Billing Trends", "🏦 Revenue vs Costs", "📉 Collection Performance"])

    with billing_tab1:
        col1, col2 = st.columns(2)

        with col1:
            # Billing and Revenue Trend
            if 'date_parsed' in fin_service_filtered.columns:
                billing_trend = fin_service_filtered.groupby('date_parsed').agg({
                    'sewer_billed': 'sum',
                    'sewer_revenue': 'sum',
                    'debt': 'sum'
                }).reset_index()

                fig_billing = go.Figure()
                fig_billing.add_trace(go.Scatter(
                    x=billing_trend['date_parsed'],
                    y=billing_trend['sewer_billed'],
                    name='Billed Amount',
                    mode='lines+markers',
                    line=dict(color='#3b82f6', width=2)
                ))
                fig_billing.add_trace(go.Scatter(
                    x=billing_trend['date_parsed'],
                    y=billing_trend['sewer_revenue'],
                    name='Revenue Collected',
                    mode='lines+markers',
                    line=dict(color='#10b981', width=2)
                ))
                fig_billing.update_layout(
                    title='Billing vs Revenue Collection Over Time',
                    xaxis_title='Date',
                    yaxis_title='Amount ($)',
                    hovermode='x unified',
                    height=400
                )
                st.plotly_chart(fig_billing, use_container_width=True)

        with col2:
            # Debt Accumulation
            if 'date_parsed' in fin_service_filtered.columns:
                fig_debt = go.Figure()
                fig_debt.add_trace(go.Scatter(
                    x=billing_trend['date_parsed'],
                    y=billing_trend['debt'],
                    name='Outstanding Debt',
                    mode='lines+markers',
                    fill='tozeroy',
                    line=dict(color='#ef4444', width=2)
                ))
                fig_debt.update_layout(
                    title='Debt Accumulation Trend',
                    xaxis_title='Date',
                    yaxis_title='Debt ($)',
                    hovermode='x unified',
                    height=400
                )
                st.plotly_chart(fig_debt, use_container_width=True)

    with billing_tab2:
        col1, col2 = st.columns(2)

        with col1:
            # Revenue vs OPEX
            if 'date_parsed' in fin_service_filtered.columns:
                revenue_opex = fin_service_filtered.groupby('date_parsed').agg({
                    'sewer_revenue': 'sum',
                    'opex': 'sum'
                }).reset_index()

                fig_rev_opex = go.Figure()
                fig_rev_opex.add_trace(go.Bar(
                    x=revenue_opex['date_parsed'],
                    y=revenue_opex['sewer_revenue'],
                    name='Revenue',
                    marker_color='#10b981'
                ))
                fig_rev_opex.add_trace(go.Bar(
                    x=revenue_opex['date_parsed'],
                    y=revenue_opex['opex'],
                    name='Operating Expenses',
                    marker_color='#f59e0b'
                ))
                fig_rev_opex.update_layout(
                    title='Revenue vs Operating Expenses',
                    xaxis_title='Date',
                    yaxis_title='Amount ($)',
                    barmode='group',
                    height=400
                )
                st.plotly_chart(fig_rev_opex, use_container_width=True)

        with col2:
            # Cost Recovery Ratio
            avg_cost_recovery = fin_service_filtered['cost_recovery_ratio'].mean()

            fig_recovery = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=avg_cost_recovery,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Cost Recovery Ratio (%)"},
                delta={'reference': 100},
                gauge={
                    'axis': {'range': [None, 150]},
                    'bar': {'color': "#3b82f6"},
                    'steps': [
                        {'range': [0, 70], 'color': "#fee2e2"},
                        {'range': [70, 100], 'color': "#fed7aa"},
                        {'range': [100, 150], 'color': "#d1fae5"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 100
                    }
                }
            ))
            fig_recovery.update_layout(height=400)
            st.plotly_chart(fig_recovery, use_container_width=True)

    with billing_tab3:
        col1, col2 = st.columns(2)

        with col1:
            # Collection Rate by City
            if 'city' in fin_service_filtered.columns:
                city_collection = fin_service_filtered.groupby('city').agg({
                    'collection_rate': 'mean',
                    'sewer_billed': 'sum',
                    'sewer_revenue': 'sum'
                }).reset_index().sort_values('collection_rate', ascending=False)

                fig_city_col = px.bar(
                    city_collection,
                    x='city',
                    y='collection_rate',
                    title='Average Collection Rate by City',
                    color='collection_rate',
                    color_continuous_scale='RdYlGn',
                    labels={'collection_rate': 'Collection Rate (%)'}
                )
                fig_city_col.update_layout(height=400)
                st.plotly_chart(fig_city_col, use_container_width=True)

        with col2:
            # Monthly Collection Pattern
            if 'month_name' in fin_service_filtered.columns:
                month_collection = fin_service_filtered.groupby('month_name')['collection_rate'].mean().reset_index()

                fig_month = px.line(
                    month_collection,
                    x='month_name',
                    y='collection_rate',
                    title='Collection Rate by Month',
                    markers=True,
                    line_shape='spline'
                )
                fig_month.update_layout(height=400)
                st.plotly_chart(fig_month, use_container_width=True)

    # ============================================================================
    # DEBT ANALYSIS
    # ============================================================================

    st.markdown("---")
    st.subheader("🏦 Debt & Arrears Analysis")

    debt_col1, debt_col2, debt_col3 = st.columns(3)

    with debt_col1:
        avg_debt_per_month = total_debt / len(fin_service_filtered) if len(fin_service_filtered) > 0 else 0
        st.metric("Avg Monthly Debt", f"${avg_debt_per_month/1e6:.2f}M")

    with debt_col2:
        debt_to_billed_ratio = (total_debt / total_billed * 100) if total_billed > 0 else 0
        st.metric("Debt-to-Billed Ratio", f"{debt_to_billed_ratio:.1f}%")

    with debt_col3:
        if 'date_parsed' in fin_service_filtered.columns and len(fin_service_filtered) > 1:
            recent_debt_trend = fin_service_filtered.sort_values('date_parsed')['debt'].iloc[-3:].mean()
            previous_debt_trend = fin_service_filtered.sort_values('date_parsed')['debt'].iloc[-6:-3].mean()
            debt_change = ((recent_debt_trend - previous_debt_trend) / previous_debt_trend * 100) if previous_debt_trend != 0 else 0
            st.metric("Debt Trend (Recent)", f"{debt_change:+.1f}%", delta_color="inverse")

    # Debt Analysis Charts
    debt_chart_col1, debt_chart_col2 = st.columns(2)

    with debt_chart_col1:
        # Debt Aging Analysis
        if 'year' in fin_service_filtered.columns:
            debt_by_year = fin_service_filtered.groupby('year')['debt'].sum().reset_index()
            fig_debt_year = px.bar(
                debt_by_year,
                x='year',
                y='debt',
                title='Total Debt by Year',
                color='debt',
                color_continuous_scale='Reds'
            )
            fig_debt_year.update_layout(height=400)
            st.plotly_chart(fig_debt_year, use_container_width=True)

    with debt_chart_col2:
        # Top Debtors (by city)
        if 'city' in fin_service_filtered.columns:
            city_debt = fin_service_filtered.groupby('city')['debt'].sum().reset_index().sort_values('debt', ascending=False).head(10)
            fig_top_debt = px.bar(
                city_debt,
                y='city',
                x='debt',
                orientation='h',
                title='Top 10 Cities by Outstanding Debt',
                color='debt',
                color_continuous_scale='Reds'
            )
            fig_top_debt.update_layout(height=400)
            st.plotly_chart(fig_top_debt, use_container_width=True)

    # ============================================================================
    # FINANCIAL HEALTH ANALYSIS
    # ============================================================================

    st.markdown("---")
    st.subheader("📊 Financial Health Indicators")

    health_tab1, health_tab2, health_tab3 = st.tabs(["💰 Budget Analysis", "⚡ Efficiency Metrics", "👥 Staffing Costs"])

    with health_tab1:
        col1, col2 = st.columns(2)

        with col1:
            # Budget Allocation Breakdown
            if len(national_filtered) > 0:
                latest_year = national_filtered['date_YY'].max()
                latest_budget = national_filtered[national_filtered['date_YY'] == latest_year]

                budget_breakdown = pd.DataFrame({
                    'Category': ['Sanitation', 'Water', 'Staff', 'Training'],
                    'Amount': [
                        latest_budget['san_allocation'].sum(),
                        latest_budget['wat_allocation'].sum(),
                        latest_budget['staff_cost'].sum(),
                        latest_budget['staff_training_budget'].sum()
                    ]
                })

                fig_budget = px.pie(
                    budget_breakdown,
                    values='Amount',
                    names='Category',
                    title=f'Budget Allocation Breakdown ({latest_year})',
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig_budget.update_layout(height=400)
                st.plotly_chart(fig_budget, use_container_width=True)

        with col2:
            # Budget Trend Over Years
            if len(national_filtered) > 1:
                budget_trend = national_filtered.groupby('date_YY').agg({
                    'budget_allocated': 'sum',
                    'san_allocation': 'sum',
                    'wat_allocation': 'sum'
                }).reset_index()

                fig_budget_trend = go.Figure()
                fig_budget_trend.add_trace(go.Scatter(
                    x=budget_trend['date_YY'],
                    y=budget_trend['budget_allocated'],
                    name='Total Budget',
                    mode='lines+markers',
                    line=dict(width=3)
                ))
                fig_budget_trend.add_trace(go.Scatter(
                    x=budget_trend['date_YY'],
                    y=budget_trend['san_allocation'],
                    name='Sanitation',
                    mode='lines+markers'
                ))
                fig_budget_trend.add_trace(go.Scatter(
                    x=budget_trend['date_YY'],
                    y=budget_trend['wat_allocation'],
                    name='Water',
                    mode='lines+markers'
                ))
                fig_budget_trend.update_layout(
                    title='Budget Allocation Trends',
                    xaxis_title='Year',
                    yaxis_title='Amount ($)',
                    height=400
                )
                st.plotly_chart(fig_budget_trend, use_container_width=True)

    with health_tab2:
        col1, col2 = st.columns(2)

        with col1:
            # Revenue per Staff
            if 'revenue_per_staff' in fin_service_filtered.columns:
                avg_rev_per_staff = fin_service_filtered['revenue_per_staff'].mean()

                fig_rev_staff = go.Figure(go.Indicator(
                    mode="number+delta",
                    value=avg_rev_per_staff,
                    title={'text': "Avg Revenue per Staff ($)"},
                    number={'prefix': "$", 'valueformat': ",.0f"},
                    delta={'reference': avg_rev_per_staff * 0.9, 'relative': True}
                ))
                fig_rev_staff.update_layout(height=300)
                st.plotly_chart(fig_rev_staff, use_container_width=True)

                # Revenue per staff trend
                if 'date_parsed' in fin_service_filtered.columns:
                    rev_staff_trend = fin_service_filtered.groupby('date_parsed')['revenue_per_staff'].mean().reset_index()
                    fig_rev_staff_trend = px.line(
                        rev_staff_trend,
                        x='date_parsed',
                        y='revenue_per_staff',
                        title='Revenue per Staff Trend',
                        markers=True
                    )
                    st.plotly_chart(fig_rev_staff_trend, use_container_width=True)

        with col2:
            # Complaint Resolution Efficiency
            avg_resolution = fin_service_filtered['complaint_resolution_rate'].mean()

            fig_complaint = go.Figure(go.Indicator(
                mode="gauge+number",
                value=avg_resolution,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Complaint Resolution Rate (%)"},
                gauge={
                    'axis': {'range': [None, 100]},
                    'bar': {'color': "#10b981"},
                    'steps': [
                        {'range': [0, 60], 'color': "#fee2e2"},
                        {'range': [60, 80], 'color': "#fed7aa"},
                        {'range': [80, 100], 'color': "#d1fae5"}
                    ]
                }
            ))
            fig_complaint.update_layout(height=300)
            st.plotly_chart(fig_complaint, use_container_width=True)

            # Complaint statistics
            total_complaints = fin_service_filtered['complaints'].sum()
            total_resolved = fin_service_filtered['resolved'].sum()
            unresolved = total_complaints - total_resolved

            st.metric("Total Complaints", f"{total_complaints:,.0f}")
            st.metric("Resolved", f"{total_resolved:,.0f}")
            st.metric("Unresolved", f"{unresolved:,.0f}", delta_color="inverse")

    with health_tab3:
        col1, col2 = st.columns(2)

        with col1:
            # Staff Composition
            total_san_staff = fin_service_filtered['san_staff'].sum()
            total_wat_staff = fin_service_filtered['w_staff'].sum()

            staff_comp = pd.DataFrame({
                'Department': ['Sanitation', 'Water'],
                'Staff Count': [total_san_staff, total_wat_staff]
            })

            fig_staff = px.pie(
                staff_comp,
                values='Staff Count',
                names='Department',
                title='Staff Distribution',
                color_discrete_sequence=['#3b82f6', '#10b981']
            )
            st.plotly_chart(fig_staff, use_container_width=True)

        with col2:
            # Staff Cost Analysis
            if len(national_filtered) > 0:
                staff_cost_trend = national_filtered.groupby('date_YY').agg({
                    'staff_cost': 'sum',
                    'trained_staff': 'sum',
                    'staff_training_budget': 'sum'
                }).reset_index()

                fig_staff_cost = go.Figure()
                fig_staff_cost.add_trace(go.Bar(
                    x=staff_cost_trend['date_YY'],
                    y=staff_cost_trend['staff_cost'],
                    name='Staff Cost',
                    marker_color='#3b82f6'
                ))
                fig_staff_cost.add_trace(go.Bar(
                    x=staff_cost_trend['date_YY'],
                    y=staff_cost_trend['staff_training_budget'],
                    name='Training Budget',
                    marker_color='#10b981'
                ))
                fig_staff_cost.update_layout(
                    title='Staff Cost & Training Budget Trend',
                    xaxis_title='Year',
                    yaxis_title='Amount ($)',
                    barmode='stack',
                    height=400
                )
                st.plotly_chart(fig_staff_cost, use_container_width=True)

    # ============================================================================
    # DATA TABLE & EXPORT
    # ============================================================================

    st.markdown("---")
    st.subheader("📋 Detailed Data View & Export")

    export_tab1, export_tab2 = st.tabs(["📊 Financial Service Data", "🏛️ National Budget Data"])

    with export_tab1:
        st.markdown(f"**{len(fin_service_filtered)} records displayed**")

        # Display options
        show_all_cols = st.checkbox("Show all columns", value=False, key="show_all_fin")

        if show_all_cols:
            display_df = fin_service_filtered
        else:
            key_columns = ['country', 'city', 'date_MMYY', 'sewer_billed', 'sewer_revenue', 
                          'debt', 'collection_rate', 'opex', 'cost_recovery_ratio', 
                          'complaints', 'resolved', 'complaint_resolution_rate']
            display_df = fin_service_filtered[[col for col in key_columns if col in fin_service_filtered.columns]]

        st.dataframe(display_df, use_container_width=True, height=400)

        # Export options
        export_col1, export_col2, export_col3 = st.columns(3)

        with export_col1:
            csv = fin_service_filtered.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name=f"financial_service_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

        with export_col2:
            # Excel export
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                fin_service_filtered.to_excel(writer, sheet_name='Financial Service', index=False)
            buffer.seek(0)

            st.download_button(
                label="📥 Download as Excel",
                data=buffer,
                file_name=f"financial_service_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with export_col3:
            # JSON export
            json_str = fin_service_filtered.to_json(orient='records', indent=2)
            st.download_button(
                label="📥 Download as JSON",
                data=json_str,
                file_name=f"financial_service_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )

    with export_tab2:
        st.markdown(f"**{len(national_filtered)} records displayed**")

        # Display options
        show_all_cols_nat = st.checkbox("Show all columns", value=False, key="show_all_nat")

        if show_all_cols_nat:
            display_df_nat = national_filtered
        else:
            key_columns_nat = ['country', 'city', 'date_YY', 'budget_allocated', 
                              'san_allocation', 'wat_allocation', 'staff_cost', 
                              'trained_staff', 'asset_health']
            display_df_nat = national_filtered[[col for col in key_columns_nat if col in national_filtered.columns]]

        st.dataframe(display_df_nat, use_container_width=True, height=400)

        # Export options
        export_col1, export_col2, export_col3 = st.columns(3)

        with export_col1:
            csv_nat = national_filtered.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download as CSV",
                data=csv_nat,
                file_name=f"national_budget_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

        with export_col2:
            # Excel export
            buffer_nat = io.BytesIO()
            with pd.ExcelWriter(buffer_nat, engine='openpyxl') as writer:
                national_filtered.to_excel(writer, sheet_name='National Budget', index=False)
            buffer_nat.seek(0)

            st.download_button(
                label="📥 Download as Excel",
                data=buffer_nat,
                file_name=f"national_budget_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with export_col3:
            # JSON export
            json_str_nat = national_filtered.to_json(orient='records', indent=2)
            st.download_button(
                label="📥 Download as JSON",
                data=json_str_nat,
                file_name=f"national_budget_data_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )

    # ============================================================================
    # SUMMARY INSIGHTS
    # ============================================================================

    st.markdown("---")
    st.subheader("💡 Key Insights & Recommendations")

    # Generate automated insights
    insights = []

    # Collection rate insight
    if avg_collection_rate < 70:
        insights.append(("🔴 Critical", f"Collection rate is low at {avg_collection_rate:.1f}%. Consider implementing stricter collection policies and incentive programs."))
    elif avg_collection_rate < 85:
        insights.append(("🟡 Warning", f"Collection rate at {avg_collection_rate:.1f}% needs improvement. Review billing processes and customer engagement strategies."))
    else:
        insights.append(("🟢 Good", f"Collection rate is healthy at {avg_collection_rate:.1f}%. Maintain current practices."))

    # Debt insight
    if debt_to_billed_ratio > 20:
        insights.append(("🔴 Critical", f"Debt-to-billed ratio is {debt_to_billed_ratio:.1f}%, indicating significant arrears. Implement aggressive debt recovery measures."))
    elif debt_to_billed_ratio > 10:
        insights.append(("🟡 Warning", f"Debt-to-billed ratio at {debt_to_billed_ratio:.1f}% requires attention. Consider debt restructuring options."))

    # Cost recovery insight
    avg_cost_recovery = fin_service_filtered['cost_recovery_ratio'].mean()
    if avg_cost_recovery < 80:
        insights.append(("🔴 Critical", f"Cost recovery ratio is only {avg_cost_recovery:.1f}%. Revenue doesn't cover operational costs. Review tariff structure."))
    elif avg_cost_recovery < 100:
        insights.append(("🟡 Warning", f"Cost recovery ratio at {avg_cost_recovery:.1f}% needs improvement to achieve financial sustainability."))
    else:
        insights.append(("🟢 Good", f"Cost recovery ratio is {avg_cost_recovery:.1f}%, indicating financial sustainability."))

    # Display insights
    for status, insight in insights:
        if "Critical" in status:
            st.error(f"{status}: {insight}")
        elif "Warning" in status:
            st.warning(f"{status}: {insight}")
        else:
            st.success(f"{status}: {insight}")

    # Footer
    st.markdown("---")
    st.caption(f"Dashboard generated on {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")