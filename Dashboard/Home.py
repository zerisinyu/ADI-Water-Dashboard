from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import streamlit as st

from utils import get_zones

# Scenes are implemented in src_page/*
from src_page.exec import scene_executive as scene_exec_page
from src_page.access import scene_access
from src_page.quality import scene_quality as scene_quality_page
from src_page.finance import scene_finance as scene_finance_page
from src_page.production import scene_production as scene_production_page
from src_page.governance import scene_governance as scene_governance_page
from src_page.sector import scene_sector as scene_sector_page


def _inject_styles() -> None:
    css_path = Path(__file__).parent / "styles.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)


def _render_overview_banner() -> None:
    zone = st.session_state.get("selected_zone")
    if isinstance(zone, dict):
        zone_label = zone.get("name") or "All zones"
    else:
        zone_label = zone or "All zones"
    start = st.session_state.get("start_month") or "Any"
    end = st.session_state.get("end_month") or "Now"

    st.title("Water Utility Performance Dashboard")
    st.caption(f"Latest performance overview for {zone_label} (Months: {start} – {end})")


def _sidebar_filters() -> None:
    st.sidebar.title("Filters")
    zones = get_zones()
    zone_names = ["All"] + [z.get("name") for z in zones]
    sel_zone = st.sidebar.selectbox("Zone", zone_names, index=0, key="global_zone")
    if sel_zone == "All":
        st.session_state["selected_zone"] = None
    else:
        st.session_state["selected_zone"] = next((z for z in zones if z.get("name") == sel_zone), None)

    st.sidebar.markdown("Month range (YYYY-MM)")
    st.sidebar.text_input("Start", value=st.session_state.get("start_month", ""), key="start_month")
    st.sidebar.text_input("End", value=st.session_state.get("end_month", ""), key="end_month")

    st.sidebar.radio("Blockages rate basis", ["per 100 km", "per 1000 connections"], index=0, key="blockage_basis")
    if st.sidebar.button("Reset filters"):
        for k in ["global_zone", "selected_zone", "start_month", "end_month", "blockage_basis"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()


def render_uhn_dashboard() -> None:
    st.set_page_config(page_title="Water Utility Performance Dashboard", page_icon="💧", layout="wide")
    _inject_styles()
    _sidebar_filters()

    st.markdown("<div class='shell'>", unsafe_allow_html=True)
    _render_overview_banner()

    st.markdown("<div class='content-area'>", unsafe_allow_html=True)
    if scene_exec_page:
        scene_exec_page()
    else:
        st.error("Executive scene not found in src_page. Please ensure src_page/exec.py exists.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_scene_page(scene_key: str) -> None:
    st.set_page_config(page_title="Water Utility Performance Dashboard", page_icon="💧", layout="wide")
    _inject_styles()
    _sidebar_filters()
    st.markdown("<div class='shell'>", unsafe_allow_html=True)
    _render_overview_banner()
    st.markdown("<div class='content-area'>", unsafe_allow_html=True)
    if scene_key == "exec":
        if scene_exec_page:
            scene_exec_page()
        else:
            st.error("Executive scene not found in src_page. Please ensure src_page/exec.py exists.")
    elif scene_key == "access":
        scene_access()
    elif scene_key == "quality":
        scene_quality_page()
    elif scene_key == "finance":
        scene_finance_page()
    elif scene_key == "production":
        scene_production_page()
    elif scene_key == "governance":
        scene_governance_page()
    elif scene_key == "sector":
        scene_sector_page()
    else:
        if scene_exec_page:
            scene_exec_page()
        else:
            st.error("Executive scene not found in src_page. Please ensure src_page/exec.py exists.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    render_uhn_dashboard()

