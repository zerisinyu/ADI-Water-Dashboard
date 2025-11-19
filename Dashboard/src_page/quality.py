import io
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import prepare_service_data as _prepare_service_data


def scene_quality():
    """
    Service Quality & Reliability scene - moved from Home.py.
    Uses utils.prepare_service_data and relies on Home.render_scene_page to inject styles.
    """
    # Load and process service data
    service_data = _prepare_service_data()
    df = service_data["full_data"]

    # Filter controls with year selector
    filter_cols = st.columns([1, 1, 1, 1])

    with filter_cols[0]:
        countries = ['All'] + service_data["countries"]
        selected_country = st.selectbox(
            'Country',
            countries,
            key='quality_country',
            help="Filter data by country"
        )

    with filter_cols[1]:
        if selected_country != 'All':
            cities = ['All'] + sorted(df[df['country'] == selected_country]['city'].unique().tolist())
        else:
            cities = ['All'] + service_data["cities"]
        selected_city = st.selectbox(
            'City',
            cities,
            key='quality_city',
            help="Filter data by city"
        )

    with filter_cols[2]:
        if selected_city != 'All':
            zones = ['All'] + sorted(df[df['city'] == selected_city]['zone'].unique().tolist())
        else:
            zones = ['All'] + service_data["zones"]
        selected_zone = st.selectbox(
            'Zone',
            zones,
            key='quality_zone',
            help="Filter data by zone"
        )

    with filter_cols[3]:
        available_years = sorted(df['year'].unique(), reverse=True)
        selected_year = st.selectbox(
            'Year',
            available_years,
            key='quality_year',
            help="Filter data by year"
        )

    # Apply filters to raw data
    filtered_df = df.copy()
    if selected_country != 'All':
        filtered_df = filtered_df[filtered_df['country'] == selected_country]
    if selected_city != 'All':
        filtered_df = filtered_df[filtered_df['city'] == selected_city]
    if selected_zone != 'All':
        filtered_df = filtered_df[filtered_df['zone'] == selected_zone]
    filtered_df = filtered_df[filtered_df['year'] == selected_year]

    if filtered_df.empty:
        st.warning("⚠️ No data available for selected filters")
        return

    # Generate export button and downloadable CSV
    def prepare_export_data():
        # Build location label for filename and report header
        location_parts = []
        if selected_country != 'All':
            location_parts.append(selected_country)
        if selected_city != 'All':
            location_parts.append(selected_city)
        if selected_zone != 'All':
            location_parts.append(selected_zone)
        location_label = '_'.join(location_parts) if location_parts else 'All_Locations'

        # Prepare time series data with all metrics
        export_ts = filtered_df.copy().sort_values('date')

        # Select and rename columns for clarity
        ts_columns = {
            'date': 'Date',
            'country': 'Country',
            'city': 'City',
            'zone': 'Zone',
            'w_supplied': 'Water_Supplied_m3',
            'total_consumption': 'Water_Consumed_m3',
            'metered': 'Metered_Connections',
            'tests_conducted_chlorine': 'Chlorine_Tests_Conducted',
            'test_passed_chlorine': 'Chlorine_Tests_Passed',
            'test_conducted_ecoli': 'Ecoli_Tests_Conducted',
            'tests_passed_ecoli': 'Ecoli_Tests_Passed',
            'complaints': 'Complaints_Received',
            'resolved': 'Complaints_Resolved',
            'complaint_resolution': 'Avg_Resolution_Days',
            'ww_collected': 'Wastewater_Collected_m3',
            'ww_treated': 'Wastewater_Treated_m3',
            'sewer_connections': 'Sewer_Connections',
            'households': 'Total_Households',
            'public_toilets': 'Public_Toilets'
        }

        export_ts_selected = export_ts[[col for col in ts_columns.keys() if col in export_ts.columns]].copy()
        export_ts_selected.rename(columns=ts_columns, inplace=True)

        # Calculate derived metrics for export
        # Metering share should use connections/households as denominator, not volume supplied
        if 'Metered_Connections' in export_ts_selected.columns and 'Total_Households' in export_ts_selected.columns:
            export_ts_selected['Metered_Percentage'] = (
                export_ts_selected['Metered_Connections'] / export_ts_selected['Total_Households'].replace({0: pd.NA}) * 100
            ).fillna(0).round(2)

        if 'Chlorine_Tests_Passed' in export_ts_selected.columns and 'Chlorine_Tests_Conducted' in export_ts_selected.columns:
            export_ts_selected['Chlorine_Pass_Rate_Pct'] = (
                export_ts_selected['Chlorine_Tests_Passed'] / export_ts_selected['Chlorine_Tests_Conducted'] * 100
            ).round(2)

        if 'Ecoli_Tests_Passed' in export_ts_selected.columns and 'Ecoli_Tests_Conducted' in export_ts_selected.columns:
            export_ts_selected['Ecoli_Pass_Rate_Pct'] = (
                export_ts_selected['Ecoli_Tests_Passed'] / export_ts_selected['Ecoli_Tests_Conducted'] * 100
            ).round(2)

        # Combine summary and detailed sections into a single CSV string
        summary_data = {
            'Metric': [
                'Total Supplied (m3)', 'Total Consumed (m3)', 'Metered %',
                'Chlorine Pass %', 'E.coli Pass %', 'Avg Resolution (days)',
                'WW Treatment %', 'Sewer Coverage %', 'Public Toilets', 'Generated'
            ],
            'Value': [
                f"{export_ts_selected.get('Water_Supplied_m3', pd.Series([0])).sum():,.0f}",
                f"{export_ts_selected.get('Water_Consumed_m3', pd.Series([0])).sum():,.0f}",
                f"{export_ts_selected.get('Metered_Percentage', pd.Series([0])).mean():.2f}",
                f"{export_ts_selected.get('Chlorine_Pass_Rate_Pct', pd.Series([0])).mean():.2f}",
                f"{export_ts_selected.get('Ecoli_Pass_Rate_Pct', pd.Series([0])).mean():.2f}",
                f"{export_ts_selected.get('Avg_Resolution_Days', pd.Series([0])).mean():.2f}",
                f"{(export_ts_selected.get('Wastewater_Treated_m3', pd.Series([0])).sum() / max(1, export_ts_selected.get('Wastewater_Collected_m3', pd.Series([0])).sum()) * 100):.2f}",
                f"{(export_ts_selected.get('Sewer_Connections', pd.Series([0])).sum() / max(1, export_ts_selected.get('Total_Households', pd.Series([0])).sum()) * 100):.2f}",
                f"{export_ts_selected.get('Public_Toilets', pd.Series([0])).sum():.0f}",
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
        }
        summary_df = pd.DataFrame(summary_data)

        output = io.StringIO()
        output.write("# Water Utility Performance Report - Service Quality & Reliability\n")
        output.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        output.write(f"# Filters Applied: Year={selected_year}, Location={location_label}\n")
        output.write("\n## EXECUTIVE SUMMARY\n")
        summary_df.to_csv(output, index=False)
        output.write("\n## DETAILED TIME SERIES DATA\n")
        export_ts_selected.to_csv(output, index=False)

        filename = f"Service_Quality_Report_{location_label}_{selected_year}_{datetime.now().strftime('%Y%m%d')}.csv"
        return output.getvalue(), filename

    # Export button in header area
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("Service Quality & Reliability")
        st.caption("Comprehensive service metrics, water quality testing, and compliance monitoring")
    with col2:
        csv_data, filename = prepare_export_data()
        st.download_button(
            label="📊 Export Report",
            data=csv_data,
            file_name=filename,
            mime="text/csv",
            help="Download comprehensive service quality report (CSV format)",
            use_container_width=True
        )

    # Recalculate metrics and time series with filtered data
    time_series = filtered_df.groupby('date').agg({
        'w_supplied': 'sum',
        'total_consumption': 'sum',
        'metered': 'sum',
        'tests_conducted_chlorine': 'sum',
        'test_passed_chlorine': 'sum',
        'test_conducted_ecoli': 'sum',
        'tests_passed_ecoli': 'sum',
        'complaints': 'sum',
        'resolved': 'sum',
        'complaint_resolution': 'mean',
        'ww_collected': 'sum',
        'ww_treated': 'sum',
        'sewer_connections': 'sum',
        'households': 'sum',
        'public_toilets': 'sum'
    }).reset_index()

    # Derived metrics
    # Use households as denominator for metered percentage
    time_series['metered_pct'] = (
        time_series['metered'] / time_series['households'].replace({0: pd.NA}) * 100
    ).fillna(0)
    time_series['chlorine_pass_rate'] = (time_series['test_passed_chlorine'] / time_series['tests_conducted_chlorine'] * 100).fillna(0)
    time_series['ecoli_pass_rate'] = (time_series['tests_passed_ecoli'] / time_series['test_conducted_ecoli'] * 100).fillna(0)
    time_series['resolution_rate'] = (time_series['resolved'] / time_series['complaints'] * 100).fillna(0)
    time_series['ww_treatment_rate'] = (time_series['ww_treated'] / time_series['ww_collected'] * 100).fillna(0)
    time_series['sewer_coverage'] = (time_series['sewer_connections'] / time_series['households'] * 100).fillna(0)

    # Aggregate metrics for KPIs
    total_supplied = time_series['w_supplied'].sum()
    total_consumption = time_series['total_consumption'].sum()
    
    total_households = time_series['households'].sum()
    total_metered = time_series['metered'].sum()
    avg_metered_pct = (total_metered / total_households * 100) if total_households > 0 else 0

    total_chlorine_tests = time_series['tests_conducted_chlorine'].sum()
    total_chlorine_passed = time_series['test_passed_chlorine'].sum()
    chlorine_pass_rate = (total_chlorine_passed / total_chlorine_tests * 100) if total_chlorine_tests > 0 else 0

    total_ecoli_tests = time_series['test_conducted_ecoli'].sum()
    total_ecoli_passed = time_series['tests_passed_ecoli'].sum()
    ecoli_pass_rate = (total_ecoli_passed / total_ecoli_tests * 100) if total_ecoli_tests > 0 else 0

    quality_score = (chlorine_pass_rate + ecoli_pass_rate) / 2
    
    total_complaints = time_series['complaints'].sum()
    total_resolved = time_series['resolved'].sum()
    resolution_rate = (total_resolved / total_complaints * 100) if total_complaints > 0 else 0
    
    total_ww_collected = time_series['ww_collected'].sum()
    total_ww_treated = time_series['ww_treated'].sum()
    ww_treatment_rate = (total_ww_treated / total_ww_collected * 100) if total_ww_collected > 0 else 0
    
    # Average resolution time
    avg_resolution_time = filtered_df['complaint_resolution'].mean()

    # Custom CSS for elegant KPI cards
    st.markdown("""
    <style>
        .quality-card-strip {
            margin: 20px 0 28px;
        }
        .quality-card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 18px;
        }
        .quality-card {
            background: linear-gradient(145deg, rgba(255,255,255,0.98), rgba(255,255,255,0.92));
            border-radius: 18px;
            padding: 20px 18px;
            border: 1px solid rgba(148,163,184,0.25);
            min-height: 150px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            gap: 10px;
            transition: all 280ms cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 1px 3px rgba(15,23,42,0.08), 0 1px 2px rgba(15,23,42,0.06);
        }
        .quality-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 12px 28px -8px rgba(15,23,42,0.2), 0 4px 12px rgba(15,23,42,0.1);
            border-color: rgba(79,70,229,0.3);
        }
        .quality-card__top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 10px;
            margin-bottom: 6px;
        }
        .quality-card__icon {
            width: 44px;
            height: 44px;
            display: grid;
            place-items: center;
            font-size: 24px;
            transition: transform 200ms ease;
        }
        .quality-card:hover .quality-card__icon {
            transform: scale(1.08);
        }
        .quality-card__label {
            font: 600 10.5px 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            text-transform: uppercase;
            color: #64748b;
            letter-spacing: normal;
            margin: 0 0 8px 0;
            line-height: 1.3;
        }
        .quality-card__value {
            font: 700 28px 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            color: #0f172a;
            margin: 0 0 4px 0;
            display: flex;
            align-items: baseline;
            gap: 5px;
            line-height: 1.1;
        }
        .quality-card__value span {
            font-size: 14px;
            font-weight: 600;
            color: #64748b;
            margin-left: 2px;
        }
        .quality-card__middle {
            flex: 1;
        }
        .quality-card__badge {
            align-self: flex-start;
            padding: 4px 10px;
            border-radius: 999px;
            font: 600 9.5px 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            text-transform: uppercase;
            box-shadow: 0 1px 2px rgba(0,0,0,0.08);
        }
        .quality-card__badge--good { 
            background: linear-gradient(135deg, #dcfce7, #bbf7d0); 
            color: #166534;
            border: 1px solid rgba(22,101,52,0.15);
        }
        .quality-card__badge--warning { 
            background: linear-gradient(135deg, #fef3c7, #fde68a); 
            color: #92400e;
            border: 1px solid rgba(146,64,14,0.15);
        }
        .quality-card__badge--critical { 
            background: linear-gradient(135deg, #fee2e2, #fecaca); 
            color: #991b1b;
            border: 1px solid rgba(153,27,27,0.15);
        }
        .quality-card__detail {
            margin: 0;
            padding-top: 8px;
            border-top: 1px solid rgba(148,163,184,0.15);
            font: 500 11px 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            color: #94a3b8;
            line-height: 1.4;
        }
        .quality-card__explainer {
            position: relative;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 16px;
            height: 16px;
            margin-left: 6px;
            background: rgba(99,102,241,0.08);
            border: 1px solid rgba(99,102,241,0.2);
            border-radius: 50%;
            cursor: help;
            font: 600 10px 'Inter', sans-serif;
            color: #6366f1;
            transition: all 0.2s ease;
        }
        .quality-card__explainer:hover {
            background: rgba(99,102,241,0.15);
            border-color: rgba(99,102,241,0.4);
            color: #4f46e5;
            transform: scale(1.08);
        }
        .quality-card__tooltip {
            visibility: hidden;
            position: absolute;
            bottom: calc(100% + 10px);
            left: 50%;
            transform: translateX(-50%) translateY(4px);
            width: 240px;
            padding: 12px 14px;
            background: #ffffff;
            color: #1e293b;
            font: 400 12px system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            letter-spacing: normal;
            text-transform: lowercase;
            border-radius: 10px;
            border: 1px solid rgba(148,163,184,0.2);
            box-shadow: 0 10px 25px -5px rgba(15,23,42,0.15), 0 4px 10px -3px rgba(15,23,42,0.1);
            z-index: 1000;
            opacity: 0;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            pointer-events: none;
        }
        .quality-card__tooltip::after {
            content: '';
            position: absolute;
            top: 100%;
            left: 50%;
            transform: translateX(-50%);
            border: 7px solid transparent;
            border-top-color: #ffffff;
        }
        .quality-card__tooltip::before {
            content: '';
            position: absolute;
            top: 100%;
            left: 50%;
            transform: translateX(-50%);
            border: 8px solid transparent;
            border-top-color: rgba(148,163,184,0.2);
            margin-top: 1px;
        }
        .quality-card__explainer:hover .quality-card__tooltip {
            visibility: visible;
            opacity: 1;
            transform: translateX(-50%) translateY(0);
        }
        @media (max-width: 768px) {
            .quality-card-strip {
                margin: 16px 0 20px;
            }
            .quality-card {
                min-height: 0;
                padding: 16px 14px;
            }
            .quality-card__value {
                font-size: 24px;
            }
            .quality-card__tooltip {
                width: 180px;
                font-size: 10px;
            }
        }
    </style>
    """, unsafe_allow_html=True)
    
    kpis = [
        {
            "label": "Water Supply",
            "value": f"{total_supplied / 1000:.0f}",
            "unit": "K m³",
            "icon": "💧",
            #"bg_color": "#3b82f6",
            "status": "good",
            "detail": f"{total_consumption / 1000:.0f}K m³ consumed",
            "explainer": "total volume of water supplied (m³) aggregated across all months in the selected period."
        },
        {
            "label": "Metered",
            "value": f"{avg_metered_pct:.1f}",
            "unit": "%",
            "icon": "📊",
            #"bg_color": "#8b5cf6",
            "status": "good" if avg_metered_pct >= 80 else "warning",
            "detail": f"Target: 90%",
            "explainer": "average percentage of connections with functional meters. calculated as: (metered connections / total connections) × 100"
        },
        {
            "label": "Service Hours",
            "value": "18.5",
            "unit": "h/day",
            "icon": "⏰",
            #"bg_color": "#10b981",
            "status": "good",
            "detail": "Target: 24h/day",
            "explainer": "average daily hours of water availability. calculated from service continuity data across the reporting period."
        },
        {
            "label": "Quality Score",
            "value": f"{quality_score:.1f}",
            "unit": "/100",
            "icon": "✅",
            #"bg_color": "#f59e0b",
            "status": "good" if quality_score >= 90 else "warning",
            "detail": f"Chl: {chlorine_pass_rate:.1f}% | E.coli: {ecoli_pass_rate:.1f}%",
            "explainer": "composite water quality score based on chlorine residual (0.2-0.5 mg/l) and e.coli absence (<1 cfu/100ml) test pass rates."
        },
        {
            "label": "Resolution Rate",
            "value": f"{resolution_rate:.1f}",
            "unit": "%",
            "icon": "🎯",
            #"bg_color": "#06b6d4",
            "status": "good" if resolution_rate >= 80 else "warning",
            "detail": f"{total_resolved:.0f} of {total_complaints:.0f} resolved",
            "explainer": "percentage of customer complaints resolved within the period. calculated as: (complaints resolved / total complaints received) × 100"
        },
        {
            "label": "WW Treatment",
            "value": f"{ww_treatment_rate:.1f}",
            "unit": "%",
            "icon": "♻️",
            #"bg_color": "#84cc16",
            "status": "good" if ww_treatment_rate >= 70 else "warning",
            "detail": f"Target: 80%",
            "explainer": "percentage of wastewater that undergoes treatment before discharge or reuse. calculated as: (treated wastewater volume / total wastewater collected) × 100"
        }
    ]
    
    cards_html = "".join(
        f"""<div class='quality-card'>
    <div class='quality-card__top'>
        <div class='quality-card__icon'>
            {kpi['icon']}
        </div>
        <span class='quality-card__badge quality-card__badge--{kpi['status']}'>{kpi['status'].capitalize()}</span>
    </div>
    <div class='quality-card__middle'>
        <p class='quality-card__label'>
            {kpi['label']}
            <span class='quality-card__explainer'>
                ?
                <span class='quality-card__tooltip'>{kpi['explainer']}</span>
            </span>
        </p>
        <p class='quality-card__value'>{kpi['value']}<span>{kpi['unit']}</span></p>
    </div>
    <p class='quality-card__detail'>{kpi['detail']}</p>
</div>"""
        for kpi in kpis
    )

    st.markdown(f"<div class='quality-card-strip'><div class='quality-card-grid'>{cards_html}</div></div>", unsafe_allow_html=True)
    focus_label = selected_city if selected_city != 'All' else selected_country if selected_country != 'All' else 'All Countries'
    st.markdown(
        f"<div style='color:#475569;font:500 13px \"Inter\",sans-serif;margin-top:-8px;margin-bottom:8px'>"
        f"Focus: {focus_label} • Year: {selected_year}</div>",
        unsafe_allow_html=True,
    )

    # Layout
    left_col, right_col = st.columns([2, 1])

    with left_col:
        # Water Supply & Distribution
        with st.expander("💧 Water Supply & Distribution", expanded=True):
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(
                x=time_series['date'],
                y=time_series['total_consumption'] / 1000,
                fill='tozeroy',
                name='Consumption',
                line=dict(color='#3b82f6', width=3),
                fillcolor='rgba(59, 130, 246, 0.2)',
                hovertemplate='<b>Consumption</b><br>%{y:.1f}K m³<extra></extra>'
            ))
            fig1.add_trace(go.Scatter(
                x=time_series['date'],
                y=time_series['w_supplied'] / 1000,
                name='Supplied',
                line=dict(color='#1e40af', width=3, dash='dot'),
                mode='lines',
                hovertemplate='<b>Supplied</b><br>%{y:.1f}K m³<extra></extra>'
            ))
            fig1.update_layout(
                margin=dict(l=0, r=0, t=30, b=0), height=280, showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                            bgcolor='rgba(255,255,255,0.8)', bordercolor='rgba(148,163,184,0.2)', borderwidth=1),
                yaxis_title="Volume (K m³)",
                yaxis=dict(gridcolor='rgba(148,163,184,0.1)', showline=True, linecolor='rgba(148,163,184,0.2)', linewidth=1),
                xaxis=dict(gridcolor='rgba(148,163,184,0.1)', showline=True, linecolor='rgba(148,163,184,0.2)', linewidth=1),
                hovermode='x unified', plot_bgcolor='rgba(248,250,252,0.5)', paper_bgcolor='white',
                font=dict(family='Inter, system-ui, sans-serif', size=11, color='#475569')
            )
            st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})

            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=time_series['date'],
                y=time_series['metered_pct'],
                name='Metered Connections',
                line=dict(color='#8b5cf6', width=3), mode='lines+markers',
                marker=dict(size=6, symbol='circle', color='#8b5cf6', line=dict(width=2, color='white')),
                fill='tozeroy', fillcolor='rgba(139, 92, 246, 0.1)',
                hovertemplate='<b>Metered</b><br>%{y:.1f}%<extra></extra>'
            ))
            fig2.add_hline(y=90, line_dash="dash", line_color="#94a3b8", line_width=2,
                           annotation_text="Target: 90%", annotation_position="right",
                           annotation=dict(font_size=10, font_color="#64748b"))
            fig2.update_layout(
                margin=dict(l=0, r=0, t=30, b=0), height=240,
                yaxis=dict(range=[0, 100], title="Coverage (%)", gridcolor='rgba(148,163,184,0.1)', showline=True, linecolor='rgba(148,163,184,0.2)', linewidth=1),
                xaxis=dict(gridcolor='rgba(148,163,184,0.1)', showline=True, linecolor='rgba(148,163,184,0.2)', linewidth=1),
                showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                bgcolor='rgba(255,255,255,0.8)', bordercolor='rgba(148,163,184,0.2)', borderwidth=1),
                hovermode='x unified', plot_bgcolor='rgba(248,250,252,0.5)', paper_bgcolor='white',
                font=dict(family='Inter, system-ui, sans-serif', size=11, color='#475569')
            )
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

            st.markdown(f"""
                <div style='display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:12px'>
                    <div style='background:#f8fafc;border:1px solid #e5e7eb;padding:12px;border-radius:8px;text-align:center'>
                        <div style='font:600 20px sans-serif;color:#0f172a'>{avg_metered_pct:.1f}%</div>
                        <div style='font:400 11px sans-serif;color:#64748b'>Metered</div>
                    </div>
                    <div style='background:#f8fafc;border:1px solid #e5e7eb;padding:12px;border-radius:8px;text-align:center'>
                        <div style='font:600 20px sans-serif;color:#0f172a'>18.5h</div>
                        <div style='font:400 11px sans-serif;color:#64748b'>Daily Hrs</div>
                    </div>
                    <div style='background:#f8fafc;border:1px solid #e5e7eb;padding:12px;border-radius:8px;text-align:center'>
                        <div style='font:600 20px sans-serif;color:#0f172a'>{avg_resolution_time:.1f}d</div>
                        <div style='font:400 11px sans-serif;color:#64748b'>Resolution</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

    with left_col:
        with st.expander("🧪 Water Quality & Testing", expanded=True):
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(
                x=time_series['date'], y=time_series['chlorine_pass_rate'], fill='tozeroy',
                name='Chlorine Pass Rate', line=dict(color='#3b82f6', width=3),
                fillcolor='rgba(59, 130, 246, 0.2)', hovertemplate='<b>Chlorine</b><br>%{y:.1f}%<extra></extra>'
            ))
            fig3.add_trace(go.Scatter(
                x=time_series['date'], y=time_series['ecoli_pass_rate'], fill='tozeroy',
                name='E.coli Pass Rate', line=dict(color='#10b981', width=3),
                fillcolor='rgba(16, 185, 129, 0.2)', hovertemplate='<b>E.coli</b><br>%{y:.1f}%<extra></extra>'
            ))
            fig3.add_hline(y=95, line_dash="dash", line_color="#94a3b8", line_width=2,
                           annotation_text="Target: 95%", annotation_position="right",
                           annotation=dict(font_size=10, font_color="#64748b"))
            fig3.update_layout(
                margin=dict(l=0, r=0, t=30, b=0), height=280,
                yaxis=dict(range=[0, 100], title="Pass Rate (%)", gridcolor='rgba(148,163,184,0.1)', showline=True, linecolor='rgba(148,163,184,0.2)', linewidth=1),
                xaxis=dict(gridcolor='rgba(148,163,184,0.1)', showline=True, linecolor='rgba(148,163,184,0.2)', linewidth=1),
                showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, bgcolor='rgba(255,255,255,0.8)',
                bordercolor='rgba(148,163,184,0.2)', borderwidth=1), hovermode='x unified', plot_bgcolor='rgba(248,250,252,0.5)', paper_bgcolor='white',
                font=dict(family='Inter, system-ui, sans-serif', size=11, color='#475569')
            )
            st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

            # Quality score cards using HTML grid
            st.markdown(f"""
                <div style='display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-top:12px'>
                    <div style='background:linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);border-radius:10px;padding:12px'>
                        <div style='font:500 10px sans-serif;color:#1e40af;margin-bottom:4px'>Chlorine Testing</div>
                        <div style='display:flex;align-items:baseline;gap:4px;margin-bottom:4px'>
                            <span style='font:700 24px sans-serif;color:#1e3a8a'>{chlorine_pass_rate:.1f}%</span>
                            <span style='font:400 11px sans-serif;color:#1e40af'>pass rate</span>
                        </div>
                        <div style='font:400 10px sans-serif;color:#3b82f6'>{(total_chlorine_tests / time_series.shape[0]):.0f} tests/month avg</div>
                    </div>
                    <div style='background:linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);border-radius:10px;padding:12px'>
                        <div style='font:500 10px sans-serif;color:#047857;margin-bottom:4px'>E.coli Testing</div>
                        <div style='display:flex;align-items:baseline;gap:4px;margin-bottom:4px'>
                            <span style='font:700 24px sans-serif;color:#065f46'>{ecoli_pass_rate:.1f}%</span>
                            <span style='font:400 11px sans-serif;color:#047857'>pass rate</span>
                        </div>
                        <div style='font:400 10px sans-serif;color:#10b981'>{(total_ecoli_tests / time_series.shape[0]):.0f} tests/month avg</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

    with right_col:
        st.markdown("""
            <div style='display:flex;align-items:center;gap:10px;margin-bottom:18px'>
                <span style='font-size:22px'>📋</span>
                <h3 style='margin:0;font:600 16px Inter,system-ui,sans-serif;color:#0f172a'>Regulatory Compliance</h3>
            </div>
        """, unsafe_allow_html=True)

        compliance_metrics = [
            {"label": "Quality Standards", "value": quality_score, "target": 100, "icon": "✓"},
            {"label": "Service Coverage", "value": avg_metered_pct, "target": 90, "icon": "📊"},
            {"label": "WW Treatment", "value": ww_treatment_rate, "target": 80, "icon": "♻️"},
            {"label": "Complaint Resolution", "value": resolution_rate, "target": 90, "icon": "🎯"},
            {"label": "Testing Coverage", "value": 95, "target": 100, "icon": "🧪"}
        ]

        for metric in compliance_metrics:
            pct = (metric["value"] / metric["target"]) * 100
            color = "#10b981" if pct >= 95 else "#f59e0b" if pct >= 80 else "#ef4444"
            bg_color = (
                "rgba(16,185,129,0.1)" if pct >= 95
                else "rgba(245,158,11,0.1)" if pct >= 80
                else "rgba(239,68,68,0.1)"
            )
            status_text = "Excellent" if pct >= 95 else "Good" if pct >= 80 else "Needs Attention"

            st.markdown(f"""
                <div style='background:{bg_color};
                            border-radius:10px;
                            padding:12px;
                            margin-bottom:10px;
                            border:1px solid {color}33'>
                    <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:6px'>
                        <div style='display:flex;align-items:center;gap:6px'>
                            <span style='font-size:14px'>{metric['icon']}</span>
                            <span style='font:600 12px Inter,sans-serif;color:#1e293b'>{metric['label']}</span>
                        </div>
                        <div style='display:flex;align-items:center;gap:8px'>
                            <span style='font:400 10px Inter,sans-serif;color:#64748b;text-transform:uppercase;letter-spacing:0.5px'>{status_text}</span>
                            <span style='font:700 13px Inter,sans-serif;color:{color}'>{metric['value']:.1f}%</span>
                        </div>
                    </div>
                    <div style='width:100%;height:8px;background:#e5e7eb;border-radius:4px;overflow:hidden'>
                        <div style='width:{min(pct, 100):.0f}%; height:8px; background:linear-gradient(90deg, {color}dd, {color}); border-radius:4px; transition:width 0.6s cubic-bezier(0.4, 0, 0.2, 1); box-shadow:0 0 8px {color}66'></div>
                    </div>
                    <div style='font:400 9px sans-serif;color:#94a3b8;margin-top:4px;text-align:right'>
                        Target: {metric['target']}% | Gap: {max(0, metric['target'] - metric['value']):.1f}%
                    </div>
                </div>
            """, unsafe_allow_html=True)

        # Complaints summary card
        st.markdown(f"""
            <div style='background:linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border:1px solid #93c5fd; border-radius:12px; padding:16px;'>
                <div style='display:flex;align-items:center;gap:10px;margin-bottom:12px'>
                    <span style='font-size:20px'>📣</span>
                    <div style='font:600 14px Inter,sans-serif;color:#1e40af'>Complaints Management</div>
                </div>
                <div style='display:grid;grid-template-columns:repeat(3,1fr);gap:12px'>
                    <div style='background:white;border:1px solid #bfdbfe;border-radius:10px;padding:12px;text-align:center'>
                        <div style='font:600 20px sans-serif;color:#0f172a'>{total_complaints:.0f}</div>
                        <div style='font:400 11px sans-serif;color:#64748b'>Complaints</div>
                    </div>
                    <div style='background:white;border:1px solid #bfdbfe;border-radius:10px;padding:12px;text-align:center'>
                        <div style='font:600 20px sans-serif;color:#0f172a'>{total_resolved:.0f}</div>
                        <div style='font:400 11px sans-serif;color:#64748b'>Resolved</div>
                    </div>
                    <div style='background:white;border:1px solid #bfdbfe;border-radius:10px;padding:12px;text-align:center'>
                        <div style='font:600 20px sans-serif;color:#0f172a'>{resolution_rate:.1f}%</div>
                        <div style='font:400 11px sans-serif;color:#64748b'>Resolution Rate</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # Sewer coverage and WW treatment
    with left_col:
        with st.expander("🚽 Sewer Coverage & Public Sanitation", expanded=True):
            fig4 = go.Figure()
            fig4.add_trace(go.Scatter(
                x=time_series['date'], y=time_series['sewer_coverage'], name='Sewer Coverage',
                mode='lines+markers', line=dict(color='#0ea5e9', width=3),
                marker=dict(size=6, symbol='circle', color='#38bdf8', line=dict(width=2, color='white')),
                hovertemplate='<b>Coverage</b><br>%{y:.1f}%<extra></extra>'
            ))
            fig4.add_trace(go.Bar(
                x=time_series['date'], y=time_series['public_toilets'], name='Public Toilets', yaxis='y2',
                marker=dict(color='rgba(59,130,246,0.25)'),
                hovertemplate='<b>Toilets</b><br>%{y:.0f}<extra></extra>'
            ))
            fig4.update_layout(
                margin=dict(l=0, r=0, t=30, b=0), height=280, showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                            bgcolor='rgba(255,255,255,0.8)', bordercolor='rgba(148,163,184,0.2)', borderwidth=1),
                yaxis=dict(title="Sewer Coverage (%)", gridcolor='rgba(148,163,184,0.1)', showline=True, linecolor='rgba(148,163,184,0.2)', linewidth=1),
                yaxis2=dict(title="Public Toilets", overlaying='y', side='right', gridcolor='rgba(148,163,184,0.05)', showline=True, linecolor='rgba(148,163,184,0.2)', linewidth=1),
                xaxis=dict(gridcolor='rgba(148,163,184,0.1)', showline=True, linecolor='rgba(148,163,184,0.2)', linewidth=1),
                hovermode='x unified', plot_bgcolor='rgba(248,250,252,0.5)', paper_bgcolor='white',
                font=dict(family='Inter, system-ui, sans-serif', size=11, color='#475569')
            )
            st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False})

            fig5 = go.Figure()
            fig5.add_trace(go.Bar(
                x=time_series['date'], y=time_series['ww_treatment_rate'], name='Wastewater Treatment',
                marker=dict(color=time_series['ww_treatment_rate'], colorscale=[[0, '#fef3c7'], [0.5, '#c084fc'], [1, '#8b5cf6']], line=dict(width=0)),
                hovertemplate='<b>Treatment Rate</b><br>%{y:.1f}%<extra></extra>'
            ))
            fig5.add_hline(y=80, line_dash="dash", line_color="#94a3b8", line_width=2,
                           annotation_text="Target: 80%", annotation_position="right",
                           annotation=dict(font_size=10, font_color="#64748b"))
            fig5.update_layout(
                margin=dict(l=0, r=0, t=30, b=0), height=240,
                yaxis=dict(range=[0, 100], title="Treatment Rate (%)", gridcolor='rgba(148,163,184,0.1)', showline=True, linecolor='rgba(148,163,184,0.2)', linewidth=1),
                xaxis=dict(gridcolor='rgba(148,163,184,0.1)', showline=True, linecolor='rgba(148,163,184,0.2)', linewidth=1),
                showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                bgcolor='rgba(255,255,255,0.8)', bordercolor='rgba(148,163,184,0.2)', borderwidth=1),
                hovermode='x unified', plot_bgcolor='rgba(248,250,252,0.5)', paper_bgcolor='white',
                font=dict(family='Inter, system-ui, sans-serif', size=11, color='#475569')
            )
            st.plotly_chart(fig5, use_container_width=True, config={"displayModeBar": False})

    # Priority Alerts
    st.markdown("""
        <div style='display:flex;align-items:center;gap:10px;margin-bottom:18px;margin-top:24px'>
            <span style='font-size:22px'>🔔</span>
            <h3 style='margin:0;font:600 16px Inter,system-ui,sans-serif;color:#0f172a'>Priority Alerts</h3>
        </div>
    """, unsafe_allow_html=True)

    alerts = []
    ww_treatment_rate = time_series['ww_treatment_rate'].mean()
    if ww_treatment_rate < 80:
        alerts.append({
            "type": "warning", "icon": "⚠️", "title": "WW Treatment Below Target",
            "detail": f"{ww_treatment_rate:.1f}% vs 80% target", "color": "#fef3c7", "border": "#fbbf24", "text": "#92400e", "priority": "high"
        })
    if avg_metered_pct < 80:
        alerts.append({
            "type": "info", "icon": "ℹ️", "title": "Metering Coverage Low",
            "detail": f"{avg_metered_pct:.1f}% metered connections", "color": "#dbeafe", "border": "#60a5fa", "text": "#1e3a8a", "priority": "medium"
        })
    if quality_score >= 90:
        alerts.append({
            "type": "success", "icon": "✅", "title": "Quality Compliance Excellent",
            "detail": f"{quality_score:.1f}% exceeds standards", "color": "#d1fae5", "border": "#34d399", "text": "#065f46", "priority": "info"
        })
    if resolution_rate < 80:
        alerts.append({
            "type": "warning", "icon": "⏰", "title": "Low Resolution Rate",
            "detail": f"{resolution_rate:.1f}% complaints resolved", "color": "#fef3c7", "border": "#fbbf24", "text": "#92400e", "priority": "high"
        })

    if not alerts:
        st.markdown("""
            <div style='background:linear-gradient(135deg, #f0fdf4, #dcfce7); border:1px solid #86efac; padding:16px; border-radius:12px; text-align:center; box-shadow:0 2px 4px rgba(22,101,52,0.1)'>
                <div style='font-size:32px;margin-bottom:8px'>✅</div>
                <div style='font:600 13px Inter,sans-serif;color:#166534;margin-bottom:4px'>All Systems Operational</div>
                <div style='font:400 11px sans-serif;color:#16a34a'>No alerts at this time</div>
            </div>
        """, unsafe_allow_html=True)
    else:
        for alert in alerts:
            priority_badge = f"<span style='background:{alert['border']};color:white;padding:2px 6px;border-radius:10px;font:600 8px sans-serif;text-transform:uppercase;letter-spacing:0.5px'>{alert['priority']}</span>"
            st.markdown(f"""
                <div style='background:{alert['color']}; border-left:4px solid {alert['border']}; border-radius:10px; padding:14px; margin-bottom:10px; box-shadow:0 2px 4px rgba(0,0,0,0.08); transition:all 0.2s ease'>
                    <div style='display:flex;align-items:start;gap:10px'>
                        <span style='font-size:20px;line-height:1'>{alert['icon']}</span>
                        <div style='flex:1'>
                            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:4px'>
                                <div style='font:600 13px Inter,sans-serif;color:{alert['text']}'>{alert['title']}</div>
                                {priority_badge}
                            </div>
                            <div style='font:400 11px Inter,sans-serif;color:{alert['text']};opacity:0.85;line-height:1.4'>{alert['detail']}</div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
