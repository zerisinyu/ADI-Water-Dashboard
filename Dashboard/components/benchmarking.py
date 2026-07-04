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
    country: Optional[str] = None,
) -> None:
    """
    Render a peer-comparison radar chart. With no country selected (or "All"),
    compares every country. With a single country selected, compares its zones
    instead — the meaningful comparison narrows from country to zone once the
    reader has picked one country to look at.
    """
    if country and country != "All":
        _render_zone_benchmark(country)
    else:
        _render_country_benchmark()


def _render_country_benchmark() -> None:
    """Cross-country radar across 6 KPIs, plus a country ranking table."""
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

    from charts import style_fig
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=True,
    )
    style_fig(fig, title="Cross-country performance benchmark", height=440, legend_top=True)
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


def _render_zone_benchmark(country: str) -> None:
    """Cross-zone radar for a single country, plus a zone ranking table.

    Only three KPIs are genuinely available at zone granularity: collection
    efficiency and the two JMP access rates. NRW and service continuity are
    keyed to `source` (production/NRW data), and a source can serve several
    zones, so those two can't be attributed to a single zone without
    fabricating a split — they're left out here rather than estimated,
    matching how the rest of the dashboard handles this gap (see the
    Production page's source-level filter and its data-quality notes).
    """
    from data.database import query
    from utils import _ensure_pipeline

    _ensure_pipeline()
    _c = country.replace("'", "''")

    zones_data: dict = {}

    try:
        coll_df = query(f"""
            SELECT zone,
                   SUM(total_paid) / NULLIF(SUM(total_billed), 0) * 100 AS collection_efficiency
            FROM v_billing_monthly
            WHERE LOWER(country) = LOWER('{_c}')
            GROUP BY zone
        """)
        for _, row in coll_df.iterrows():
            z = row["zone"]
            zones_data.setdefault(z, {})["Collection Efficiency"] = min(row["collection_efficiency"], 100)
    except Exception:
        pass

    try:
        wa_df = query(f"""
            SELECT zone, AVG(w_safely_managed_pct) AS safe_pct
            FROM w_access
            WHERE LOWER(country) = LOWER('{_c}') AND year = (
                SELECT MAX(year) FROM w_access WHERE LOWER(country) = LOWER('{_c}')
            )
            GROUP BY zone
        """)
        for _, row in wa_df.iterrows():
            zones_data.setdefault(row["zone"], {})["Water Access"] = row["safe_pct"]
    except Exception:
        pass

    try:
        sa_df = query(f"""
            SELECT zone, AVG(s_safely_managed_pct) AS safe_pct
            FROM s_access
            WHERE LOWER(country) = LOWER('{_c}') AND year = (
                SELECT MAX(year) FROM s_access WHERE LOWER(country) = LOWER('{_c}')
            )
            GROUP BY zone
        """)
        for _, row in sa_df.iterrows():
            zones_data.setdefault(row["zone"], {})["Sanitation Access"] = row["safe_pct"]
    except Exception:
        pass

    if not zones_data:
        st.info(f"Insufficient zone-level data for {country}.")
        return

    categories = ["Collection Efficiency", "Water Access", "Sanitation Access"]

    from charts import colorway
    colors = colorway()

    fig = go.Figure()
    for i, (zone, metrics) in enumerate(sorted(zones_data.items())):
        values = [metrics.get(cat, 0) for cat in categories]
        values.append(values[0])
        color = colors[i % len(colors)]
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=categories + [categories[0]],
            fill="toself",
            name=zone,
            line=dict(color=color),
            fillcolor=f"rgba({','.join(str(int(color[j:j+2], 16)) for j in (1, 3, 5))}, 0.1)" if len(color) == 7 else None,
        ))

    from charts import style_fig
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=True,
    )
    style_fig(fig, title=f"{country} — cross-zone performance benchmark", height=440, legend_top=True)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("#### Zone Rankings")
    rows = []
    for zone, metrics in sorted(zones_data.items()):
        row = {"Zone": zone}
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
