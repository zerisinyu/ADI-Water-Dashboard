import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
    Financial Health scene - Redesigned for Commercial Director / CFO.
    Focus: Cash Flow, Collection Efficiency, Cost Recovery.
    """
    # --- CSS Styling (Consistent with Quality/Access) ---
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
    df_billing, df_fin, df_prod = load_finance_data()
    
    if df_billing.empty and df_fin.empty:
        st.warning("⚠️ Financial data not available.")
        return

    # --- Filters (from Session State) ---
    # Header Section
    st.markdown("<h1 style='font-size: 24px; font-weight: 700; color: #111827; margin-bottom: 16px;'>Financial Health</h1>", unsafe_allow_html=True)
    
    # Filter Controls
    with st.container():
        st.markdown("""
            <style>
                div[data-testid="stHorizontalBlock"] {
                    align-items: center;
                }
            </style>
        """, unsafe_allow_html=True)
        
        f1, f2, f3, f4 = st.columns([1.5, 1.5, 2, 1])
        
        with f1:
            # Date Range Selector (View Type)
            view_type = st.selectbox(
                "View",
                ["Monthly", "Quarterly", "Annual"],
                key="fin_view_type",
                label_visibility="collapsed"
            )

        with f2:
            # Country Filter
            countries = ["All", "Uganda", "Cameroon", "Lesotho", "Malawi"]
            selected_country = st.selectbox(
                "Country",
                countries,
                key="fin_country_select",
                label_visibility="collapsed"
            )

        with f3:
            # Zone/City Filter (Multi-select)
            # Determine available zones based on country
            available_zones = []
            if selected_country != "All":
                # Try to get zones from billing or service data
                if not df_billing.empty and 'zone' in df_billing.columns and 'country' in df_billing.columns:
                    available_zones = sorted(df_billing[df_billing['country'] == selected_country]['zone'].unique().tolist())
                
                if not available_zones and not df_fin.empty and 'city' in df_fin.columns and 'country' in df_fin.columns:
                     available_zones = sorted(df_fin[df_fin['country'] == selected_country]['city'].unique().tolist())
            else:
                # All zones
                if not df_billing.empty and 'zone' in df_billing.columns:
                    available_zones = sorted(df_billing['zone'].unique().tolist())
            
            selected_zones = st.multiselect(
                "Zone/City",
                available_zones,
                default=[],
                key="fin_zone_select",
                placeholder="Select Zones/Cities",
                label_visibility="collapsed"
            )

        with f4:
            # Currency Toggle
            currency_mode = st.radio(
                "Currency",
                ["Local", "USD"],
                horizontal=True,
                key="fin_currency_toggle",
                label_visibility="collapsed"
            )

    st.markdown("---")

    # --- Apply Filters ---
    
    # 1. Billing Data
    df_b_filt = df_billing.copy()
    if not df_b_filt.empty:
        if selected_country != 'All' and 'country' in df_b_filt.columns:
            df_b_filt = df_b_filt[df_b_filt['country'] == selected_country]
        
        if selected_zones and 'zone' in df_b_filt.columns:
            df_b_filt = df_b_filt[df_b_filt['zone'].isin(selected_zones)]
            
        # Time filtering based on view_type would happen in aggregation steps usually, 
        # but here we might filter by a specific range if needed. 
        # For now, we keep full history for trends, but might filter for "Current Period" cards.

    # 2. Financial Services Data
    df_f_filt = df_fin.copy()
    if not df_f_filt.empty:
        if selected_country != 'All' and 'country' in df_f_filt.columns:
            df_f_filt = df_f_filt[df_f_filt['country'] == selected_country]
        
        # Map 'city' to zone selection if possible, or ignore if mismatch
        if selected_zones and 'city' in df_f_filt.columns:
             df_f_filt = df_f_filt[df_f_filt['city'].isin(selected_zones)]

    # 3. Production Data
    df_p_filt = df_prod.copy()
    if not df_p_filt.empty:
        if selected_country != 'All' and 'country' in df_p_filt.columns:
            df_p_filt = df_p_filt[df_p_filt['country'] == selected_country]
            
        if selected_zones and 'zone' in df_p_filt.columns:
            df_p_filt = df_p_filt[df_p_filt['zone'].isin(selected_zones)]

    # --- Step 1: The "Cash Flow" Pulse (Scorecard) ---
    st.markdown("<div class='section-header'>💸 Cash Flow Pulse <span style='font-size:14px;color:#6b7280;font-weight:400'>| Morning Check</span></div>", unsafe_allow_html=True)

    # Calculations
    # A. Collection Efficiency
    total_billed_water = df_b_filt['billed'].sum() if not df_b_filt.empty else 0
    total_paid_water = df_b_filt['paid'].sum() if not df_b_filt.empty else 0
    
    # Sewer billing/revenue from financial services
    total_billed_sewer = df_f_filt['sewer_billed'].sum() if not df_f_filt.empty and 'sewer_billed' in df_f_filt.columns else 0
    total_paid_sewer = df_f_filt['sewer_revenue'].sum() if not df_f_filt.empty and 'sewer_revenue' in df_f_filt.columns else 0
    
    total_billed = total_billed_water + total_billed_sewer
    total_collected = total_paid_water + total_paid_sewer
    
    coll_efficiency = (total_collected / total_billed * 100) if total_billed > 0 else 0
    
    # B. Total Revenue (Cash)
    # Already calculated as total_collected
    
    # C. Operating Cost Coverage (OCC)
    total_opex = df_f_filt['opex'].sum() if not df_f_filt.empty and 'opex' in df_f_filt.columns else 0
    occ = (total_collected / total_opex) if total_opex > 0 else 0
    
    # D. Unit Cost of Production
    total_production = df_p_filt['production_m3'].sum() if not df_p_filt.empty else 0
    unit_cost = (total_opex / total_production) if total_production > 0 else 0

    # Render Scorecard
    sc1, sc2, sc3, sc4 = st.columns(4)
    
    # 1. Collection Efficiency
    with sc1:
        target = 95
        delta = coll_efficiency - target
        delta_cls = "delta-up" if delta >= 0 else "delta-down"
        icon = "↑" if delta >= 0 else "↓"
        st.markdown(f"""
        <div class='metric-container'>
            <div class='metric-label'>Collection Efficiency</div>
            <div class='metric-value'>{coll_efficiency:.1f}%</div>
            <div class='metric-delta {delta_cls}'>{icon} {abs(delta):.1f}% vs Target ({target}%)</div>
        </div>
        """, unsafe_allow_html=True)

    # 2. Total Revenue
    with sc2:
        # Format large numbers
        if total_collected > 1e9:
            val_str = f"{total_collected/1e9:.2f}B"
        elif total_collected > 1e6:
            val_str = f"{total_collected/1e6:.2f}M"
        else:
            val_str = f"{total_collected:,.0f}"
            
        st.markdown(f"""
        <div class='metric-container'>
            <div class='metric-label'>Total Revenue (Cash)</div>
            <div class='metric-value'>{val_str}</div>
            <div class='metric-sub'>Water + Sewer</div>
        </div>
        """, unsafe_allow_html=True)

    # 3. Operating Cost Coverage
    with sc3:
        target_occ = 1.0
        delta_occ = occ - target_occ
        delta_cls_occ = "delta-up" if delta_occ >= 0 else "delta-down"
        icon_occ = "↑" if delta_occ >= 0 else "↓"
        
        st.markdown(f"""
        <div class='metric-container'>
            <div class='metric-label'>Op. Cost Coverage</div>
            <div class='metric-value'>{occ:.2f}</div>
            <div class='metric-delta {delta_cls_occ}'>{icon_occ} {abs(delta_occ):.2f} vs Target (1.0)</div>
        </div>
        """, unsafe_allow_html=True)

    # 4. Unit Cost of Production
    with sc4:
        st.markdown(f"""
        <div class='metric-container'>
            <div class='metric-label'>Unit Cost of Prod.</div>
            <div class='metric-value'>${unit_cost:.2f}</div>
            <div class='metric-sub'>per m³</div>
        </div>
        """, unsafe_allow_html=True)

    # --- Step 2: Revenue Gap Analysis ---
    st.markdown("<div class='section-header'>📉 Revenue Gap Analysis <span style='font-size:14px;color:#6b7280;font-weight:400'>| Billing vs Collection</span></div>", unsafe_allow_html=True)
    
    col_rev1, col_rev2 = st.columns(2)
    
    with col_rev1:
        st.markdown("**Billed vs. Collected Trend**")
        if not df_b_filt.empty:
            # Group by date
            rev_trend = df_b_filt.groupby('date_dt')[['billed', 'paid']].sum().reset_index()
            
            fig_rev = go.Figure()
            fig_rev.add_trace(go.Scatter(x=rev_trend['date_dt'], y=rev_trend['billed'], name='Billed',
                                         line=dict(color='#3b82f6', width=2)))
            fig_rev.add_trace(go.Scatter(x=rev_trend['date_dt'], y=rev_trend['paid'], name='Collected',
                                         line=dict(color='#10b981', width=2), fill='tonexty')) # Fill to show gap
            
            fig_rev.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0), 
                                  legend=dict(orientation="h", y=1.1),
                                  yaxis_title="Amount")
            st.plotly_chart(fig_rev, use_container_width=True)
        else:
            st.info("No billing data for trend analysis.")

    with col_rev2:
        st.markdown("**Revenue Composition (Water vs Sewer)**")
        # Prepare monthly data
        # Water
        water_monthly = df_b_filt.groupby('date_dt')['paid'].sum().reset_index().rename(columns={'paid': 'Water'})
        # Sewer
        sewer_monthly = df_f_filt.groupby('date_dt')['sewer_revenue'].sum().reset_index().rename(columns={'sewer_revenue': 'Sewer'})
        
        # Merge
        if not water_monthly.empty or not sewer_monthly.empty:
            rev_mix = pd.merge(water_monthly, sewer_monthly, on='date_dt', how='outer').fillna(0)
            
            fig_mix = px.bar(rev_mix, x='date_dt', y=['Water', 'Sewer'], 
                             color_discrete_map={'Water': '#3b82f6', 'Sewer': '#f59e0b'})
            fig_mix.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0), 
                                  legend=dict(orientation="h", y=1.1),
                                  yaxis_title="Revenue Collected")
            st.plotly_chart(fig_mix, use_container_width=True)
        else:
            st.info("No revenue data available.")

    # --- Step 3: Cost Control Center ---
    st.markdown("<div class='section-header'>🛡️ Cost Control Center <span style='font-size:14px;color:#6b7280;font-weight:400'>| Opex & Staff</span></div>", unsafe_allow_html=True)
    
    col_cost1, col_cost2 = st.columns(2)
    
    with col_cost1:
        st.markdown("**Opex Trend vs Budget**")
        if not df_f_filt.empty:
            opex_trend = df_f_filt.groupby('date_dt')['opex'].sum().reset_index()
            
            # Simulated Budget Line (e.g., average opex * 0.9 as target)
            avg_opex = opex_trend['opex'].mean()
            budget_limit = avg_opex * 0.95 
            
            fig_opex = go.Figure()
            fig_opex.add_trace(go.Scatter(x=opex_trend['date_dt'], y=opex_trend['opex'], name='Actual Opex',
                                          line=dict(color='#ef4444', width=2)))
            fig_opex.add_trace(go.Scatter(x=opex_trend['date_dt'], y=[budget_limit]*len(opex_trend), name='Budget Limit',
                                          line=dict(color='#6b7280', width=2, dash='dash')))
            
            fig_opex.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0), 
                                   legend=dict(orientation="h", y=1.1),
                                   yaxis_title="Opex")
            st.plotly_chart(fig_opex, use_container_width=True)
            
            # Budget Variance Alert
            last_month_opex = opex_trend.iloc[-1]['opex'] if not opex_trend.empty else 0
            if last_month_opex > budget_limit:
                st.markdown(f"""
                <div class='alert-box'>
                    ⚠️ <strong>Budget Alert:</strong> Last month's Opex ({last_month_opex:,.0f}) exceeded the implied budget limit ({budget_limit:,.0f}).
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No Opex data available.")

    with col_cost2:
        st.markdown("**Staff Cost Ratio (Estimated)**")
        # Since we lack direct staff cost, we'll estimate or show a placeholder gauge
        # Assuming staff cost is roughly 40% of Opex for this demo if data missing
        
        # Create a gauge
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = 42, # Placeholder value
            title = {'text': "Staff Cost % (Est.)"},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "#3b82f6"},
                'steps': [
                    {'range': [0, 30], 'color': "#d1fae5"},
                    {'range': [30, 50], 'color': "#fed7aa"},
                    {'range': [50, 100], 'color': "#fee2e2"}],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 50}}))
        
        fig_gauge.update_layout(height=300, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_gauge, use_container_width=True)
        st.caption("*Note: Staff cost data simulated for demonstration.*")

    # --- Step 3.1: Budget Allocation Breakdown (New) ---
    st.markdown("---")
    st.markdown("**Budget Allocation Breakdown**")
    
    if not df_f_filt.empty:
        # Simulate breakdown based on Total Opex since we lack granular cost data
        # Typical Utility Breakdown: Staff (40%), Energy (30%), Maintenance (15%), Chemicals (10%), Other (5%)
        total_opex_val = df_f_filt['opex'].sum()
        
        if total_opex_val > 0:
            alloc_data = pd.DataFrame({
                'Category': ['Staff', 'Energy', 'Maintenance', 'Chemicals', 'Other'],
                'Percentage': [0.40, 0.30, 0.15, 0.10, 0.05]
            })
            alloc_data['Amount'] = alloc_data['Percentage'] * total_opex_val
            
            fig_pie = px.pie(alloc_data, values='Amount', names='Category', 
                             title='Opex Breakdown (Estimated Model)',
                             color_discrete_sequence=px.colors.qualitative.Set3,
                             hole=0.4)
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_pie, use_container_width=True)
            
            # Overlay "No Data" Alert with Blur Effect
            st.markdown("""
            <div style="
                margin-top: -360px;
                height: 360px; 
                width: 100%; 
                position: relative; 
                z-index: 10; 
                backdrop-filter: blur(5px);
                -webkit-backdrop-filter: blur(5px);
                background-color: rgba(255, 255, 255, 0.4);
                display: flex; 
                justify-content: center; 
                align-items: center;
            ">
                <div style="
                    background: white; 
                    padding: 20px 30px; 
                    border-radius: 8px; 
                    border: 1px solid #e5e7eb; 
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); 
                    text-align: center;
                ">
                    <div style="font-size: 20px; margin-bottom: 8px;">⚠️</div>
                    <div style="font-size: 16px; font-weight: 600; color: #1f2937; margin-bottom: 4px;">No Data Available</div>
                    <div style="font-size: 12px; color: #6b7280;">Granular expense breakdown is missing.</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("No Opex data to visualize breakdown.")
    else:
        st.info("No Financial data available.")

    # --- Step 4: "Lost Money" (NRW Financials) ---
    st.markdown("<div class='section-header'>💧 The Cost of Inefficiency <span style='font-size:14px;color:#6b7280;font-weight:400'>| NRW Financial Impact</span></div>", unsafe_allow_html=True)
    
    # Calculation
    total_consumption = df_b_filt['consumption_m3'].sum() if not df_b_filt.empty else 0
    # Production already summed as total_production
    
    nrw_vol = total_production - total_consumption
    nrw_pct = (nrw_vol / total_production * 100) if total_production > 0 else 0
    
    # Avg Tariff
    avg_tariff = (total_billed_water / total_consumption) if total_consumption > 0 else 0
    
    lost_revenue = nrw_vol * avg_tariff
    
    col_nrw1, col_nrw2, col_nrw3 = st.columns(3)
    
    col_nrw1.metric("Physical Water Loss", f"{nrw_vol:,.0f} m³", f"{nrw_pct:.1f}% of Prod", delta_color="inverse")
    col_nrw2.metric("Average Tariff", f"${avg_tariff:.2f}", "per m³")
    col_nrw3.metric("Commercial Value Lost", f"${lost_revenue:,.0f}", "Potential Revenue", delta_color="inverse")

    # --- Additional: Receivables Management (Debt Aging & Top Debtors) ---
    st.markdown("<div class='section-header'>📋 Receivables Management <span style='font-size:14px;color:#6b7280;font-weight:400'>| Aging & Action List</span></div>", unsafe_allow_html=True)
    
    if not df_b_filt.empty:
        # --- Debt Aging Analysis ---
        col_age, col_list = st.columns([1, 1])
        
        with col_age:
            st.markdown("**Debt Aging Analysis**")
            # Calculate Outstanding
            df_debt = df_b_filt.copy()
            df_debt['outstanding'] = df_debt['billed'] - df_debt['paid']
            df_debt = df_debt[df_debt['outstanding'] > 0] # Only unpaid
            
            if not df_debt.empty:
                # Determine reference date (Max date in selection or dataset)
                ref_date = df_debt['date_dt'].max()
                
                # Calculate Days Overdue
                df_debt['days_overdue'] = (ref_date - df_debt['date_dt']).dt.days
                
                # Binning
                bins = [0, 30, 60, 90, 9999]
                labels = ['0-30 Days', '31-60 Days', '61-90 Days', '90+ Days']
                df_debt['aging_bucket'] = pd.cut(df_debt['days_overdue'], bins=bins, labels=labels, right=False)
                
                # Aggregate
                aging_summary = df_debt.groupby('aging_bucket', observed=False)['outstanding'].sum().reset_index()
                
                # Chart
                fig_aging = px.bar(aging_summary, x='aging_bucket', y='outstanding',
                                   title="Outstanding Debt by Age",
                                   labels={'outstanding': 'Amount ($)', 'aging_bucket': 'Age Category'},
                                   color='aging_bucket',
                                   color_discrete_sequence=px.colors.sequential.Reds_r)
                
                fig_aging.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0), showlegend=False)
                st.plotly_chart(fig_aging, use_container_width=True)
            else:
                st.success("No outstanding debt found in selected period.")

        with col_list:
            st.markdown("**Top Debtors Action List**")
            # Group by customer
            cust_debt = df_b_filt.groupby('customer_id')[['billed', 'paid']].sum().reset_index()
            cust_debt['Outstanding'] = cust_debt['billed'] - cust_debt['paid']
            
            top_debtors = cust_debt.sort_values('Outstanding', ascending=False).head(10)
            
            st.dataframe(
                top_debtors,
                column_config={
                    "customer_id": "Customer ID",
                    "billed": st.column_config.NumberColumn("Total Billed", format="$%d"),
                    "paid": st.column_config.NumberColumn("Total Paid", format="$%d"),
                    "Outstanding": st.column_config.NumberColumn("Outstanding Debt", format="$%d"),
                },
                hide_index=True,
                use_container_width=True,
                height=350
            )
    else:
        st.info("No customer data available.")