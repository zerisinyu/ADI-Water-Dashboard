from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st


# Base data directory (shared across pages)
DATA_DIR = Path(__file__).resolve().parents[1] / "Data"


def load_json(name: str) -> Optional[Dict[str, Any]]:
    """Load a JSON file from the Data directory, returning None on failure."""
    p = DATA_DIR / name
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None


@st.cache_data
def load_csv_data() -> Dict[str, pd.DataFrame]:
    """Read sewer and water access CSV datasets from disk and cache the resulting DataFrames."""
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


def normalise_access_df(
    df: pd.DataFrame,
    *,
    prefix: str,
    extra_pct_cols: Optional[List[str]] = None,
) -> pd.DataFrame:
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


def latest_snapshot(
    df: pd.DataFrame,
    *,
    rename_map: Dict[str, str],
    additional_columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Return the most recent record per (country, zone) pair and rename columns for clarity."""
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


def zone_identifier(country: Optional[str], zone: Optional[str]) -> str:
    base = f"{country or 'na'}-{zone or 'zone'}".lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-") or "zone"


@st.cache_data
def prepare_access_data() -> Dict[str, Any]:
    """
    Prepare derived access datasets for the Access & Coverage scene.
    Returns cached water/sewer snapshots, full histories, and zone-level summaries.
    """
    csv_data = load_csv_data()
    water_df = normalise_access_df(csv_data["water"], prefix="w_", extra_pct_cols=["municipal_coverage"])
    sewer_df = normalise_access_df(csv_data["sewer"], prefix="s_")

    water_latest = latest_snapshot(
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
        additional_columns=[
            "municipal_coverage",
            "w_safely_managed",
            "w_basic",
            "w_limited",
            "w_unimproved",
            "surface_water",
        ],
    )
    sewer_latest = latest_snapshot(
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
            "id": zone_identifier(row.get("country"), row.get("zone")),
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


@st.cache_data
def get_zones() -> List[Dict[str, Any]]:
    """Convenience wrapper to get cached zone records for the sidebar selector."""
    return prepare_access_data()["zones"]


@st.cache_data
def prepare_service_data() -> Dict[str, Any]:
    """
    Prepare service quality data for visualization.
    Returns a dictionary containing processed service data including:
    - Full service data DataFrame
    - Latest snapshots by zone
    - Aggregated time series for key metrics
    """
    service_path = DATA_DIR / "Service_data.csv"
    if not service_path.exists():
        raise FileNotFoundError(f"Service data file not found: {service_path}")

    df = pd.read_csv(service_path)

    # Convert month/year to datetime and sort
    df["date"] = pd.to_datetime(
        df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2) + "-01"
    )
    df = df.sort_values("date")

    # Derived metrics
    df["water_quality_rate"] = (
        (
            df["test_passed_chlorine"] / df["tests_conducted_chlorine"] * 100
            + df["tests_passed_ecoli"] / df["test_conducted_ecoli"] * 100
        )
        / 2
    )
    df["complaint_resolution_rate"] = (df["resolved"] / df["complaints"] * 100)
    df["nrw_rate"] = ((df["w_supplied"] - df["total_consumption"]) / df["w_supplied"] * 100)
    df["sewer_coverage_rate"] = (df["sewer_connections"] / df["households"] * 100)

    latest_by_zone = df.sort_values("date").groupby(["country", "city", "zone"]).last().reset_index()

    time_series = (
        df.groupby("date")
        .agg(
            {
                "w_supplied": "sum",
                "total_consumption": "sum",
                "metered": "sum",
                "water_quality_rate": "mean",
                "complaint_resolution_rate": "mean",
                "nrw_rate": "mean",
                "sewer_coverage_rate": "mean",
                "public_toilets": "sum",
            }
        )
        .reset_index()
    )

    return {
        "full_data": df,
        "latest_by_zone": latest_by_zone,
        "time_series": time_series,
        "zones": sorted(df["zone"].unique()),
        "cities": sorted(df["city"].unique()),
        "countries": sorted(df["country"].unique()),
    }


# ----------------------------- UI Helpers -----------------------------

def conic_css(value: int, good_color: str = "#10b981", soft_color: str = "#e2e8f0") -> str:
    angle = max(0, min(100, int(value))) * 3.6
    return f"background: conic-gradient({good_color} {angle}deg, {soft_color} {angle}deg);"


def download_button(filename: str, rows: List[dict], label: str = "Export CSV"):
    if not rows:
        return
    df = pd.DataFrame(rows)
    data = df.to_csv(index=False).encode("utf-8")
    st.download_button(label, data=data, file_name=filename, mime="text/csv")


def scene_page_path(scene_key: str) -> Optional[str]:
    mapping = {
        "exec": "Home.py",
        "access": "pages/2_🗺️_Access_&_Coverage.py",
        "quality": "pages/3_🛠️_Service_Quality_&_Reliability.py",
        "finance": "pages/4_💹_Financial_Health.py",
        "production": "pages/5_♻️_Production.py",
    }
    return mapping.get(scene_key)
