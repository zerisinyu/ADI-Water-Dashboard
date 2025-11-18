import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
try:
    import folium  # type: ignore
    from streamlit_folium import st_folium  # type: ignore
    HAS_FOLIUM = True
except Exception:
    HAS_FOLIUM = False

import numpy as np 

from utils import DATA_DIR
ACCESS_WATER_FILE = DATA_DIR / "Water Access Data.csv"
ACCESS_SEWER_FILE = DATA_DIR / "Sewer Access Data.csv"


@st.cache_data
def _load_access_kpi_data() -> pd.DataFrame:
    """
    Combine the water and sewer access CSVs into a tidy structure.
    """
    frames: List[pd.DataFrame] = []
    for path in (ACCESS_WATER_FILE, ACCESS_SEWER_FILE):
        if not path.exists():
            continue
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        frame.columns = frame.columns.str.replace(r"^(w_|s_)", "", regex=True)
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df.columns = df.columns.str.replace(r"^(w_|s_)", "", regex=True)
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    for col in ("zone", "country", "type"):
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()
    if "type" in df.columns:
        df["type"] = (
            df["type"]
            .astype("string")
            .str.strip()
            .str.lower()
            .replace({"w_access": "water", "s_access": "sewer"})
        )
    numeric_cols = {col for col in df.columns if col.endswith("_pct")}
    numeric_cols.update({"popn_total", "surface_water", "safely_managed", "open_def", "unimproved"})
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _ensure_year_int(df: pd.DataFrame) -> pd.DataFrame:
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    return df


def _country_summary_2024(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate 2024 safely managed metrics per (country, type).
    """
    d = df.copy()
    d = d[d["year"] == 2024]
    if d.empty:
        return d
    if "type" not in d.columns:
        d["type"] = "unknown"
    d["sewer_gap_pct"] = d.get("unimproved_pct", np.nan) + d.get("open_def_pct", np.nan)
    agg = (
        d.groupby(["country", "type"])
        .agg(
            safely_min=("safely_managed_pct", "min"),
            safely_med=("safely_managed_pct", "median"),
            safely_max=("safely_managed_pct", "max"),
            open_def_min=("open_def_pct", "min"),
            open_def_med=("open_def_pct", "median"),
            open_def_max=("open_def_pct", "max"),
            unimproved_min=("unimproved_pct", "min"),
            unimproved_med=("unimproved_pct", "median"),
            unimproved_max=("unimproved_pct", "max"),
            sewer_gap_min=("sewer_gap_pct", "min"),
            sewer_gap_med=("sewer_gap_pct", "median"),
            sewer_gap_max=("sewer_gap_pct", "max"),
            zones=("zone", "nunique"),
            popn_sum=("popn_total", "sum"),
        )
        .reset_index()
    )
    return agg


def _surface_water_2024(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    For 2024 water records, return per-zone exposure and per-country ranges.
    """
    d = df.copy()
    d = d[(d["year"] == 2024) & (d.get("type") == "water")]
    if d.empty:
        return d, pd.DataFrame()
    if "surface_water_pct" not in d.columns:
        d["surface_water_pct"] = np.nan
    if "popn_total" not in d.columns:
        d["popn_total"] = np.nan
    d = d.dropna(subset=["surface_water_pct", "popn_total"]).copy()
    if d.empty:
        return d, pd.DataFrame()
    d["surface_users_est"] = (d["surface_water_pct"] / 100.0) * d["popn_total"]
    rng = (
        d.groupby("country")
        .agg(
            pct_min=("surface_water_pct", "min"),
            pct_med=("surface_water_pct", "median"),
            pct_max=("surface_water_pct", "max"),
            users_min=("surface_users_est", "min"),
            users_med=("surface_users_est", "median"),
            users_max=("surface_users_est", "max"),
        )
        .reset_index()
    )
    return d, rng


def _trend_series(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return rows between 2020 and 2024 for time-series visualisations.
    """
    if "year" not in df.columns:
        return pd.DataFrame()
    return df[(df["year"] >= 2020) & (df["year"] <= 2024)].copy()


def _urban_rural_tag(zone: Any) -> str:
    if pd.isna(zone):
        return "unknown"
    z = str(zone).lower()
    if "rural" in z:
        return "rural"
    if "urban" in z:
        return "urban"
    if any(k in z for k in ["yaounde", "douala", "kawempe", "kampala", "maseru", "lilongwe", "blantyre"]):
        return "urban"
    return "other"


def scene_access():
    df = _load_access_kpi_data()
    if df.empty:
        st.info("Access datasets not available. Ensure the Water and Sewer access CSVs are in the Data directory.")
        return

    df = _ensure_year_int(df)
    summary_2024 = _country_summary_2024(df)

    st.markdown("<div class='panel'><h3>2024 Safely Managed Coverage by Country</h3>", unsafe_allow_html=True)
    safely_med = summary_2024.dropna(subset=["safely_med"]).copy() if not summary_2024.empty else pd.DataFrame()
    if safely_med.empty:
        st.info("No safely managed coverage records found for 2024.")
    else:
        fig_overall = px.bar(
            safely_med,
            x="country",
            y="safely_med",
            color="type",
            barmode="group",
            hover_data={
                "safely_med": ":.1f",
                "safely_min": ":.1f",
                "safely_max": ":.1f",
                "open_def_med": ":.1f",
                "unimproved_med": ":.1f",
                "zones": True,
                "popn_sum": True,
            },
        )
        fig_overall.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            yaxis_title="Safely managed % (median)",
            legend_title="Service",
        )
        st.plotly_chart(fig_overall, use_container_width=True, config={"displayModeBar": False})
        st.caption("Hover for min/max ranges, open defecation, unimproved shares, zone counts, and population totals.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><h3>2024 Sewer Access Gap (Unimproved + Open Defecation)</h3>", unsafe_allow_html=True)
    sewer_gap = summary_2024[summary_2024["type"] == "sewer"].dropna(subset=["sewer_gap_med"]).copy() if not summary_2024.empty else pd.DataFrame()
    if sewer_gap.empty:
        st.info("No sewer access gap data available for 2024.")
    else:
        fig_gap = px.bar(
            sewer_gap,
            x="country",
            y="sewer_gap_med",
            hover_data={"sewer_gap_min": ":.1f", "sewer_gap_max": ":.1f"},
        )
        fig_gap.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            yaxis_title="Gap % (median)",
            showlegend=False,
        )
        st.plotly_chart(fig_gap, use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><h3>Surface Water Exposure (Water type, 2024)</h3>", unsafe_allow_html=True)
    sw_2024, sw_ranges = _surface_water_2024(df)
    if sw_2024.empty:
        st.info("No surface water metrics recorded for 2024.")
    else:
        left, right = st.columns(2)
        fig_surface_pct = px.strip(
            sw_2024,
            x="country",
            y="surface_water_pct",
            hover_data=["zone", "surface_water_pct", "popn_total", "surface_users_est"],
        )
        fig_surface_pct.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            yaxis_title="Surface water users (%)",
            xaxis_title=None,
        )
        fig_surface_cnt = px.scatter(
            sw_2024,
            x="country",
            y="surface_users_est",
            size="popn_total",
            size_max=45,
            hover_data=["zone", "surface_water_pct", "popn_total", "surface_users_est"],
        )
        fig_surface_cnt.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            yaxis_title="Estimated users",
            xaxis_title=None,
        )
        with left:
            st.plotly_chart(fig_surface_pct, use_container_width=True, config={"displayModeBar": False})
        with right:
            st.plotly_chart(fig_surface_cnt, use_container_width=True, config={"displayModeBar": False})
        if not sw_ranges.empty:
            st.caption("Per-country surface water exposure ranges (2024).")
            st.dataframe(sw_ranges.round(1), width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><h3>Population Coverage Trend (2020–2024)</h3>", unsafe_allow_html=True)
    ts = _trend_series(df)
    if ts.empty or "popn_total" not in ts.columns or ts["popn_total"].dropna().empty:
        st.info("Population totals unavailable for the requested period.")
    else:
        pop_trend = ts.groupby(["country", "year"], as_index=False)["popn_total"].sum()
        fig_pop_trend = px.line(
            pop_trend,
            x="year",
            y="popn_total",
            color="country",
            markers=True,
        )
        fig_pop_trend.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            yaxis_title="Population",
            legend_title="Country",
        )
        st.plotly_chart(fig_pop_trend, use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><h3>Urban vs Rural Disparities (2024)</h3>", unsafe_allow_html=True)
    ur = df[df["year"] == 2024].copy()
    if ur.empty or "country" not in ur.columns:
        st.info("No 2024 records available to compare urban and rural zones.")
    else:
        ur["ur_tag"] = ur["zone"].map(_urban_rural_tag)
        ur["country"] = ur["country"].astype("string")
        les = ur[ur["country"].str.upper() == "LESOTHO"].copy()
        mw = ur[ur["country"].str.upper() == "MALAWI"].copy()
        col1, col2 = st.columns(2)
        if not les.empty:
            fig_les = px.bar(
                les,
                x="zone",
                y="safely_managed_pct",
                color="type",
                hover_data=["ur_tag", "open_def_pct", "unimproved_pct"],
            )
            fig_les.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_tickangle=-30,
                yaxis_title="Safely managed %",
                legend_title="Service",
            )
            with col1:
                st.plotly_chart(fig_les, use_container_width=True, config={"displayModeBar": False})
        else:
            col1.info("No Lesotho records found for 2024.")
        if not mw.empty:
            fig_mw = px.bar(
                mw,
                x="zone",
                y="safely_managed_pct",
                color="type",
                hover_data=["ur_tag", "open_def_pct", "unimproved_pct"],
            )
            fig_mw.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_tickangle=-30,
                yaxis_title="Safely managed %",
                legend_title="Service",
            )
            with col2:
                st.plotly_chart(fig_mw, use_container_width=True, config={"displayModeBar": False})
        else:
            col2.info("No Malawi records found for 2024.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><h3>Focused Zone Trends (2020–2024)</h3>", unsafe_allow_html=True)
    if ts.empty or "zone" not in ts.columns or "country" not in ts.columns:
        st.info("Time series data unavailable for the 2020–2024 window.")
    else:
        focus_mask = ts["zone"].str.contains("yaounde|maseru|kawempe", case=False, na=False) | ts["country"].astype("string").str.upper().isin(["MALAWI"])
        focus_zones = ts[focus_mask].copy()
        if focus_zones.empty:
            st.info("No focus zones matched the current filters.")
        else:
            fig_yoy = px.line(
                focus_zones,
                x="year",
                y="safely_managed_pct",
                color="zone",
                facet_row="country",
                facet_col="type",
                markers=True,
                hover_data=["country", "zone", "type"],
            )
            fig_yoy.update_layout(
                margin=dict(l=10, r=10, t=40, b=10),
                yaxis_title="Safely managed %",
            )
            st.plotly_chart(fig_yoy, use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><h3>Priority Zones (2024 snapshot)</h3>", unsafe_allow_html=True)
    if ur.empty or "country" not in ur.columns or "zone" not in ur.columns:
        st.info("Priority ranking unavailable without 2024 records.")
    else:
        priority = (
            ur.assign(sewer_gap_pct=lambda x: x.get("unimproved_pct", np.nan) + x.get("open_def_pct", np.nan))
            .loc[
                lambda x: (
                    (x["country"].str.upper() == "MALAWI")
                    | (x["zone"].str.contains("kawempe", case=False, na=False))
                    | (x["zone"].str.contains("yaounde 1", case=False, na=False))
                    | ((x["country"].str.upper() == "LESOTHO") & (x["zone"].str.contains("rural", case=False, na=False)))
                )
            ][
                ["country", "zone", "type", "popn_total", "safely_managed_pct", "open_def_pct", "unimproved_pct", "sewer_gap_pct"]
            ]
            .sort_values(["country", "zone", "type"])
        )
        if priority.empty:
            st.info("Priority filter returned no rows.")
        else:
            priority_display = priority.rename(
                columns={
                    "popn_total": "population",
                    "safely_managed_pct": "safely_managed_%",
                    "open_def_pct": "open_def_%",
                    "unimproved_pct": "unimproved_%",
                    "sewer_gap_pct": "sewer_gap_%",
                }
            ).copy()
            percent_cols = [col for col in priority_display.columns if col.endswith("%")]
            for col in percent_cols:
                priority_display[col] = priority_display[col].round(1)
            if "population" in priority_display.columns:
                priority_display["population"] = pd.to_numeric(priority_display["population"], errors="coerce").round(0).astype("Int64")
            st.dataframe(priority_display, width="stretch")
            st.caption("Sewer gap = unimproved % + open defecation % (sewer).")
    st.markdown("</div>", unsafe_allow_html=True)
