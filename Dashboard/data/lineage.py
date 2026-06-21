"""
Data lineage visualization using Plotly Sankey diagram.

Shows the flow: source CSV -> DuckDB table -> derived view -> dashboard page,
providing transparency into how raw data becomes the KPIs shown on screen.
"""
from __future__ import annotations

import logging

import plotly.graph_objects as go
import streamlit as st

logger = logging.getLogger(__name__)

# Lineage DAG definition
# Each node has: label, color
# Each link has: source_idx, target_idx, value (thickness), label
NODES = [
    # Layer 0: Source CSVs (indices 0-6)
    {"label": "billing.csv", "color": "#94a3b8"},
    {"label": "production.csv", "color": "#94a3b8"},
    {"label": "sw_service.csv", "color": "#94a3b8"},
    {"label": "w_access.csv", "color": "#94a3b8"},
    {"label": "s_access.csv", "color": "#94a3b8"},
    {"label": "all_fin_service.csv", "color": "#94a3b8"},
    {"label": "all_nationalacc.csv", "color": "#94a3b8"},
    # Layer 1: DuckDB tables (indices 7-13)
    {"label": "billing", "color": "#3b82f6"},
    {"label": "production", "color": "#3b82f6"},
    {"label": "sw_service", "color": "#3b82f6"},
    {"label": "w_access", "color": "#3b82f6"},
    {"label": "s_access", "color": "#3b82f6"},
    {"label": "fin_service", "color": "#3b82f6"},
    {"label": "national_accounts", "color": "#3b82f6"},
    # Layer 2: Derived views (indices 14-18)
    {"label": "v_billing_monthly", "color": "#8b5cf6"},
    {"label": "v_production_monthly", "color": "#8b5cf6"},
    {"label": "v_nrw_monthly", "color": "#8b5cf6"},
    {"label": "v_service_quality", "color": "#8b5cf6"},
    {"label": "v_financial_monthly", "color": "#8b5cf6"},
    # Layer 3: Dashboard pages (indices 19-25)
    {"label": "Executive Dashboard", "color": "#10b981"},
    {"label": "Access & Coverage", "color": "#10b981"},
    {"label": "Service Quality", "color": "#10b981"},
    {"label": "Financial Health", "color": "#10b981"},
    {"label": "Production", "color": "#10b981"},
    {"label": "Governance", "color": "#10b981"},
    {"label": "Sector Environment", "color": "#10b981"},
    # Layer 3 continued: Analytics features (indices 26-28)
    {"label": "Forecasting", "color": "#f59e0b"},
    {"label": "Anomaly Detection", "color": "#f59e0b"},
    {"label": "Benchmarking", "color": "#f59e0b"},
]

LINKS = [
    # CSV -> DuckDB table
    {"source": 0, "target": 7, "value": 8, "label": "ingest + validate"},
    {"source": 1, "target": 8, "value": 5, "label": "ingest + validate"},
    {"source": 2, "target": 9, "value": 5, "label": "ingest + validate"},
    {"source": 3, "target": 10, "value": 4, "label": "ingest + validate"},
    {"source": 4, "target": 11, "value": 4, "label": "ingest + validate"},
    {"source": 5, "target": 12, "value": 4, "label": "ingest + validate"},
    {"source": 6, "target": 13, "value": 4, "label": "ingest + validate"},
    # DuckDB table -> Derived views
    {"source": 7, "target": 14, "value": 6, "label": "aggregate monthly"},
    {"source": 8, "target": 15, "value": 5, "label": "aggregate monthly"},
    {"source": 14, "target": 16, "value": 4, "label": "join billing+production"},
    {"source": 15, "target": 16, "value": 4, "label": "join billing+production"},
    {"source": 9, "target": 17, "value": 5, "label": "derive quality rates"},
    {"source": 12, "target": 18, "value": 4, "label": "derive cost recovery"},
    # Tables/Views -> Dashboard pages
    {"source": 14, "target": 19, "value": 5, "label": "collection efficiency"},
    {"source": 16, "target": 19, "value": 4, "label": "NRW"},
    {"source": 18, "target": 19, "value": 3, "label": "cost recovery"},
    {"source": 10, "target": 20, "value": 5, "label": "water access"},
    {"source": 11, "target": 20, "value": 5, "label": "sanitation access"},
    {"source": 17, "target": 21, "value": 5, "label": "quality metrics"},
    {"source": 18, "target": 22, "value": 4, "label": "financial KPIs"},
    {"source": 15, "target": 23, "value": 4, "label": "production volumes"},
    {"source": 13, "target": 24, "value": 4, "label": "governance data"},
    {"source": 13, "target": 25, "value": 4, "label": "budget data"},
    # Views -> Analytics features
    {"source": 14, "target": 26, "value": 3, "label": "forecast input"},
    {"source": 15, "target": 26, "value": 3, "label": "forecast input"},
    {"source": 16, "target": 26, "value": 3, "label": "forecast input"},
    {"source": 14, "target": 27, "value": 3, "label": "anomaly input"},
    {"source": 16, "target": 27, "value": 3, "label": "anomaly input"},
    {"source": 14, "target": 28, "value": 3, "label": "benchmark KPIs"},
    {"source": 16, "target": 28, "value": 3, "label": "benchmark KPIs"},
    {"source": 18, "target": 28, "value": 3, "label": "benchmark KPIs"},
]


def render_data_lineage(height: int = 600) -> None:
    """Render a Sankey diagram showing the data lineage from CSV to dashboard."""

    node_labels = [n["label"] for n in NODES]
    node_colors = [n["color"] for n in NODES]

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=20,
            thickness=25,
            line=dict(color="#1e293b", width=1),
            label=node_labels,
            color=node_colors,
            hovertemplate="%{label}<extra></extra>",
        ),
        link=dict(
            source=[lk["source"] for lk in LINKS],
            target=[lk["target"] for lk in LINKS],
            value=[lk["value"] for lk in LINKS],
            label=[lk["label"] for lk in LINKS],
            color="rgba(148, 163, 184, 0.3)",
            hovertemplate="%{label}<br>%{source.label} → %{target.label}<extra></extra>",
        ),
    ))

    fig.update_layout(
        title=dict(
            text="Data Pipeline Lineage",
            font=dict(size=18, color="#0f172a"),
        ),
        height=height,
        font=dict(size=12, color="#334155"),
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="white",
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Legend
    st.markdown("""
    <div style="display: flex; gap: 24px; flex-wrap: wrap; padding: 12px 0;">
        <div style="display: flex; align-items: center; gap: 6px;">
            <div style="width: 16px; height: 16px; border-radius: 3px; background: #94a3b8;"></div>
            <span style="font-size: 13px; color: #64748b;">Source CSVs</span>
        </div>
        <div style="display: flex; align-items: center; gap: 6px;">
            <div style="width: 16px; height: 16px; border-radius: 3px; background: #3b82f6;"></div>
            <span style="font-size: 13px; color: #64748b;">DuckDB Tables</span>
        </div>
        <div style="display: flex; align-items: center; gap: 6px;">
            <div style="width: 16px; height: 16px; border-radius: 3px; background: #8b5cf6;"></div>
            <span style="font-size: 13px; color: #64748b;">Derived Views</span>
        </div>
        <div style="display: flex; align-items: center; gap: 6px;">
            <div style="width: 16px; height: 16px; border-radius: 3px; background: #10b981;"></div>
            <span style="font-size: 13px; color: #64748b;">Dashboard Pages</span>
        </div>
        <div style="display: flex; align-items: center; gap: 6px;">
            <div style="width: 16px; height: 16px; border-radius: 3px; background: #f59e0b;"></div>
            <span style="font-size: 13px; color: #64748b;">Analytics Features</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
