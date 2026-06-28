"""Daily-briefing card configuration.

The home page shows one briefing card per pillar (Access, Financial, Operational,
Service quality). An admin can choose, per slot, *which* metric fills it and *how*
it is visualised (sparkline vs donut). That choice is persisted via the keystore
preference store and mirrored into session_state so it also survives reloads on
Streamlit Cloud (where the on-disk keystore is disabled).

This module is the single source of truth for:
  * the four fixed slots and the metrics each can show (`METRIC_CHOICES`),
  * the default layout (`DEFAULT_LAYOUT`),
  * load/save helpers used by both the home page (read) and the Settings page
    (read + write).

Actual metric *values* are computed on the home page and passed in; this module
only deals with the layout selection, so it has no heavy data dependencies.
"""
from __future__ import annotations

from typing import Dict

import streamlit as st

from data import keystore

PREF_KEY = "briefing_layout"
_SESSION_KEY = "briefing_layout"

# The four fixed pillar slots, in display order. Each is one card.
SLOTS = ["access", "finance", "ops", "quality"]

SLOT_LABELS = {
    "access": "Access & coverage",
    "finance": "Financial health",
    "ops": "Operational",
    "quality": "Service quality",
}

# Metrics that can fill each slot. id -> (label, Material icon, METRIC_REGISTRY key|None).
# The registry key drives the ⓘ helper tooltip (formula / frequency) on the card.
METRIC_CHOICES: Dict[str, Dict[str, tuple]] = {
    "access": {
        "service_coverage":     ("Service coverage", "diversity_3", None),
        "water_coverage":       ("Water coverage", "water_drop", None),
        "sanitation_coverage":  ("Sanitation coverage", "wash", None),
    },
    "finance": {
        "financial_health":      ("Financial health", "payments", None),
        "collection_efficiency": ("Collection efficiency", "request_quote", "collection_efficiency"),
        "cost_coverage":         ("O&M cost coverage", "savings", "cost_coverage"),
    },
    "ops": {
        "operational_efficiency": ("Operational efficiency", "bolt", None),
        "nrw":                    ("Non-revenue water", "invert_colors", "nrw"),
        "capacity_utilisation":   ("Capacity utilisation", "factory", None),
        "service_continuity":     ("Service continuity", "schedule", "service_continuity"),
    },
    "quality": {
        "service_quality":          ("Service quality", "verified", None),
        "water_quality_compliance": ("Water quality", "science", "water_quality_compliance"),
        "complaint_resolution":     ("Complaint resolution", "support_agent", None),
    },
}

VIZ_OPTIONS = ["sparkline", "donut"]

DEFAULT_LAYOUT: Dict[str, Dict[str, str]] = {
    "access":  {"metric": "service_coverage", "viz": "sparkline"},
    "finance": {"metric": "financial_health", "viz": "sparkline"},
    "ops":     {"metric": "operational_efficiency", "viz": "sparkline"},
    "quality": {"metric": "service_quality", "viz": "sparkline"},
}


def _sanitize(raw) -> Dict[str, Dict[str, str]]:
    """Coerce a stored layout to a valid one, falling back to defaults for any
    unknown slot / metric / viz so a stale or corrupt preference never breaks the
    home page."""
    layout = {slot: dict(DEFAULT_LAYOUT[slot]) for slot in SLOTS}
    if isinstance(raw, dict):
        for slot in SLOTS:
            entry = raw.get(slot)
            if not isinstance(entry, dict):
                continue
            metric = entry.get("metric")
            if metric in METRIC_CHOICES[slot]:
                layout[slot]["metric"] = metric
            viz = entry.get("viz")
            if viz in VIZ_OPTIONS:
                layout[slot]["viz"] = viz
    return layout


def load_layout() -> Dict[str, Dict[str, str]]:
    """Return the active briefing layout. Prefers the in-session copy (works on
    Streamlit Cloud), then the persisted keystore preference, then defaults."""
    if _SESSION_KEY in st.session_state:
        return _sanitize(st.session_state[_SESSION_KEY])
    saved = keystore.get_preference(PREF_KEY)
    layout = _sanitize(saved)
    st.session_state[_SESSION_KEY] = layout
    return layout


def save_layout(layout: Dict[str, Dict[str, str]]) -> None:
    """Persist a layout to the keystore and mirror it into session_state."""
    clean = _sanitize(layout)
    st.session_state[_SESSION_KEY] = clean
    try:
        keystore.set_preference(PREF_KEY, clean)
    except Exception:
        # On read-only / cloud deployments the keystore may refuse to write;
        # the session mirror still keeps the choice for the rest of the session.
        pass


def metric_label(slot: str, metric_id: str) -> str:
    choice = METRIC_CHOICES.get(slot, {}).get(metric_id)
    return choice[0] if choice else metric_id
