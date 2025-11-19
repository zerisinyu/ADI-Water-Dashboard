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
                <div style='background:#10b981;padding:12px;border-radius:8px'>
                    <span style='color:white;font-size:20px'>📈</span>
                </div>
                <span class='status-badge status-good'>good</span>
            </div>
            <div style='color:#6b7280;font-size:12px;margin-bottom:4px'>Collection Rate</div>
            <div style='font-size:24px;font-weight:bold;margin-bottom:4px'>{}%</div>
            <div style='font-size:14px;color:#374151'>${:,.0f}K</div>
            <div style='font-size:11px;color:#9ca3af;margin-top:4px'>of ${:,.0f}K</div>
        </div>
        """.format(
            data['billing']['efficiency'],
            data['billing']['collected'] / 1000,
            data['billing']['totalBilled'] / 1000
        ), unsafe_allow_html=True)

    with col4:
        st.markdown("""
        <div class='metric-card'>
            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:12px'>
                <div style='background:#ef4444;padding:12px;border-radius:8px'>
                    <span style='color:white;font-size:20px'>⚠️</span>
                </div>
                <span class='status-badge status-critical'>critical</span>
            </div>
            <div style='color:#6b7280;font-size:12px;margin-bottom:4px'>Outstanding Debt</div>
            <div style='font-size:24px;font-weight:bold;margin-bottom:4px'>${:,.0f}K</div>
            <div style='font-size:14px;color:#374151'>${:,.0f}K</div>
            <div style='font-size:11px;color:#9ca3af;margin-top:4px'>Current unpaid bills</div>
        </div>
        """.format(
            data['debt']['totalDebt'] / 1000,
            data['debt']['outstandingBills'] / 1000
        ), unsafe_allow_html=True)

    st.markdown("---")

    # Charts section
    row1_col1, row1_col2 = st.columns(2)

    # Budget Allocation Pie Chart
    with row1_col1:
        st.markdown("<div class='panel'><h3>Budget Allocation Breakdown</h3>", unsafe_allow_html=True)
        
        budget_data = pd.DataFrame([
            {'category': 'Staff Costs', 'value': 21.4, 'amount': 450000},
            {'category': 'Operations', 'value': 35.2, 'amount': 739200},
            {'category': 'Maintenance', 'value': 18.5, 'amount': 388500},
            {'category': 'Infrastructure', 'value': 15.3, 'amount': 321300},
            {'category': 'Other', 'value': 9.6, 'amount': 201600}
        ])
        
        colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']
        
        fig1 = go.Figure(data=[go.Pie(
            labels=budget_data['category'],
            values=budget_data['value'],
            marker=dict(colors=colors),
            textinfo='label+percent',
            textposition='outside',
            hovertemplate='<b>%{label}</b><br>%{value}% ($%{customdata}K)<extra></extra>',
            customdata=budget_data['amount'] / 1000
        )])
        
        fig1.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            height=350,
            showlegend=False
        )
        
        st.plotly_chart(fig1, use_container_width=True, config={'displayModeBar': False})
        
        st.markdown("""
        <div style='border-top:1px solid #e5e7eb;padding-top:12px;margin-top:12px'>
            <div style='display:flex;justify-content:space-between;font-size:13px'>
                <span style='color:#6b7280'>Staff Cost Highlight:</span>
                <span style='font-weight:600;color:#3b82f6'>21.4% - Within Acceptable Range</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # NRW Trend Line Chart
    with row1_col2:
        st.markdown("<div class='panel'><h3>Non-Revenue Water Trend</h3>", unsafe_allow_html=True)
        
        nrw_data = pd.DataFrame([
            {'month': 'Jan', 'nrw': 34, 'target': 25},
            {'month': 'Feb', 'nrw': 33, 'target': 25},
            {'month': 'Mar', 'nrw': 35, 'target': 25},
            {'month': 'Apr', 'nrw': 32, 'target': 25},
            {'month': 'May', 'nrw': 31, 'target': 25},
            {'month': 'Jun', 'nrw': 32, 'target': 25}
        ])
        
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=nrw_data['month'], y=nrw_data['nrw'],
            mode='lines+markers',
            name='Actual NRW',
            line=dict(color='#f59e0b', width=3),
            marker=dict(size=8)
        ))
        fig2.add_trace(go.Scatter(
            x=nrw_data['month'], y=nrw_data['target'],
            mode='lines',
            name='Target',
            line=dict(color='#10b981', width=2, dash='dash')
        ))
        
        fig2.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            height=350,
            yaxis_title='NRW %',
            xaxis_title='',
            hovermode='x unified'
        )
        
        st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})
        
        st.markdown("""
        <div style='border-top:1px solid #e5e7eb;padding-top:12px;margin-top:12px'>
            <div style='display:flex;justify-content:space-between;font-size:13px'>
                <span style='color:#6b7280'>Current Status:</span>
                <span style='font-weight:600;color:#f59e0b'>32% - Above 25% Target</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Second row of charts
    row2_col1, row2_col2 = st.columns(2)

    # Debt Aging Bar Chart
    with row2_col1:
        st.markdown("<div class='panel'><h3>Debt Aging Analysis</h3>", unsafe_allow_html=True)
        
        debt_data = pd.DataFrame([
            {'category': '0-30 days', 'amount': 120000},
            {'category': '31-60 days', 'amount': 85000},
            {'category': '61-90 days', 'amount': 65000},
            {'category': '90+ days', 'amount': 50000}
        ])
        
        fig3 = go.Figure(data=[go.Bar(
            x=debt_data['category'],
            y=debt_data['amount'],
            marker_color='#ef4444',
            text=debt_data['amount'].apply(lambda x: f'${x/1000:.0f}K'),
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>$%{y:,.0f}<extra></extra>'
        )])
        
        fig3.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            height=350,
            yaxis_title='Amount ($)',
            xaxis_title='',
            showlegend=False
        )
        
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

    # Billing & Collection Summary
    with row2_col2:
        st.markdown("<div class='panel'><h3>Billing & Collection Summary</h3>", unsafe_allow_html=True)
        
        st.markdown("""
        <div style='border-bottom:1px solid #e5e7eb;padding-bottom:16px;margin-bottom:16px'>
            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>
                <span style='font-size:13px;color:#6b7280'>Total Billed</span>
                <span style='font-size:18px;font-weight:600'>$1,850K</span>
            </div>
            <div style='width:100%;height:8px;background:#e5e7eb;border-radius:4px'>
                <div style='width:100%;height:8px;background:#3b82f6;border-radius:4px'></div>
            </div>
        </div>
        
        <div style='border-bottom:1px solid #e5e7eb;padding-bottom:16px;margin-bottom:16px'>
            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>
                <span style='font-size:13px;color:#6b7280'>Collected</span>
                <span style='font-size:18px;font-weight:600;color:#10b981'>$1,443K</span>
            </div>
            <div style='width:100%;height:8px;background:#e5e7eb;border-radius:4px'>
                <div style='width:78%;height:8px;background:#10b981;border-radius:4px'></div>
            </div>
            <div style='font-size:11px;color:#9ca3af;margin-top:4px'>78% Collection Rate</div>
        </div>
        
        <div style='border-bottom:1px solid #e5e7eb;padding-bottom:16px'>
            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>
                <span style='font-size:13px;color:#6b7280'>Outstanding</span>
                <span style='font-size:18px;font-weight:600;color:#f59e0b'>$407K</span>
            </div>
            <div style='width:100%;height:8px;background:#e5e7eb;border-radius:4px'>
                <div style='width:22%;height:8px;background:#f59e0b;border-radius:4px'></div>
            </div>
            <div style='font-size:11px;color:#9ca3af;margin-top:4px'>22% Uncollected</div>
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


# ----------------------------- Additional Scenes -----------------------------

def scene_production():
    st.markdown("<div class='panel'><h3>Sanitation & Reuse Chain</h3>", unsafe_allow_html=True)
    sc = _load_json("sanitation_chain.json") or {
        "month": "2025-03", "collected_mld": 68, "treated_mld": 43, "ww_reused_mld": 12,
        "fs_treated_tpd": 120, "fs_reused_tpd": 34, "households_non_sewered": 48000, "households_emptied": 16400,
        "public_toilets_functional_pct": 74,
    }
    c1 = (sc["treated_mld"] / max(1, sc["collected_mld"])) * 100
    c2 = (sc["ww_reused_mld"] / max(1, sc["collected_mld"])) * 100
    c3 = (sc["households_emptied"] / max(1, sc["households_non_sewered"])) * 100
    c4 = (sc["fs_reused_tpd"] / max(1, sc["fs_treated_tpd"])) * 100
    tiles = st.columns(5)
    tiles[0].metric("Collected→Treated %", f"{c1:.1f}")
    tiles[1].metric("WW reused / supplied %", f"{c2:.1f}")
    tiles[2].metric("FS emptied %", f"{c3:.1f}")
    tiles[3].metric("Treated FS reused %", f"{c4:.1f}")
    tiles[4].metric("Public toilets functional %", f"{sc['public_toilets_functional_pct']}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><h3>Flows</h3>", unsafe_allow_html=True)
    stages = ["Collected", "Treated", "Reused"]
    ww_vals = [sc["collected_mld"], sc["treated_mld"], sc["ww_reused_mld"]]
    fs_vals = [sc["households_non_sewered"], sc["households_emptied"], round(sc["households_non_sewered"] * (c4/100))]
    df_flow = pd.DataFrame({"stage": stages*2, "value": ww_vals+fs_vals, "stream": ["Wastewater"]*3 + ["Faecal Sludge"]*3})
    fig = px.bar(df_flow, x="stage", y="value", color="stream", barmode="group")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key="sanitation_flows")
    st.markdown("</div>", unsafe_allow_html=True)