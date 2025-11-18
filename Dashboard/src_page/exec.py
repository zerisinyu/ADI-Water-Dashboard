import pandas as pd
import streamlit as st
from utils import load_json, conic_css as _conic_css, download_button as _download_button, scene_page_path as _scene_page_path


def _get_executive_snapshot() -> dict:
    return load_json("executive_summary.json") or {
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
