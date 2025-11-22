from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import streamlit as st

from utils import get_zones, prepare_service_data

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
    country = st.session_state.get("selected_country")
    
    if zone and zone != 'All':
        location_label = f"{zone}, {country}" if country and country != 'All' else zone
    elif country and country != 'All':
        location_label = country
    else:
        location_label = "All Locations"
        
    month = st.session_state.get("selected_month") or "All"
    year = st.session_state.get("selected_year") or "All"

    st.title("Water Utility Performance Dashboard")
    st.caption(f"Overview for {location_label} | Year: {year} | Month: {month}")


def _sidebar_filters() -> None:
    st.sidebar.title("Filters")
    
    # Load data for filters (using service data as it has the most granular time/location info)
    service_data = prepare_service_data()
    df_service = service_data["full_data"]
    
    # 1. Country
    countries = ['All'] + service_data["countries"]
    # Initialize session state if not present
    if "selected_country" not in st.session_state:
        st.session_state["selected_country"] = "All"
        
    selected_country = st.sidebar.selectbox('Country', countries, key='selected_country')

    # 2. Zone
    if selected_country != 'All':
        zones = ['All'] + sorted(df_service[df_service['country'] == selected_country]['zone'].unique().tolist())
    else:
        zones = ['All'] + service_data["zones"]
        
    if "selected_zone" not in st.session_state:
        st.session_state["selected_zone"] = "All"
        
    selected_zone = st.sidebar.selectbox('Zone', zones, key='selected_zone')

    # 3. Year
    available_years = sorted(df_service['year'].unique(), reverse=True)
    if "selected_year" not in st.session_state:
        st.session_state["selected_year"] = available_years[0] if available_years else None
        
    selected_year = st.sidebar.selectbox('Year', available_years, key='selected_year')

    # 4. Month
    months = ['All', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    if "selected_month" not in st.session_state:
        st.session_state["selected_month"] = "All"
        
    selected_month_name = st.sidebar.selectbox('Month', months, key='selected_month')

    if st.sidebar.button("Reset filters"):
        st.session_state["selected_country"] = "All"
        st.session_state["selected_zone"] = "All"
        if available_years:
            st.session_state["selected_year"] = available_years[0]
        st.session_state["selected_month"] = "All"
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

