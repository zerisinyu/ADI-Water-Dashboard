import streamlit as st

from utils import load_json


def scene_governance():
    st.markdown("<div class='panel'><h3>Compliance & Providers</h3>", unsafe_allow_html=True)
    gov = load_json("governance.json") or {
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

