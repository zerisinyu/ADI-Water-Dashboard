from __future__ import annotations

import io
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


# ----------------------------- Styles & Shell -----------------------------

def _inject_styles():
    # Read CSS file
    with open(os.path.join(os.path.dirname(__file__), "styles.css")) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# ----------------------------- Mock Data -----------------------------

DATA_DIR = Path(__file__).resolve().parents[1] / "Data"

def _load_json(name: str) -> Optional[Dict[str, Any]]:
    p = DATA_DIR / name
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None


def _get_executive_snapshot() -> Dict[str, Any]:
    return _load_json("executive_summary.json") or {
        "month": "2025-08",
        "water_safe_pct": 59,
        "san_safe_pct": 31,
        "collection_eff_pct": 94,
        "om_coverage_pct": 98,
        "nrw_pct": 44,
        "asset_health_idx": 72,
        "hours_per_day": 20.3,
        "dwq_pct": 96,
    }


def _render_overview_banner():
    es = _get_executive_snapshot()
    zone = st.session_state.get("selected_zone")
    if isinstance(zone, dict):
        zone_label = zone.get("name") or "All zones"
    else:
        zone_label = zone or "All zones"
    start = st.session_state.get("start_month") or "Any"
    end = st.session_state.get("end_month") or "Now"

    st.title("Water Utility Performance Dashboard")
    st.caption(f"Latest performance overview for {zone_label} (Months: {start} – {end})")

def _filter_df_by_months(df: pd.DataFrame, col: str = "m") -> pd.DataFrame:
    sm = st.session_state.get("start_month")
    em = st.session_state.get("end_month")
    if (sm or em) and col in df.columns:
        try:
            d = pd.to_datetime(df[col], errors="coerce")
            if sm:
                d0 = pd.to_datetime(sm, errors="coerce")
                df = df[d >= d0]
            if em:
                d1 = pd.to_datetime(em, errors="coerce")
                df = df[d <= d1]
        except Exception:
            pass
    return df
def _dq_badge(ok: bool, partial: bool = False) -> str:
    if ok:
        return "<span style='color:#065f46'>Data quality: complete</span>"
    if partial:
        return "<span style='color:#b45309'>Data quality: partial</span>"
    return "<span style='color:#991b1b'>Data quality: missing</span>"

ZONES = [
    {"id": "n", "name": "North", "safeAccess": 58},
    {"id": "s", "name": "South", "safeAccess": 66},
    {"id": "e", "name": "East", "safeAccess": 74},
    {"id": "w", "name": "West", "safeAccess": 49},
    {"id": "c", "name": "Central", "safeAccess": 81},
    {"id": "se", "name": "South-East", "safeAccess": 63},
    {"id": "ne", "name": "North-East", "safeAccess": 71},
    {"id": "nw", "name": "North-West", "safeAccess": 55},
]

SERVICE_LADDER = [
    {"zone": "North", "safely_managed": 41, "basic": 28, "limited": 18, "unimproved": 9, "open_defecation": 4},
    {"zone": "South", "safely_managed": 45, "basic": 31, "limited": 14, "unimproved": 7, "open_defecation": 3},
    {"zone": "East", "safely_managed": 52, "basic": 29, "limited": 12, "unimproved": 5, "open_defecation": 2},
    {"zone": "West", "safely_managed": 33, "basic": 26, "limited": 23, "unimproved": 12, "open_defecation": 6},
    {"zone": "Central", "safely_managed": 64, "basic": 22, "limited": 8, "unimproved": 4, "open_defecation": 2},
]

PROGRESS = [
    {"m": "Jan", "v": 56},
    {"m": "Feb", "v": 57},
    {"m": "Mar", "v": 58},
    {"m": "Apr", "v": 58},
    {"m": "May", "v": 59},
    {"m": "Jun", "v": 60},
]

WQ_MONTHLY = [
    {"m": "Jan", "v": 95},
    {"m": "Feb", "v": 93},
    {"m": "Mar", "v": 96},
    {"m": "Apr", "v": 92},
    {"m": "May", "v": 94},
    {"m": "Jun", "v": 97},
]

BLOCKAGES = [
    {"m": "Jan", "v": 16}, {"m": "Feb", "v": 14}, {"m": "Mar", "v": 12},
    {"m": "Apr", "v": 10}, {"m": "May", "v": 13}, {"m": "Jun", "v": 11}
]

COMPLAINTS_VS_INTERRUP = [
    {"zone": "North", "complaints": 120, "interruptions": 15},
    {"zone": "South", "complaints": 90, "interruptions": 11},
    {"zone": "East", "complaints": 80, "interruptions": 9},
    {"zone": "West", "complaints": 150, "interruptions": 18},
    {"zone": "Central", "complaints": 70, "interruptions": 7},
]

REVENUE_OPEX = [
    {"year": 2020, "revenue": 98, "opex": 102, "coverage": 96},
    {"year": 2021, "revenue": 110, "opex": 108, "coverage": 102},
    {"year": 2022, "revenue": 118, "opex": 114, "coverage": 104},
    {"year": 2023, "revenue": 120, "opex": 118, "coverage": 102},
    {"year": 2024, "revenue": 130, "opex": 122, "coverage": 107},
]

NRW_COLLECTION = [
    {"year": 2020, "nrw": 42, "collection": 89},
    {"year": 2021, "nrw": 39, "collection": 90},
    {"year": 2022, "nrw": 37, "collection": 91},
    {"year": 2023, "nrw": 35, "collection": 92},
    {"year": 2024, "nrw": 33, "collection": 93},
]

FINANCIALS_TABLE = [
    {"metric": "Collection Efficiency %", "value": 92},
    {"metric": "Cost Coverage %", "value": 107},
    {"metric": "NRW %", "value": 33},
    {"metric": "Working Ratio", "value": 0.87},
    {"metric": "Tariff Gap %", "value": 8},
]


# ----------------------------- Utilities -----------------------------

def _conic_css(value: int, good_color: str = "#10b981", soft_color: str = "#e2e8f0") -> str:
    angle = max(0, min(100, int(value))) * 3.6
    return f"background: conic-gradient({good_color} {angle}deg, {soft_color} {angle}deg);"


def _download_button(filename: str, rows: List[dict], label: str = "Export CSV"):
    if not rows:
        return
    df = pd.DataFrame(rows)
    data = df.to_csv(index=False).encode("utf-8")
    st.download_button(label, data=data, file_name=filename, mime="text/csv")


# ----------------------------- Scenes -----------------------------

def _scene_page_path(scene_key: str) -> Optional[str]:
    mapping = {
        "exec": "Home.py",
        "access": "pages/2_🗺️_Access_&_Coverage.py",
        "quality": "pages/3_🛠️_Service_Quality_&_Reliability.py",
        "finance": "pages/4_💹_Financial_Health.py",
        "production": "pages/5_♻️_Production.py",
    }
    return mapping.get(scene_key)

def scene_executive():
    st.markdown("<div class='panel warn'>Coverage progressing slower than plan in 2 zones; review pipeline projects.</div>", unsafe_allow_html=True)

    es = _get_executive_snapshot()

    scorecards = [
        {"label": "Safely Managed Water", "value": es["water_safe_pct"], "target": 60, "scene": "access", "delta": +1.4},
        {"label": "Safely Managed Sanitation", "value": es["san_safe_pct"], "target": 70, "scene": "access", "delta": +0.8},
        {"label": "Collection Efficiency", "value": es["collection_eff_pct"], "target": 95, "scene": "finance", "delta": +2.1},
        {"label": "O&M Coverage", "value": es["om_coverage_pct"], "target": 150, "scene": "finance", "delta": +0.6},
        {"label": "NRW", "value": es["nrw_pct"], "target": 25, "scene": "finance", "delta": -0.6},
    ]
    st.markdown("<div class='scoregrid'>", unsafe_allow_html=True)
    cols = st.columns(4)
    for i, sc in enumerate(scorecards[:4]):
        with cols[i % 4]:
            gauge_style = _conic_css(sc["value"]) if sc.get("target") is None else _conic_css(sc["value"], "#10b981" if sc["value"] >= sc["target"] else "#f59e0b")
            st.markdown(
                f"""
                <div class='scorecard'>
                  <div class='gauge-wrap'>
                    <div class='gauge' style="{gauge_style}"><div class='gauge-inner'>{sc['value']}%</div></div>
                    <div>
                      <div style='font:600 13px Inter;color:#0f172a'>{sc['label']}</div>
                      <div class='meta'>Target: {sc['target']}% • Δ {abs(sc.get('delta',0))}%</div>
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            target = _scene_page_path(sc["scene"])
            if target:
                st.page_link(target, label="View details →", icon=None)
    st.markdown("</div>", unsafe_allow_html=True)

    # Second row gauges
    row2 = [
        {"label": "Asset Health Index", "value": es["asset_health_idx"], "target": 80, "scene": "finance"},
        {"label": "Hours of Supply", "value": es["hours_per_day"], "target": 22, "scene": "quality"},
        {"label": "DWQ", "value": es["dwq_pct"], "target": 95, "scene": "quality"},
    ]
    cols2 = st.columns(3)
    for i, sc in enumerate(row2):
        with cols2[i % 3]:
            unit = "%" if sc["label"] != "Hours of Supply" else "h/d"
            val = sc["value"] if unit == "%" else round(sc["value"], 1)
            gauge_style = _conic_css(sc["value"] if unit == "%" else min(100, sc["value"]*4))
            st.markdown(
                f"""
                <div class='scorecard'>
                  <div class='gauge-wrap'>
                    <div class='gauge' style="{gauge_style}"><div class='gauge-inner'>{val}{unit}</div></div>
                    <div>
                      <div style='font:600 13px Inter;color:#0f172a'>{sc['label']}</div>
                      <div class='meta'>Target: {sc['target']}{unit}</div>
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            target = _scene_page_path(sc["scene"])
            if target:
                st.page_link(target, label="View details →", icon=None)

    left, right = st.columns(2)
    with left:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<div style='display:flex;align-items:center;justify-content:space-between'><h3>Quick Stats</h3>", unsafe_allow_html=True)
        quick_stats = [
            {"metric": "Population Served", "value": "1.2M"},
            {"metric": "Active Connections", "value": "198k"},
            {"metric": "Active Staff", "value": "512"},
            {"metric": "Staff per 1k Conns", "value": "6.4"},
        ]
        _download_button("quick-stats.csv", quick_stats)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<div class='kgrid'>", unsafe_allow_html=True)
        for row in quick_stats:
            st.markdown(
                f"<div class='kitem'><span>{row['metric']}</span><span>{row['value']}</span></div>",
                unsafe_allow_html=True,
            )
        st.markdown("</div></div>", unsafe_allow_html=True)

    with right:
        recent = [
            {"when": "Today 10:12", "activity": "Zone West below DWQ target for May"},
            {"when": "Yesterday", "activity": "Tariff review submitted to regulator"},
            {"when": "2 days ago", "activity": "NRW taskforce created for Zone North"},
        ]
        st.markdown("<div class='panel'><h3>Recent Activity</h3>", unsafe_allow_html=True)
        _download_button("recent-activity.csv", recent)
        st.table(pd.DataFrame(recent))
        st.markdown("</div>", unsafe_allow_html=True)
@st.cache_data
def load_csv_data() -> Dict[str, pd.DataFrame]:
    """
    Read sewer and water access CSV datasets from disk and cache the resulting DataFrames.
    """
    csv_map = {
        "sewer": "Sewer Access Data.csv",
        "water": "Water Access Data.csv",
    }
    frames: Dict[str, pd.DataFrame] = {}
    for key, filename in csv_map.items():
        path = DATA_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        frames[key] = pd.read_csv(path)
    return frames


def _normalise_access_df(df: pd.DataFrame, *, prefix: str, extra_pct_cols: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Clean up access data: trim text, coerce numeric percentage columns, and ensure year is numeric.
    """
    frame = df.copy()
    if "zone" in frame.columns:
        frame["zone"] = frame["zone"].astype(str).str.strip()
    if "country" in frame.columns:
        frame["country"] = frame["country"].astype(str).str.strip()
    if "year" in frame.columns:
        frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype("Int64")
    pct_cols = [col for col in frame.columns if col.startswith(prefix) and col.endswith("_pct")]
    if extra_pct_cols:
        pct_cols.extend(col for col in extra_pct_cols if col in frame.columns)
    for col in pct_cols:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def _latest_snapshot(
    df: pd.DataFrame,
    *,
    rename_map: Dict[str, str],
    additional_columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Return the most recent record per (country, zone) pair and rename columns for clarity.
    """
    keys = [col for col in ("country", "zone") if col in df.columns]
    if not keys:
        keys = ["zone"]
    if "year" in df.columns:
        idx = df.groupby(keys)["year"].idxmax()
        latest = df.loc[idx].copy()
    else:
        latest = df.drop_duplicates(keys, keep="last").copy()
    keep_cols = set(keys + ["year"] + list(rename_map.keys()))
    if additional_columns:
        keep_cols.update(additional_columns)
    available_cols = [col for col in keep_cols if col in latest.columns]
    latest = latest[available_cols]
    latest = latest.rename(columns=rename_map)
    return latest


def _zone_identifier(country: Optional[str], zone: Optional[str]) -> str:
    base = f"{country or 'na'}-{zone or 'zone'}".lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-") or "zone"


@st.cache_data
def _prepare_service_data() -> Dict[str, Any]:
    """
    Prepare service quality data for visualization.
    Returns a dictionary containing processed service data including:
    - Full service data DataFrame
    - Latest snapshots by zone
    - Aggregated time series for key metrics
    """
    # Load service data
    service_path = DATA_DIR / "Service_data.csv"
    if not service_path.exists():
        raise FileNotFoundError(f"Service data file not found: {service_path}")
    
    df = pd.read_csv(service_path)
    
    # Clean and process data
    # Convert month and year to datetime
    df['date'] = pd.to_datetime(df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2) + '-01')
    df = df.sort_values('date')
    
    # Calculate derived metrics
    df['water_quality_rate'] = ((df['test_passed_chlorine'] / df['tests_conducted_chlorine'] * 100 +
                                df['tests_passed_ecoli'] / df['test_conducted_ecoli'] * 100) / 2)
    df['complaint_resolution_rate'] = (df['resolved'] / df['complaints'] * 100)
    df['nrw_rate'] = ((df['w_supplied'] - df['total_consumption']) / df['w_supplied'] * 100)
    df['sewer_coverage_rate'] = (df['sewer_connections'] / df['households'] * 100)
    
    # Get latest snapshot
    latest_by_zone = df.sort_values('date').groupby(['country', 'city', 'zone']).last().reset_index()
    
    # Aggregate time series
    time_series = df.groupby('date').agg({
        'w_supplied': 'sum',
        'total_consumption': 'sum',
        'metered': 'sum',
        'water_quality_rate': 'mean',
        'complaint_resolution_rate': 'mean',
        'nrw_rate': 'mean',
        'sewer_coverage_rate': 'mean',
        'public_toilets': 'sum'
    }).reset_index()
    
    return {
        "full_data": df,
        "latest_by_zone": latest_by_zone,
        "time_series": time_series,
        "zones": sorted(df['zone'].unique()),
        "cities": sorted(df['city'].unique()),
        "countries": sorted(df['country'].unique())
    }

def _prepare_access_data() -> Dict[str, Any]:
    """
    Prepare derived access datasets for the Access & Coverage scene.
    Returns cached water/sewer snapshots, full histories, and zone-level summaries.
    """
    csv_data = load_csv_data()
    water_df = _normalise_access_df(csv_data["water"], prefix="w_", extra_pct_cols=["municipal_coverage"])
    sewer_df = _normalise_access_df(csv_data["sewer"], prefix="s_")

    water_latest = _latest_snapshot(
        water_df,
        rename_map={
            "year": "water_year",
            "w_safely_managed_pct": "water_safely_pct",
            "w_basic_pct": "water_basic_pct",
            "w_limited_pct": "water_limited_pct",
            "w_unimproved_pct": "water_unimproved_pct",
            "surface_water_pct": "water_surface_pct",
            "municipal_coverage": "water_municipal_coverage",
        },
        additional_columns=["municipal_coverage", "w_safely_managed", "w_basic", "w_limited", "w_unimproved", "surface_water"],
    )
    sewer_latest = _latest_snapshot(
        sewer_df,
        rename_map={
            "year": "sewer_year",
            "s_safely_managed_pct": "sewer_safely_pct",
            "s_basic_pct": "sewer_basic_pct",
            "s_limited_pct": "sewer_limited_pct",
            "s_unimproved_pct": "sewer_unimproved_pct",
            "open_def_pct": "sewer_open_def_pct",
        },
        additional_columns=["s_safely_managed", "s_basic", "s_limited", "s_unimproved", "open_def"],
    )

    merge_keys = [col for col in ("country", "zone") if col in water_latest.columns and col in sewer_latest.columns]
    if not merge_keys:
        merge_keys = ["zone"]
    zones_df = water_latest.merge(sewer_latest, on=merge_keys, how="outer", suffixes=("", "_dup"))
    if "country_dup" in zones_df.columns and "country" not in merge_keys:
        zones_df["country"] = zones_df["country"].fillna(zones_df["country_dup"])
        zones_df = zones_df.drop(columns=["country_dup"])
    zones_df["safeAccess"] = zones_df[["water_safely_pct", "sewer_safely_pct"]].mean(axis=1, skipna=True)
    zone_records: List[Dict[str, Any]] = []
    for _, row in zones_df.sort_values(by=[col for col in ("country", "zone") if col in zones_df.columns]).iterrows():
        record = {
            "id": _zone_identifier(row.get("country"), row.get("zone")),
            "name": row.get("zone"),
            "country": row.get("country"),
            "safeAccess": float(row["safeAccess"]) if pd.notna(row.get("safeAccess")) else None,
            "water_safely_pct": float(row["water_safely_pct"]) if pd.notna(row.get("water_safely_pct")) else None,
            "sewer_safely_pct": float(row["sewer_safely_pct"]) if pd.notna(row.get("sewer_safely_pct")) else None,
            "water_year": int(row["water_year"]) if pd.notna(row.get("water_year")) else None,
            "sewer_year": int(row["sewer_year"]) if pd.notna(row.get("sewer_year")) else None,
        }
        zone_records.append(record)

    return {
        "water_full": water_df,
        "sewer_full": sewer_df,
        "water_latest": water_latest,
        "sewer_latest": sewer_latest,
        "zones": zone_records,
    }

def load_csv_data() -> Dict[str, pd.DataFrame]:
    """
    Read sewer and water access CSV datasets from disk and cache the resulting DataFrames.
    """
    csv_map = {
        "sewer": "Sewer Access Data.csv",
        "water": "Water Access Data.csv",
    }
    frames: Dict[str, pd.DataFrame] = {}
    for key, filename in csv_map.items():
        path = DATA_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        frames[key] = pd.read_csv(path)
    return frames


def _normalise_access_df(df: pd.DataFrame, *, prefix: str, extra_pct_cols: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Clean up access data: trim text, coerce numeric percentage columns, and ensure year is numeric.
    """
    frame = df.copy()
    if "zone" in frame.columns:
        frame["zone"] = frame["zone"].astype(str).str.strip()
    if "country" in frame.columns:
        frame["country"] = frame["country"].astype(str).str.strip()
    if "year" in frame.columns:
        frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype("Int64")
    pct_cols = [col for col in frame.columns if col.startswith(prefix) and col.endswith("_pct")]
    if extra_pct_cols:
        pct_cols.extend(col for col in extra_pct_cols if col in frame.columns)
    for col in pct_cols:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def _latest_snapshot(
    df: pd.DataFrame,
    *,
    rename_map: Dict[str, str],
    additional_columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Return the most recent record per (country, zone) pair and rename columns for clarity.
    """
    keys = [col for col in ("country", "zone") if col in df.columns]
    if not keys:
        keys = ["zone"]
    if "year" in df.columns:
        idx = df.groupby(keys)["year"].idxmax()
        latest = df.loc[idx].copy()
    else:
        latest = df.drop_duplicates(keys, keep="last").copy()
    keep_cols = set(keys + ["year"] + list(rename_map.keys()))
    if additional_columns:
        keep_cols.update(additional_columns)
    available_cols = [col for col in keep_cols if col in latest.columns]
    latest = latest[available_cols]
    latest = latest.rename(columns=rename_map)
    return latest


def _zone_identifier(country: Optional[str], zone: Optional[str]) -> str:
    base = f"{country or 'na'}-{zone or 'zone'}".lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-") or "zone"


@st.cache_data
def _prepare_service_data() -> Dict[str, Any]:
    """
    Prepare service quality data for visualization.
    Returns a dictionary containing processed service data including:
    - Full service data DataFrame
    - Latest snapshots by zone
    - Aggregated time series for key metrics
    """
    # Load service data
    service_path = DATA_DIR / "Service_data.csv"
    if not service_path.exists():
        raise FileNotFoundError(f"Service data file not found: {service_path}")
    
    df = pd.read_csv(service_path)
    
    # Clean and process data
    # Convert month and year to datetime
    df['date'] = pd.to_datetime(df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2) + '-01')
    df = df.sort_values('date')
    
    # Calculate derived metrics
    df['water_quality_rate'] = ((df['test_passed_chlorine'] / df['tests_conducted_chlorine'] * 100 +
                                df['tests_passed_ecoli'] / df['test_conducted_ecoli'] * 100) / 2)
    df['complaint_resolution_rate'] = (df['resolved'] / df['complaints'] * 100)
    df['nrw_rate'] = ((df['w_supplied'] - df['total_consumption']) / df['w_supplied'] * 100)
    df['sewer_coverage_rate'] = (df['sewer_connections'] / df['households'] * 100)
    
    # Get latest snapshot
    latest_by_zone = df.sort_values('date').groupby(['country', 'city', 'zone']).last().reset_index()
    
    # Aggregate time series
    time_series = df.groupby('date').agg({
        'w_supplied': 'sum',
        'total_consumption': 'sum',
        'metered': 'sum',
        'water_quality_rate': 'mean',
        'complaint_resolution_rate': 'mean',
        'nrw_rate': 'mean',
        'sewer_coverage_rate': 'mean',
        'public_toilets': 'sum'
    }).reset_index()
    
    return {
        "full_data": df,
        "latest_by_zone": latest_by_zone,
        "time_series": time_series,
        "zones": sorted(df['zone'].unique()),
        "cities": sorted(df['city'].unique()),
        "countries": sorted(df['country'].unique())
    }

def _prepare_access_data() -> Dict[str, Any]:
    """
    Prepare derived access datasets for the Access & Coverage scene.
    Returns cached water/sewer snapshots, full histories, and zone-level summaries.
    """
    csv_data = load_csv_data()
    water_df = _normalise_access_df(csv_data["water"], prefix="w_", extra_pct_cols=["municipal_coverage"])
    sewer_df = _normalise_access_df(csv_data["sewer"], prefix="s_")

    water_latest = _latest_snapshot(
        water_df,
        rename_map={
            "year": "water_year",
            "w_safely_managed_pct": "water_safely_pct",
            "w_basic_pct": "water_basic_pct",
            "w_limited_pct": "water_limited_pct",
            "w_unimproved_pct": "water_unimproved_pct",
            "surface_water_pct": "water_surface_pct",
            "municipal_coverage": "water_municipal_coverage",
        },
        additional_columns=["municipal_coverage", "w_safely_managed", "w_basic", "w_limited", "w_unimproved", "surface_water"],
    )
    sewer_latest = _latest_snapshot(
        sewer_df,
        rename_map={
            "year": "sewer_year",
            "s_safely_managed_pct": "sewer_safely_pct",
            "s_basic_pct": "sewer_basic_pct",
            "s_limited_pct": "sewer_limited_pct",
            "s_unimproved_pct": "sewer_unimproved_pct",
            "open_def_pct": "sewer_open_def_pct",
        },
        additional_columns=["s_safely_managed", "s_basic", "s_limited", "s_unimproved", "open_def"],
    )

    merge_keys = [col for col in ("country", "zone") if col in water_latest.columns and col in sewer_latest.columns]
    if not merge_keys:
        merge_keys = ["zone"]
    zones_df = water_latest.merge(sewer_latest, on=merge_keys, how="outer", suffixes=("", "_dup"))
    if "country_dup" in zones_df.columns and "country" not in merge_keys:
        zones_df["country"] = zones_df["country"].fillna(zones_df["country_dup"])
        zones_df = zones_df.drop(columns=["country_dup"])
    zones_df["safeAccess"] = zones_df[["water_safely_pct", "sewer_safely_pct"]].mean(axis=1, skipna=True)
    zone_records: List[Dict[str, Any]] = []
    for _, row in zones_df.sort_values(by=[col for col in ("country", "zone") if col in zones_df.columns]).iterrows():
        record = {
            "id": _zone_identifier(row.get("country"), row.get("zone")),
            "name": row.get("zone"),
            "country": row.get("country"),
            "safeAccess": float(row["safeAccess"]) if pd.notna(row.get("safeAccess")) else None,
            "water_safely_pct": float(row["water_safely_pct"]) if pd.notna(row.get("water_safely_pct")) else None,
            "sewer_safely_pct": float(row["sewer_safely_pct"]) if pd.notna(row.get("sewer_safely_pct")) else None,
            "water_year": int(row["water_year"]) if pd.notna(row.get("water_year")) else None,
            "sewer_year": int(row["sewer_year"]) if pd.notna(row.get("sewer_year")) else None,
        }
        zone_records.append(record)

    return {
        "water_full": water_df,
        "sewer_full": sewer_df,
        "water_latest": water_latest,
        "sewer_latest": sewer_latest,
        "zones": zone_records,
    }


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
            st.dataframe(sw_ranges.round(1), use_container_width=True)
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
            st.dataframe(priority_display, use_container_width=True)
            st.caption("Sewer gap = unimproved % + open defecation % (sewer).")
    st.markdown("</div>", unsafe_allow_html=True)

def scene_quality():
    """
    Service Quality & Reliability scene - matches water_service_dashboard.tsx design
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
        """Prepare comprehensive data export for utility managers"""
        from datetime import datetime
        import io
        
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
        export_ts = filtered_df.copy()
        export_ts = export_ts.sort_values('date')
        
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
        if 'Water_Supplied_m3' in export_ts_selected.columns and 'Metered_Connections' in export_ts_selected.columns:
            export_ts_selected['Metered_Percentage'] = (export_ts_selected['Metered_Connections'] / export_ts_selected['Water_Supplied_m3'] * 100).round(2)
        
        if 'Chlorine_Tests_Passed' in export_ts_selected.columns and 'Chlorine_Tests_Conducted' in export_ts_selected.columns:
            export_ts_selected['Chlorine_Pass_Rate_Pct'] = (export_ts_selected['Chlorine_Tests_Passed'] / export_ts_selected['Chlorine_Tests_Conducted'] * 100).round(2)
        
        if 'Ecoli_Tests_Passed' in export_ts_selected.columns and 'Ecoli_Tests_Conducted' in export_ts_selected.columns:
            export_ts_selected['Ecoli_Pass_Rate_Pct'] = (export_ts_selected['Ecoli_Tests_Passed'] / export_ts_selected['Ecoli_Tests_Conducted'] * 100).round(2)
        
        if 'Complaints_Resolved' in export_ts_selected.columns and 'Complaints_Received' in export_ts_selected.columns:
            export_ts_selected['Resolution_Rate_Pct'] = (export_ts_selected['Complaints_Resolved'] / export_ts_selected['Complaints_Received'] * 100).round(2)
        
        if 'Wastewater_Treated_m3' in export_ts_selected.columns and 'Wastewater_Collected_m3' in export_ts_selected.columns:
            export_ts_selected['WW_Treatment_Rate_Pct'] = (export_ts_selected['Wastewater_Treated_m3'] / export_ts_selected['Wastewater_Collected_m3'] * 100).round(2)
        
        if 'Sewer_Connections' in export_ts_selected.columns and 'Total_Households' in export_ts_selected.columns:
            export_ts_selected['Sewer_Coverage_Pct'] = (export_ts_selected['Sewer_Connections'] / export_ts_selected['Total_Households'] * 100).round(2)
        
        # Create summary statistics dataframe
        summary_data = {
            'Metric': [
                'Reporting Period',
                'Location',
                'Total Water Supplied (m³)',
                'Total Water Consumed (m³)',
                'Average Metered Coverage (%)',
                'Chlorine Pass Rate (%)',
                'E.coli Pass Rate (%)',
                'Overall Quality Score (/100)',
                'Total Complaints Received',
                'Total Complaints Resolved',
                'Complaint Resolution Rate (%)',
                'Average Resolution Time (days)',
                'Wastewater Treatment Rate (%)',
                'Average Sewer Coverage (%)',
                'Data Export Date'
            ],
            'Value': [
                f"{export_ts_selected['Date'].min()} to {export_ts_selected['Date'].max()}",
                ' > '.join(location_parts) if location_parts else 'All Locations',
                f"{export_ts_selected.get('Water_Supplied_m3', pd.Series([0])).sum():,.0f}",
                f"{export_ts_selected.get('Water_Consumed_m3', pd.Series([0])).sum():,.0f}",
                f"{export_ts_selected.get('Metered_Percentage', pd.Series([0])).mean():.2f}",
                f"{export_ts_selected.get('Chlorine_Pass_Rate_Pct', pd.Series([0])).mean():.2f}",
                f"{export_ts_selected.get('Ecoli_Pass_Rate_Pct', pd.Series([0])).mean():.2f}",
                f"{(export_ts_selected.get('Chlorine_Pass_Rate_Pct', pd.Series([0])).mean() + export_ts_selected.get('Ecoli_Pass_Rate_Pct', pd.Series([0])).mean()) / 2:.2f}",
                f"{export_ts_selected.get('Complaints_Received', pd.Series([0])).sum():.0f}",
                f"{export_ts_selected.get('Complaints_Resolved', pd.Series([0])).sum():.0f}",
                f"{export_ts_selected.get('Resolution_Rate_Pct', pd.Series([0])).mean():.2f}",
                f"{export_ts_selected.get('Avg_Resolution_Days', pd.Series([0])).mean():.2f}",
                f"{export_ts_selected.get('WW_Treatment_Rate_Pct', pd.Series([0])).mean():.2f}",
                f"{export_ts_selected.get('Sewer_Coverage_Pct', pd.Series([0])).mean():.2f}",
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        
        # Combine both dataframes into a single CSV with clear sections
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
    
    # Calculate derived metrics
    time_series['metered_pct'] = (time_series['metered'] / time_series['w_supplied'] * 100).fillna(0)
    time_series['chlorine_pass_rate'] = (time_series['test_passed_chlorine'] / time_series['tests_conducted_chlorine'] * 100).fillna(0)
    time_series['ecoli_pass_rate'] = (time_series['tests_passed_ecoli'] / time_series['test_conducted_ecoli'] * 100).fillna(0)
    time_series['resolution_rate'] = (time_series['resolved'] / time_series['complaints'] * 100).fillna(0)
    time_series['ww_treatment_rate'] = (time_series['ww_treated'] / time_series['ww_collected'] * 100).fillna(0)
    time_series['sewer_coverage'] = (time_series['sewer_connections'] / time_series['households'] * 100).fillna(0)
    
    # Aggregate metrics for KPIs
    total_supplied = time_series['w_supplied'].sum()
    total_consumption = time_series['total_consumption'].sum()
    total_metered = time_series['metered'].sum()
    avg_metered_pct = (total_metered / total_supplied * 100) if total_supplied > 0 else 0
    
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
    
    # Main content grid - Left column (charts) and Right column (compliance)
    left_col, right_col = st.columns([2, 1])
    
    with left_col:
        # Water Supply & Distribution Section
        with st.expander("💧 Water Supply & Distribution", expanded=True):
            # Supply vs Consumption - Area + Line chart
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
                margin=dict(l=0, r=0, t=30, b=0),
                height=280,
                showlegend=True,
                legend=dict(
                    orientation="h", 
                    yanchor="bottom", 
                    y=1.02, 
                    x=0,
                    bgcolor='rgba(255,255,255,0.8)',
                    bordercolor='rgba(148,163,184,0.2)',
                    borderwidth=1
                ),
                yaxis_title="Volume (K m³)",
                yaxis=dict(
                    gridcolor='rgba(148,163,184,0.1)',
                    showline=True,
                    linecolor='rgba(148,163,184,0.2)',
                    linewidth=1
                ),
                xaxis=dict(
                    gridcolor='rgba(148,163,184,0.1)',
                    showline=True,
                    linecolor='rgba(148,163,184,0.2)',
                    linewidth=1
                ),
                hovermode='x unified',
                plot_bgcolor='rgba(248,250,252,0.5)',
                paper_bgcolor='white',
                font=dict(family='Inter, system-ui, sans-serif', size=11, color='#475569')
            )
            st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})
            
            # Metered percentage trend
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                x=time_series['date'],
                y=time_series['metered_pct'],
                name='Metered Connections',
                line=dict(color='#8b5cf6', width=3),
                mode='lines+markers',
                marker=dict(size=6, symbol='circle', color='#8b5cf6', line=dict(width=2, color='white')),
                fill='tozeroy',
                fillcolor='rgba(139, 92, 246, 0.1)',
                hovertemplate='<b>Metered</b><br>%{y:.1f}%<extra></extra>'
            ))
            # Add target line
            fig2.add_hline(
                y=90, 
                line_dash="dash", 
                line_color="#94a3b8", 
                line_width=2,
                annotation_text="Target: 90%",
                annotation_position="right",
                annotation=dict(font_size=10, font_color="#64748b")
            )
            fig2.update_layout(
                margin=dict(l=0, r=0, t=30, b=0),
                height=240,
                yaxis=dict(
                    range=[0, 100], 
                    title="Coverage (%)",
                    gridcolor='rgba(148,163,184,0.1)',
                    showline=True,
                    linecolor='rgba(148,163,184,0.2)',
                    linewidth=1
                ),
                xaxis=dict(
                    gridcolor='rgba(148,163,184,0.1)',
                    showline=True,
                    linecolor='rgba(148,163,184,0.2)',
                    linewidth=1
                ),
                showlegend=True,
                legend=dict(
                    orientation="h", 
                    yanchor="bottom", 
                    y=1.02, 
                    x=0,
                    bgcolor='rgba(255,255,255,0.8)',
                    bordercolor='rgba(148,163,184,0.2)',
                    borderwidth=1
                ),
                hovermode='x unified',
                plot_bgcolor='rgba(248,250,252,0.5)',
                paper_bgcolor='white',
                font=dict(family='Inter, system-ui, sans-serif', size=11, color='#475569')
            )
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
            
            # Mini stats below chart using HTML to avoid nesting
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
        
        # Water Quality & Testing Section
        with st.expander("🧪 Water Quality & Testing", expanded=True):
            # Chlorine and E.coli pass rates - Dual area chart
            fig3 = go.Figure()
            fig3.add_trace(go.Scatter(
                x=time_series['date'],
                y=time_series['chlorine_pass_rate'],
                fill='tozeroy',
                name='Chlorine Pass Rate',
                line=dict(color='#3b82f6', width=3),
                fillcolor='rgba(59, 130, 246, 0.2)',
                hovertemplate='<b>Chlorine</b><br>%{y:.1f}%<extra></extra>'
            ))
            fig3.add_trace(go.Scatter(
                x=time_series['date'],
                y=time_series['ecoli_pass_rate'],
                fill='tozeroy',
                name='E.coli Pass Rate',
                line=dict(color='#10b981', width=3),
                fillcolor='rgba(16, 185, 129, 0.2)',
                hovertemplate='<b>E.coli</b><br>%{y:.1f}%<extra></extra>'
            ))
            # Add target line at 95%
            fig3.add_hline(
                y=95, 
                line_dash="dash", 
                line_color="#94a3b8", 
                line_width=2,
                annotation_text="Target: 95%",
                annotation_position="right",
                annotation=dict(font_size=10, font_color="#64748b")
            )
            fig3.update_layout(
                margin=dict(l=0, r=0, t=30, b=0),
                height=280,
                yaxis=dict(
                    range=[0, 100], 
                    title="Pass Rate (%)",
                    gridcolor='rgba(148,163,184,0.1)',
                    showline=True,
                    linecolor='rgba(148,163,184,0.2)',
                    linewidth=1
                ),
                xaxis=dict(
                    gridcolor='rgba(148,163,184,0.1)',
                    showline=True,
                    linecolor='rgba(148,163,184,0.2)',
                    linewidth=1
                ),
                showlegend=True,
                legend=dict(
                    orientation="h", 
                    yanchor="bottom", 
                    y=1.02, 
                    x=0,
                    bgcolor='rgba(255,255,255,0.8)',
                    bordercolor='rgba(148,163,184,0.2)',
                    borderwidth=1
                ),
                hovermode='x unified',
                plot_bgcolor='rgba(248,250,252,0.5)',
                paper_bgcolor='white',
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
        
        # Sanitation & Wastewater Section
        with st.expander("♻️ Sanitation & Wastewater", expanded=True):
            # Sewer coverage and public toilets - Combined bar and line
            fig4 = go.Figure()
            fig4.add_trace(go.Bar(
                x=time_series['date'],
                y=time_series['sewer_coverage'],
                name='Sewer Coverage',
                marker=dict(
                    color=time_series['sewer_coverage'],
                    colorscale=[[0, '#dbeafe'], [0.5, '#93c5fd'], [1, '#3b82f6']],
                    line=dict(width=0)
                ),
                hovertemplate='<b>Sewer Coverage</b><br>%{y:.1f}%<extra></extra>'
            ))
            fig4.add_trace(go.Scatter(
                x=time_series['date'],
                y=time_series['public_toilets'],
                name='Public Toilets',
                line=dict(color='#10b981', width=3),
                mode='lines+markers',
                marker=dict(size=6, color='#10b981', line=dict(width=2, color='white')),
                yaxis='y2',
                hovertemplate='<b>Toilets</b><br>%{y:.0f}<extra></extra>'
            ))
            fig4.update_layout(
                margin=dict(l=0, r=0, t=30, b=0),
                height=280,
                showlegend=True,
                legend=dict(
                    orientation="h", 
                    yanchor="bottom", 
                    y=1.02, 
                    x=0,
                    bgcolor='rgba(255,255,255,0.8)',
                    bordercolor='rgba(148,163,184,0.2)',
                    borderwidth=1
                ),
                yaxis=dict(
                    title="Sewer Coverage (%)",
                    gridcolor='rgba(148,163,184,0.1)',
                    showline=True,
                    linecolor='rgba(148,163,184,0.2)',
                    linewidth=1
                ),
                yaxis2=dict(
                    title="Public Toilets", 
                    overlaying='y', 
                    side='right',
                    gridcolor='rgba(148,163,184,0.05)',
                    showline=True,
                    linecolor='rgba(148,163,184,0.2)',
                    linewidth=1
                ),
                xaxis=dict(
                    gridcolor='rgba(148,163,184,0.1)',
                    showline=True,
                    linecolor='rgba(148,163,184,0.2)',
                    linewidth=1
                ),
                hovermode='x unified',
                plot_bgcolor='rgba(248,250,252,0.5)',
                paper_bgcolor='white',
                font=dict(family='Inter, system-ui, sans-serif', size=11, color='#475569')
            )
            st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False})
            
            # WW treatment rate - Bar chart with gradient
            fig5 = go.Figure()
            fig5.add_trace(go.Bar(
                x=time_series['date'],
                y=time_series['ww_treatment_rate'],
                name='Wastewater Treatment',
                marker=dict(
                    color=time_series['ww_treatment_rate'],
                    colorscale=[[0, '#fef3c7'], [0.5, '#c084fc'], [1, '#8b5cf6']],
                    line=dict(width=0)
                ),
                hovertemplate='<b>Treatment Rate</b><br>%{y:.1f}%<extra></extra>'
            ))
            # Add target line at 80%
            fig5.add_hline(
                y=80, 
                line_dash="dash", 
                line_color="#94a3b8", 
                line_width=2,
                annotation_text="Target: 80%",
                annotation_position="right",
                annotation=dict(font_size=10, font_color="#64748b")
            )
            fig5.update_layout(
                margin=dict(l=0, r=0, t=30, b=0),
                height=240,
                yaxis=dict(
                    range=[0, 100], 
                    title="Treatment Rate (%)",
                    gridcolor='rgba(148,163,184,0.1)',
                    showline=True,
                    linecolor='rgba(148,163,184,0.2)',
                    linewidth=1
                ),
                xaxis=dict(
                    gridcolor='rgba(148,163,184,0.1)',
                    showline=True,
                    linecolor='rgba(148,163,184,0.2)',
                    linewidth=1
                ),
                showlegend=True,
                legend=dict(
                    orientation="h", 
                    yanchor="bottom", 
                    y=1.02, 
                    x=0,
                    bgcolor='rgba(255,255,255,0.8)',
                    bordercolor='rgba(148,163,184,0.2)',
                    borderwidth=1
                ),
                hovermode='x unified',
                plot_bgcolor='rgba(248,250,252,0.5)',
                paper_bgcolor='white',
                font=dict(family='Inter, system-ui, sans-serif', size=11, color='#475569')
            )
            st.plotly_chart(fig5, use_container_width=True, config={"displayModeBar": False})
    
    with right_col:
        # Regulatory Compliance Section - Remove outer container
        st.markdown("""
            <div style='display:flex;align-items:center;gap:10px;margin-bottom:18px'>
                <span style='font-size:22px'>📋</span>
                <h3 style='margin:0;font:600 16px Inter,system-ui,sans-serif;color:#0f172a'>Regulatory Compliance</h3>
            </div>
        """, unsafe_allow_html=True)
        
        # Progress bars for compliance metrics with enhanced styling
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
            # bg_color = "rgba(16,185,129,0.1)" if pct >= 95 else "rgba(245,158,11,0.1)" if pct >= 80 else "rgba(239,68,68,0.1)"
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
                        <div style='width:{min(pct, 100):.0f}%;
                                    height:8px;
                                    background:linear-gradient(90deg, {color}dd, {color});
                                    border-radius:4px;
                                    transition:width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
                                    box-shadow:0 0 8px {color}66'></div>
                    </div>
                    <div style='font:400 9px sans-serif;color:#94a3b8;margin-top:4px;text-align:right'>
                        Target: {metric['target']}% | Gap: {max(0, metric['target'] - metric['value']):.1f}%
                    </div>
                </div>
            """, unsafe_allow_html=True)
        
        # Complaints management summary - Enhanced card
        st.markdown(f"""
            <div style='background:linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
                        border:1px solid #93c5fd;
                        border-radius:12px;
                        padding:16px;
                        margin-top:12px;
                        box-shadow:0 2px 4px rgba(59,130,246,0.1)'>
                <div style='display:flex;align-items:center;gap:8px;margin-bottom:12px'>
                    <span style='font-size:18px'>📞</span>
                    <div style='font:600 12px Inter,sans-serif;color:#1e3a8a'>Complaints Management</div>
                </div>
                <div style='display:grid;grid-template-columns:1fr 1fr;gap:12px'>
                    <div style='background:white;border-radius:8px;padding:12px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.1)'>
                        <div style='font:700 24px Inter,sans-serif;color:#1e40af;margin-bottom:4px'>{total_complaints:.0f}</div>
                        <div style='font:400 10px sans-serif;color:#3b82f6;text-transform:uppercase;letter-spacing:0.5px'>Received</div>
                    </div>
                    <div style='background:white;border-radius:8px;padding:12px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.1)'>
                        <div style='font:700 24px Inter,sans-serif;color:#047857;margin-bottom:4px'>{total_resolved:.0f}</div>
                        <div style='font:400 10px sans-serif;color:#10b981;text-transform:uppercase;letter-spacing:0.5px'>Resolved</div>
                    </div>
                </div>
                <div style='margin-top:12px;padding-top:12px;border-top:1px solid #bfdbfe;text-align:center'>
                    <div style='font:600 14px Inter,sans-serif;color:#1e40af'>{resolution_rate:.1f}%</div>
                    <div style='font:400 9px sans-serif;color:#3b82f6;text-transform:uppercase;letter-spacing:0.5px'>Resolution Rate</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Remove closing div tag since we removed the container
        
        # Priority Alerts Section - Remove outer container
        st.markdown("""
            <div style='display:flex;align-items:center;gap:10px;margin-bottom:18px;margin-top:24px'>
                <span style='font-size:22px'>🔔</span>
                <h3 style='margin:0;font:600 16px Inter,system-ui,sans-serif;color:#0f172a'>Priority Alerts</h3>
            </div>
        """, unsafe_allow_html=True)
        
        # Generate alerts based on thresholds
        alerts = []
        
        if ww_treatment_rate < 80:
            alerts.append({
                "type": "warning",
                "icon": "⚠️",
                "title": "WW Treatment Below Target",
                "detail": f"{ww_treatment_rate:.1f}% vs 80% target",
                "color": "#fef3c7",
                "border": "#fbbf24",
                "text": "#92400e",
                "priority": "high"
            })
        
        if avg_metered_pct < 80:
            alerts.append({
                "type": "info",
                "icon": "ℹ️",
                "title": "Metering Coverage Low",
                "detail": f"{avg_metered_pct:.1f}% metered connections",
                "color": "#dbeafe",
                "border": "#60a5fa",
                "text": "#1e3a8a",
                "priority": "medium"
            })
        
        if quality_score >= 90:
            alerts.append({
                "type": "success",
                "icon": "✅",
                "title": "Quality Compliance Excellent",
                "detail": f"{quality_score:.1f}% exceeds standards",
                "color": "#d1fae5",
                "border": "#34d399",
                "text": "#065f46",
                "priority": "info"
            })
        
        if resolution_rate < 80:
            alerts.append({
                "type": "warning",
                "icon": "⏰",
                "title": "Low Resolution Rate",
                "detail": f"{resolution_rate:.1f}% complaints resolved",
                "color": "#fef3c7",
                "border": "#fbbf24",
                "text": "#92400e",
                "priority": "high"
            })
        
        if not alerts:
            st.markdown("""
                <div style='background:linear-gradient(135deg, #f0fdf4, #dcfce7);
                            border:1px solid #86efac;
                            padding:16px;
                            border-radius:12px;
                            text-align:center;
                            box-shadow:0 2px 4px rgba(22,101,52,0.1)'>
                    <div style='font-size:32px;margin-bottom:8px'>✅</div>
                    <div style='font:600 13px Inter,sans-serif;color:#166534;margin-bottom:4px'>All Systems Operational</div>
                    <div style='font:400 11px sans-serif;color:#16a34a'>No alerts at this time</div>
                </div>
            """, unsafe_allow_html=True)
        else:
            for alert in alerts:
                priority_badge = f"<span style='background:{alert['border']};color:white;padding:2px 6px;border-radius:10px;font:600 8px sans-serif;text-transform:uppercase;letter-spacing:0.5px'>{alert['priority']}</span>"
                st.markdown(f"""
                    <div style='background:{alert['color']};
                                border-left:4px solid {alert['border']};
                                border-radius:10px;
                                padding:14px;
                                margin-bottom:10px;
                                box-shadow:0 2px 4px rgba(0,0,0,0.08);
                                transition:all 0.2s ease'>
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
        
        # Remove closing div tag since we removed the container
    
    # outer wrapper removed above; alerts rendered as individual inline blocks


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


def scene_governance():
    st.markdown("<div class='panel'><h3>Compliance & Providers</h3>", unsafe_allow_html=True)
    gov = _load_json("governance.json") or {
        "active_providers": 42, "total_providers": 50, "active_licensed": 36, "total_licensed": 40,
        "wtp_inspected_count": 18, "invest_in_hc_pct": 2.6,
        "trained": {"male": 120, "female": 86}, "staff_total": 512,
        "compliance": {"license": True, "tariff": True, "levy": False, "reporting": True},
    }
    comp = gov.get("compliance", {})
    cols = st.columns(4)
    cols[0].metric("License valid", "Yes" if comp.get("license") else "No")
    cols[1].metric("Tariff valid", "Yes" if comp.get("tariff") else "No")
    cols[2].metric("Levy paid", "Yes" if comp.get("levy") else "No")
    cols[3].metric("Reporting on time", "Yes" if comp.get("reporting") else "No")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><h3>Providers & Inspections</h3>", unsafe_allow_html=True)
    pcols = st.columns(3)
    pcols[0].metric("Active providers %", f"{(gov['active_providers']/max(1,gov['total_providers']))*100:.1f}")
    pcols[1].metric("Active licensed %", f"{(gov['active_licensed']/max(1,gov['total_licensed']))*100:.1f}")
    pcols[2].metric("WTP inspected", gov["wtp_inspected_count"])
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><h3>Human Capital</h3>", unsafe_allow_html=True)
    hcols = st.columns(3)
    hcols[0].metric("Invest in HC %", gov["invest_in_hc_pct"])
    hcols[1].metric("Staff trained (M/F)", f"{gov['trained']['male']}/{gov['trained']['female']}")
    hcols[2].metric("Staff total", gov["staff_total"])
    st.markdown("</div>", unsafe_allow_html=True)


def scene_sector():
    st.markdown("<div class='panel'><h3>Sector Budget</h3>", unsafe_allow_html=True)
    se = _load_json("sector_environment.json") or {
        "year": 2024,
        "budget": {"water_pct": 1.9, "sanitation_pct": 1.1, "wash_disbursed_pct": 72},
        "water_stress_pct": 54,
        "water_use_efficiency": {"agri_usd_per_m3": 1.8, "manufacturing_usd_per_m3": 14.2},
        "disaster_loss_usd_m": 63.5,
    }
    b = se["budget"]
    dfb = pd.DataFrame({"metric": ["Water budget %", "Sanitation budget %", "WASH disbursed %"], "value": [b["water_pct"], b["sanitation_pct"], b["wash_disbursed_pct"]]})
    figb = px.bar(dfb, x="metric", y="value", color="metric")
    st.plotly_chart(figb, use_container_width=True, config={"displayModeBar": False}, key="sector_budget")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><h3>Environment</h3>", unsafe_allow_html=True)
    ecols = st.columns(3)
    ecols[0].metric("Water stress % (↓)", se["water_stress_pct"])
    ecols[1].metric("WUE Agri $/m³", se["water_use_efficiency"]["agri_usd_per_m3"])
    ecols[2].metric("WUE Mfg $/m³", se["water_use_efficiency"]["manufacturing_usd_per_m3"])
    st.metric("Disaster loss (USD m)", se["disaster_loss_usd_m"])
    st.markdown("</div>", unsafe_allow_html=True)


# ----------------------------- App entry -----------------------------

def render_uhn_dashboard():
    st.set_page_config(page_title="Water Utility Performance Dashboard", page_icon="💧", layout="wide")
    _inject_styles()
    _sidebar_filters()

    st.markdown("<div class='shell'>", unsafe_allow_html=True)
    _render_overview_banner()

    st.markdown("<div class='content-area'>", unsafe_allow_html=True)
    scene_executive()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def _sidebar_filters():
    st.sidebar.title("Filters")
    zone_names = ["All"] + [z["name"] for z in ZONES]
    sel_zone = st.sidebar.selectbox("Zone", zone_names, index=0, key="global_zone")
    if sel_zone == "All":
        st.session_state["selected_zone"] = None
    else:
        st.session_state["selected_zone"] = next((z for z in ZONES if z["name"] == sel_zone), None)

    st.sidebar.markdown("Month range (YYYY-MM)")
    st.sidebar.text_input("Start", value=st.session_state.get("start_month", ""), key="start_month")
    st.sidebar.text_input("End", value=st.session_state.get("end_month", ""), key="end_month")

    st.sidebar.radio("Blockages rate basis", ["per 100 km", "per 1000 connections"], index=0, key="blockage_basis")
    if st.sidebar.button("Reset filters"):
        for k in ["global_zone", "selected_zone", "start_month", "end_month", "blockage_basis"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

def render_scene_page(scene_key: str):
    st.set_page_config(page_title="Water Utility Performance Dashboard", page_icon="💧", layout="wide")
    _inject_styles()
    _sidebar_filters()
    st.markdown("<div class='shell'>", unsafe_allow_html=True)
    _render_overview_banner()
    st.markdown("<div class='content-area'>", unsafe_allow_html=True)
    if scene_key == "exec":
        scene_executive()
    elif scene_key == "access":
        scene_access()
    elif scene_key == "quality":
        scene_quality()
    elif scene_key == "finance":
        scene_finance()
    elif scene_key == "production":
        scene_production()
    else:
        scene_executive()
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    render_uhn_dashboard()


# ----------------------------- Map helper -----------------------------

def _render_zone_map_overlay(
    *,
    geojson_path: str,
    id_property: str = "id",
    name_property: str = "name",
    metric_property: str = "safeAccess",
    key: str = "zones_map",
) -> Optional[str]:
    """
    Render a Folium map with zone polygons and return the clicked zone name.
    - Colors polygons by metric_property (expects percentage 0-100).
    - Uses popup to capture selection via streamlit-folium's last_object_clicked_popup.
    Returns selected zone name or None.
    """
    if not HAS_FOLIUM:
        return None
    try:
        path = Path(geojson_path)
        if not path.exists():
            # Try relative to repo root one level up
            alt = Path(__file__).resolve().parents[1] / geojson_path
            path = alt if alt.exists() else path
        with path.open("r", encoding="utf-8") as f:
            gj = json.load(f)
    except Exception:
        st.info("Zones GeoJSON not found (Data/zones.geojson). Falling back to simple grid.")
        return None

    # Compute map center
    def _bounds(feature) -> Tuple[float, float, float, float]:
        coords = feature["geometry"]["coordinates"]
        def iter_coords(c):
            if isinstance(c[0], (float, int)):
                yield c
            else:
                for cc in c:
                    yield from iter_coords(cc)
        lats, lngs = [], []
        for lon, lat in iter_coords(coords):
            lats.append(lat)
            lngs.append(lon)
        return min(lats), min(lngs), max(lats), max(lngs)

    try:
        b = [_bounds(f) for f in gj.get("features", []) if f.get("geometry")]
        lat_c = (min(bb[0] for bb in b) + max(bb[2] for bb in b)) / 2
        lon_c = (min(bb[1] for bb in b) + max(bb[3] for bb in b)) / 2
    except Exception:
        lat_c, lon_c = 0.0, 0.0

    m = folium.Map(location=[lat_c, lon_c], zoom_start=10, tiles="CartoDB positron")

    def color_for(v: Optional[float]) -> str:
        if v is None:
            return "#94a3b8"
        try:
            v = float(v)
        except Exception:
            return "#94a3b8"
        if v >= 80:
            return "#10b981"
        if v >= 60:
            return "#f59e0b"
        return "#ef4444"

    def style_fn(feature: Dict[str, Any]):
        props = feature.get("properties", {})
        v = props.get(metric_property)
        return {
            "fillColor": color_for(v),
            "color": "#334155",
            "weight": 1,
            "fillOpacity": 0.55,
        }

    def highlight_fn(feature):
        return {"weight": 2, "color": "#0ea5e9"}

    tooltip = folium.GeoJsonTooltip(
        fields=[name_property, metric_property],
        aliases=["Zone", "Safe access %"],
        sticky=True,
    )

    # Popup carries clicked zone name
    def _popup_html(feature):
        props = feature.get("properties", {})
        nm = props.get(name_property, "")
        return folium.Popup(html=f"<b>{nm}</b>", max_width=200)

    gj_layer = folium.GeoJson(
        gj,
        name="Zones",
        style_function=style_fn,
        highlight_function=highlight_fn,
        tooltip=tooltip,
        popup=_popup_html,
    )
    gj_layer.add_to(m)

    legend_html = """
    <div style='position: absolute; bottom: 18px; left: 18px; z-index: 9999; background: white; border: 1px solid #e5e7eb; padding: 8px 10px; border-radius: 8px; font: 12px Inter'>
      <div style='margin-bottom: 4px; font-weight: 600; color: #0f172a'>Safe access</div>
      <div><span style='display:inline-block;width:10px;height:10px;background:#10b981;border-radius:3px;margin-right:6px'></span> ≥ 80%</div>
      <div><span style='display:inline-block;width:10px;height:10px;background:#f59e0b;border-radius:3px;margin-right:6px'></span> 60–79%</div>
      <div><span style='display:inline-block;width:10px;height:10px;background:#ef4444;border-radius:3px;margin-right:6px'></span> < 60%</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    out = st_folium(m, width=None, height=380, returned_objects=["last_object_clicked_popup"], key=key)
    popup_text = out.get("last_object_clicked_popup") if isinstance(out, dict) else None
    if popup_text:
        nm = str(popup_text).replace("<b>", "").replace("</b>", "")
        return nm
    return None