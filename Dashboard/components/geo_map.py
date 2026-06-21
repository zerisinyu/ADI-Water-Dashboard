"""
Choropleth map component for zone-level KPI visualization.

Uses the existing GeoJSON files (zones.geojson, zone_points_approx.geojson)
to render interactive Plotly choropleth maps colored by selected metrics.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "Data"


def _load_geojson() -> Optional[dict]:
    """Load zones GeoJSON file."""
    geojson_path = DATA_DIR / "zones.geojson"
    if not geojson_path.exists():
        logger.warning("GeoJSON file not found: %s", geojson_path)
        return None
    try:
        with open(geojson_path) as f:
            return json.load(f)
    except Exception:
        logger.exception("Failed to load GeoJSON")
        return None


def _geojson_to_dataframe(geojson: dict) -> pd.DataFrame:
    """Extract properties from GeoJSON features into a DataFrame."""
    records = []
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        records.append(props)
    return pd.DataFrame(records)


METRIC_OPTIONS = {
    "water_safely_pct": {"label": "Water Safely Managed (%)", "colorscale": "Blues", "range": [0, 100]},
    "water_basic_pct": {"label": "Water Basic Access (%)", "colorscale": "Teal", "range": [0, 100]},
    "water_surface_pct": {"label": "Surface Water Use (%)", "colorscale": "Reds", "range": [0, 30]},
    "sewer_safely_pct": {"label": "Sanitation Safely Managed (%)", "colorscale": "Greens", "range": [0, 100]},
    "sewer_open_def_pct": {"label": "Open Defecation (%)", "colorscale": "OrRd", "range": [0, 20]},
    "safeAccess": {"label": "Combined Safe Access (%)", "colorscale": "Viridis", "range": [0, 100]},
}


def render_choropleth(
    metric_key: str = "safeAccess",
    country_filter: Optional[str] = None,
    height: int = 500,
) -> None:
    """
    Render an interactive choropleth map colored by the selected metric.

    Args:
        metric_key: Key from METRIC_OPTIONS to color zones by.
        country_filter: Optional country to filter zones.
        height: Chart height in pixels.
    """
    geojson = _load_geojson()
    if geojson is None:
        st.info("Geographic data not available (zones.geojson missing)")
        return

    df = _geojson_to_dataframe(geojson)
    if df.empty:
        st.info("No zone data in GeoJSON")
        return

    # Filter by country
    if country_filter and country_filter != "All" and "country" in df.columns:
        df = df[df["country"].str.lower() == country_filter.lower()]

    if metric_key not in df.columns:
        st.warning(f"Metric '{metric_key}' not found in geographic data")
        return

    df[metric_key] = pd.to_numeric(df[metric_key], errors="coerce")

    metric_info = METRIC_OPTIONS.get(metric_key, {"label": metric_key, "colorscale": "Viridis", "range": [0, 100]})

    # Build choropleth using scatter_map with zone points
    points_path = DATA_DIR / "zone_points_approx.geojson"
    if points_path.exists():
        try:
            with open(points_path) as f:
                points_geojson = json.load(f)

            # Extract lat/lon from point features
            for feature in points_geojson.get("features", []):
                props = feature.get("properties", {})
                coords = feature.get("geometry", {}).get("coordinates", [0, 0])
                name = props.get("name", "")
                # Match to df
                mask = df["name"] == name
                if mask.any():
                    df.loc[mask, "lon"] = coords[0]
                    df.loc[mask, "lat"] = coords[1]

            if "lat" in df.columns and "lon" in df.columns:
                df = df.dropna(subset=["lat", "lon", metric_key])

                fig = px.scatter_map(
                    df,
                    lat="lat",
                    lon="lon",
                    color=metric_key,
                    size=metric_key,
                    hover_name="name",
                    hover_data={
                        "country": True,
                        metric_key: ":.1f",
                        "lat": False,
                        "lon": False,
                    },
                    color_continuous_scale=metric_info["colorscale"],
                    range_color=metric_info["range"],
                    size_max=25,
                    zoom=4,
                    title=metric_info["label"],
                )
                fig.update_layout(
                    height=height,
                    map_style="carto-positron",
                    margin=dict(l=0, r=0, t=40, b=0),
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                return
        except Exception:
            logger.exception("Failed to render point-based map")

    # Fallback: simple bar chart by zone if map rendering fails
    fig = px.bar(
        df.sort_values(metric_key, ascending=False),
        x="name",
        y=metric_key,
        color=metric_key,
        color_continuous_scale=metric_info["colorscale"],
        title=f"{metric_info['label']} by Zone",
        labels={"name": "Zone", metric_key: metric_info["label"]},
    )
    fig.update_layout(height=height, xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_map_selector_and_chart(country_filter: Optional[str] = None) -> None:
    """Render a metric selector dropdown followed by the choropleth map."""
    metric_labels = {k: v["label"] for k, v in METRIC_OPTIONS.items()}

    selected = st.selectbox(
        "Map Metric",
        options=list(metric_labels.keys()),
        format_func=lambda k: metric_labels[k],
        key="geo_map_metric",
    )

    render_choropleth(metric_key=selected, country_filter=country_filter)
