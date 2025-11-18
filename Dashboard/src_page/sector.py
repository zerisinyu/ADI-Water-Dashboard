import pandas as pd
import plotly.express as px
import streamlit as st

from utils import load_json


def scene_sector():
    st.markdown("<div class='panel'><h3>Sector Budget</h3>", unsafe_allow_html=True)
    se = load_json("sector_environment.json") or {
        "year": 2024,
        "budget": {"water_pct": 1.9, "sanitation_pct": 1.1, "wash_disbursed_pct": 72},
        "water_stress_pct": 54,
        "water_use_efficiency": {"agri_usd_per_m3": 1.8, "manufacturing_usd_per_m3": 14.2},
        "disaster_loss_usd_m": 63.5,
    }
    b = se["budget"]
    dfb = pd.DataFrame({
        "metric": ["Water budget %", "Sanitation budget %", "WASH disbursed %"],
        "value": [b["water_pct"], b["sanitation_pct"], b["wash_disbursed_pct"]],
    })
    figb = px.bar(dfb, x="metric", y="value", color="metric")
    st.plotly_chart(figb, use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><h3>Environment</h3>", unsafe_allow_html=True)
    ecols = st.columns(3)
    ecols[0].metric("Water stress % (↓)", se["water_stress_pct"])
    ecols[1].metric("WUE Agri $/m³", se["water_use_efficiency"]["agri_usd_per_m3"])
    ecols[2].metric("WUE Mfg $/m³", se["water_use_efficiency"]["manufacturing_usd_per_m3"])
    st.metric("Disaster loss (USD m)", se["disaster_loss_usd_m"])
    st.markdown("</div>", unsafe_allow_html=True)
