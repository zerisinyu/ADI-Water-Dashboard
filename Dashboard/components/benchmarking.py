"""
Cross-country benchmarking component.

Renders radar charts and ranking tables comparing countries across
key water/sanitation KPIs.
"""
from __future__ import annotations

import logging
from typing import Optional

import plotly.graph_objects as go
import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)


def render_benchmarking_radar(
    year: Optional[int] = None,
) -> None:
    """
    Render a radar chart comparing all countries across 6 KPIs,
    plus a ranking table with percentile positions.
    """
    from data.database import query
    from utils import _ensure_pipeline

    _ensure_pipeline()

    # Collect metrics per country
    countries_data = {}

    # 1. Collection efficiency from billing
    try:
        coll_df = query("""
            SELECT country,
                   SUM(total_paid) / NULLIF(SUM(total_billed), 0) * 100 AS collection_efficiency
            FROM v_billing_monthly
            GROUP BY country
        """)
        for _, row in coll_df.iterrows():
            c = row["country"]
            countries_data.setdefault(c, {})["Collection Efficiency"] = min(row["collection_efficiency"], 100)
    except Exception:
        pass

    # 2. NRW from v_nrw_monthly
    try:
        nrw_df = query("""
            SELECT country, AVG(nrw_pct) AS avg_nrw
            FROM v_nrw_monthly
            GROUP BY country
        """)
        for _, row in nrw_df.iterrows():
            c = row["country"]
            # Invert NRW so higher = better (100 - NRW)
            countries_data.setdefault(c, {})["NRW Score"] = max(0, 100 - row["avg_nrw"])
    except Exception:
        pass

    # 3. Service hours
    try:
        svc_df = query("""
            SELECT country, AVG(avg_service_hours) AS avg_hours
            FROM v_production_monthly
            GROUP BY country
        """)
        for _, row in svc_df.iterrows():
            c = row["country"]
            # Normalize to 0-100 (24h = 100)
            countries_data.setdefault(c, {})["Service Continuity"] = min(row["avg_hours"] / 24 * 100, 100)
    except Exception:
        pass

    # 4. Water access from w_access (latest year)
    try:
        wa_df = query("""
            SELECT country, AVG(w_safely_managed_pct) AS safe_pct
            FROM w_access
            WHERE year = (SELECT MAX(year) FROM w_access)
            GROUP BY country
        """)
        for _, row in wa_df.iterrows():
            c = row["country"]
            countries_data.setdefault(c, {})["Water Access"] = row["safe_pct"]
    except Exception:
        pass

    # 5. Sanitation access
    try:
        sa_df = query("""
            SELECT country, AVG(s_safely_managed_pct) AS safe_pct
            FROM s_access
            WHERE year = (SELECT MAX(year) FROM s_access)
            GROUP BY country
        """)
        for _, row in sa_df.iterrows():
            c = row["country"]
            countries_data.setdefault(c, {})["Sanitation Access"] = row["safe_pct"]
    except Exception:
        pass

    # 6. Cost recovery
    try:
        cr_df = query("""
            SELECT country, AVG(cost_recovery_pct) AS cost_recovery
            FROM v_financial_monthly
            GROUP BY country
        """)
        for _, row in cr_df.iterrows():
            c = row["country"]
            countries_data.setdefault(c, {})["Cost Recovery"] = min(row["cost_recovery"], 100)
    except Exception:
        pass

    if not countries_data:
        st.info("Insufficient data for cross-country benchmarking")
        return

    # Build radar chart
    categories = ["Collection Efficiency", "NRW Score", "Service Continuity",
                   "Water Access", "Sanitation Access", "Cost Recovery"]

    from charts import colorway
    colors = colorway()[:4]

    fig = go.Figure()
    for i, (country, metrics) in enumerate(sorted(countries_data.items())):
        values = [metrics.get(cat, 0) for cat in categories]
        values.append(values[0])  # Close the polygon

        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=categories + [categories[0]],
            fill="toself",
            name=country,
            line=dict(color=colors[i % len(colors)]),
            fillcolor=f"rgba({','.join(str(int(c, 16)) for c in [colors[i % len(colors)][1:3], colors[i % len(colors)][3:5], colors[i % len(colors)][5:7]])}, 0.1)" if len(colors[i % len(colors)]) == 7 else None,
        ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        title="Cross-Country Performance Benchmark",
        height=440,
        showlegend=True,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Ranking table
    st.markdown("#### Country Rankings")
    rows = []
    for country, metrics in sorted(countries_data.items()):
        row = {"Country": country}
        total = 0
        for cat in categories:
            val = metrics.get(cat, 0)
            row[cat] = f"{val:.1f}"
            total += val
        row["Overall Score"] = f"{total / len(categories):.1f}"
        rows.append(row)

    ranking_df = pd.DataFrame(rows).sort_values("Overall Score", ascending=False)
    ranking_df.index = range(1, len(ranking_df) + 1)
    ranking_df.index.name = "Rank"
    st.dataframe(ranking_df, use_container_width=True)
