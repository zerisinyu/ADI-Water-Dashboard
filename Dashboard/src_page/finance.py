import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def scene_finance():
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
    </style>
    """, unsafe_allow_html=True)

    # Financial data structure
    financial_data = {
        "uganda": {
            "staffCostAllocation": {
                "staffCosts": 450000,
                "totalBudget": 2100000,
                "percentage": 21.4
            },
            "nrw": {
                "percentage": 32,
                "volumeLost": 2840000,
                "estimatedRevenueLoss": 890000
            },
            "debt": {
                "totalDebt": 1250000,
                "collectionRate": 78,
                "outstandingBills": 320000
            },
            "billing": {
                "totalBilled": 1850000,
                "collected": 1443000,
                "efficiency": 78
            }
        }
    }

    # Production summary
    production_summary = {
        '2024': {
            'victoria': {'total': 2645143, 'avgDaily': 7234},
            'kyoga': {'total': 2583427, 'avgDaily': 7066}
        },
        '2023': {
            'victoria': {'total': 2589428, 'avgDaily': 7093},
            'kyoga': {'total': 2673284, 'avgDaily': 7324}
        }
    }

    # Header
    st.title("Water Utility Financial Dashboard - Uganda")
    st.markdown("**Financial Plan & Billing KPIs | Sources: Victoria & Kyoga**")

    # Warning banner
    st.warning("⚠️ **Note:** Financial data shown is placeholder structure. Actual production data available: 2020-2024. Awaiting Lesotho billing data.")

    # Year selector
    selected_year = st.selectbox("Select Year", ['2024', '2023', '2022'], index=0)

    st.markdown("---")

    # KPI Cards
    data = financial_data['uganda']
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("""
        <div class='metric-card'>
            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:12px'>
                <div style='background:#3b82f6;padding:12px;border-radius:8px'>
                    <span style='color:white;font-size:20px'>💰</span>
                </div>
                <span class='status-badge status-good'>good</span>
            </div>
            <div style='color:#6b7280;font-size:12px;margin-bottom:4px'>Staff Cost Allocation</div>
            <div style='font-size:24px;font-weight:bold;margin-bottom:4px'>{:.1f}%</div>
            <div style='font-size:14px;color:#374151'>${:,.0f}K</div>
            <div style='font-size:11px;color:#9ca3af;margin-top:4px'>of ${:,.0f}K</div>
        </div>
        """.format(
            data['staffCostAllocation']['percentage'],
            data['staffCostAllocation']['staffCosts'] / 1000,
            data['staffCostAllocation']['totalBudget'] / 1000
        ), unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class='metric-card'>
            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:12px'>
                <div style='background:#f59e0b;padding:12px;border-radius:8px'>
                    <span style='color:white;font-size:20px'>💧</span>
                </div>
                <span class='status-badge status-warning'>warning</span>
            </div>
            <div style='color:#6b7280;font-size:12px;margin-bottom:4px'>Non-Revenue Water</div>
            <div style='font-size:24px;font-weight:bold;margin-bottom:4px'>{}%</div>
            <div style='font-size:14px;color:#374151'>{:.2f}M m³</div>
            <div style='font-size:11px;color:#9ca3af;margin-top:4px'>Loss: ${:,.0f}K</div>
        </div>
        """.format(
            data['nrw']['percentage'],
            data['nrw']['volumeLost'] / 1000000,
            data['nrw']['estimatedRevenueLoss'] / 1000
        ), unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class='metric-card'>
            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:12px'>
                <div style='background:#ef4444;padding:12px;border-radius:8px'>
                    <span style='color:white;font-size:20px'>📉</span>
                </div>
                <span class='status-badge status-critical'>critical</span>
            </div>
            <div style='color:#6b7280;font-size:12px;margin-bottom:4px'>Debt Portfolio</div>
            <div style='font-size:24px;font-weight:bold;margin-bottom:4px'>${:,.0f}K</div>
            <div style='font-size:14px;color:#374151'>Collection Rate: {}%</div>
            <div style='font-size:11px;color:#9ca3af;margin-top:4px'>Outstanding Bills: ${:,.0f}K</div>
        </div>
        """.format(
            data['debt']['totalDebt'] / 1000,
            data['debt']['collectionRate'],
            data['debt']['outstandingBills'] / 1000
        ), unsafe_allow_html=True)

    with col4:
        st.markdown("""
        <div class='metric-card'>
            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:12px'>
                <div style='background:#10b981;padding:12px;border-radius:8px'>
                    <span style='color:white;font-size:20px'>📊</span>
                </div>
                <span class='status-badge status-good'>good</span>
            </div>
            <div style='color:#6b7280;font-size:12px;margin-bottom:4px'>Billing Efficiency</div>
            <div style='font-size:24px;font-weight:bold;margin-bottom:4px'>{}%</div>
            <div style='font-size:14px;color:#374151'>Collected: ${:,.0f}K</div>
            <div style='font-size:11px;color:#9ca3af;margin-top:4px'>Total Billed: ${:,.0f}K</div>
        </div>
        """.format(
            data['billing']['efficiency'],
            data['billing']['collected'] / 1000,
            data['billing']['totalBilled'] / 1000
        ), unsafe_allow_html=True)

    st.markdown("---")

    # Production Summary Cards
    st.markdown("<div class='panel'><h3>Production Summary</h3>", unsafe_allow_html=True)
    pcol1, pcol2 = st.columns(2)
    with pcol1:
        st.markdown("""
        <div style='background:linear-gradient(135deg, #eff6ff, #dbeafe);padding:16px;border-radius:12px;border:1px solid #bfdbfe'>
            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:6px'>
                <span style='font:600 14px Inter,sans-serif;color:#1e40af'>Victoria Production</span>
                <span style='background:#1e40af;color:white;padding:2px 8px;border-radius:999px;font:700 10px Inter,sans-serif'>2024</span>
            </div>
            <div style='display:flex;gap:24px'>
                <div>
                    <div style='font:600 22px Inter,sans-serif;color:#0f172a'>2.65M m³</div>
                    <div style='font:400 11px Inter,sans-serif;color:#64748b'>Total</div>
                </div>
                <div>
                    <div style='font:600 22px Inter,sans-serif;color:#0f172a'>7,234</div>
                    <div style='font:400 11px Inter,sans-serif;color:#64748b'>Avg Daily</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with pcol2:
        st.markdown("""
        <div style='background:linear-gradient(135deg, #ecfeff, #cffafe);padding:16px;border-radius:12px;border:1px solid #a5f3fc'>
            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:6px'>
                <span style='font:600 14px Inter,sans-serif;color:#115e59'>Kyoga Production</span>
                <span style='background:#115e59;color:white;padding:2px 8px;border-radius:999px;font:700 10px Inter,sans-serif'>2024</span>
            </div>
            <div style='display:flex;gap:24px'>
                <div>
                    <div style='font:600 22px Inter,sans-serif;color:#0f172a'>2.58M m³</div>
                    <div style='font:400 11px Inter,sans-serif;color:#64748b'>Total</div>
                </div>
                <div>
                    <div style='font:600 22px Inter,sans-serif;color:#0f172a'>7,066</div>
                    <div style='font:400 11px Inter,sans-serif;color:#64748b'>Avg Daily</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Two-column layout for charts
    row2_col1, row2_col2 = st.columns([2, 1])

    # NRW Analysis
    with row2_col1:
        st.markdown("<div class='panel'><h3>Non-Revenue Water Analysis</h3>", unsafe_allow_html=True)
        df_nrw = pd.DataFrame({
            'Category': ['NRW %', 'Volume Lost (m³)', 'Revenue Loss ($)'],
            'Value': [data['nrw']['percentage'], data['nrw']['volumeLost'], data['nrw']['estimatedRevenueLoss']]
        })
        fig1 = go.Figure()
        fig1.add_trace(go.Bar(x=df_nrw['Category'], y=df_nrw['Value'], marker_color=['#f59e0b', '#60a5fa', '#ef4444']))
        fig1.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=350, showlegend=False,
                           yaxis_title='Value', xaxis_title='')
        st.plotly_chart(fig1, use_container_width=True, config={'displayModeBar': False})
        st.markdown("</div>", unsafe_allow_html=True)

    # Debt & Billing Details
    with row2_col2:
        st.markdown("<div class='panel'><h3>Debt & Collection Details</h3>", unsafe_allow_html=True)
        debt_data = pd.DataFrame({
            'category': ['Total Debt', 'Collections', 'Outstanding'],
            'amount': [data['debt']['totalDebt'], data['billing']['collected'], data['debt']['outstandingBills']]
        })
        fig3 = go.Figure([go.Bar(
            x=debt_data['category'],
            y=debt_data['amount'],
            marker_color='#ef4444',
            text=debt_data['amount'].apply(lambda x: f'${x/1000:.0f}K'),
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>$%{y:,.0f}<extra></extra>'
        )])
        fig3.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=350, yaxis_title='Amount ($)', xaxis_title='', showlegend=False)
        st.plotly_chart(fig3, use_container_width=True, config={'displayModeBar': False})
        st.markdown("""
        <div style='border-top:1px solid #e5e7eb;padding-top:12px;margin-top:12px'>
            <div style='display:flex;justify-content:space-between;font-size:13px;margin-bottom:8px'>
                <span style='color:#6b7280'>Total Outstanding:</span>
                <span style='font-weight:600;color:#ef4444'>$320K</span>
            </div>
            <div style='display:flex;justify-content:space-between;font-size:13px'>
                <span style='color:#6b7280'>Over 90 days:</span>
                <span style='font-weight:600;color:#ef4444'>$50K (15.6%)</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")

    # Key Financial Highlights
    st.markdown("<div class='panel'><h3>Key Financial Highlights</h3>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div style='border-left:4px solid #3b82f6;padding-left:16px'>
            <h4 style='font-size:16px;font-weight:600;margin-bottom:12px'>Staff Cost Allocation</h4>
            <ul style='font-size:13px;color:#6b7280;line-height:1.8;list-style:none;padding:0'>
                <li>• 21.4% of total budget allocated to staff</li>
                <li>• $450K annual staff costs</li>
                <li>• Within industry benchmark (20-25%)</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div style='border-left:4px solid #f59e0b;padding-left:16px'>
            <h4 style='font-size:16px;font-weight:600;margin-bottom:12px'>Non-Revenue Water</h4>
            <ul style='font-size:13px;color:#6b7280;line-height:1.8;list-style:none;padding:0'>
                <li>• Current NRW at 32% (Target: 25%)</li>
                <li>• 2.84M m³ water lost annually</li>
                <li>• Estimated revenue loss: $890K</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div style='border-left:4px solid #ef4444;padding-left:16px'>
            <h4 style='font-size:16px;font-weight:600;margin-bottom:12px'>Debt Management</h4>
            <ul style='font-size:13px;color:#6b7280;line-height:1.8;list-style:none;padding:0'>
                <li>• 78% collection efficiency</li>
                <li>• $320K in outstanding bills</li>
                <li>• 15.6% debt over 90 days old</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
