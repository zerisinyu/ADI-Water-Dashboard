from __future__ import annotations

import html as _html
import json
import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import pandas as pd
import streamlit as st

from data.database import DATA_DIR, query, init_database
from data.pipeline import run_pipeline, get_last_run
from data.metrics import metric_tooltip

logger = logging.getLogger(__name__)


def _ensure_pipeline() -> None:
    """Run the ETL pipeline only when the DuckDB session actually needs it.

    Three cases:
    - Already initialised this session: cheap probe for a derived view; if it's
      gone (an in-memory DB wiped by Streamlit's `runOnSave` module reload while
      the session flag survived), rebuild.
    - New session, warm on-disk DB: if every table + derived view is present and
      no source file is newer than the DB, skip the whole pipeline (the big
      cold-start win — no re-extract, no Pandera validation, no view rebuild).
    - Otherwise: run the full pipeline.
    """
    if st.session_state.get("_pipeline_initialised"):
        try:
            from data.database import query as _q
            _q("SELECT 1 FROM v_billing_monthly LIMIT 1")
            return
        except Exception:
            pass  # views wiped — fall through and rebuild
    else:
        try:
            from data.database import is_warm_and_fresh
            if is_warm_and_fresh():
                st.session_state["_pipeline_initialised"] = True
                return
        except Exception:
            pass
    run_pipeline()
    st.session_state["_pipeline_initialised"] = True


# =============================================================================
# ACCESS CONTROL HELPERS
# =============================================================================

def get_user_country_filter() -> Optional[str]:
    """
    Get the country filter for the current user.
    
    Returns:
        Country name if user is restricted to a specific country,
        None if user has access to all countries (master user).
    """
    try:
        from auth import get_current_user, UserRole
        user = get_current_user()
        if user is None:
            return None  # No user logged in - let page handle this
        if user.role == UserRole.MASTER_USER:
            return None  # Master users have access to all countries
        return user.assigned_country
    except ImportError:
        # Auth module not available - no filtering
        return None


def filter_df_by_user_access(df: pd.DataFrame, country_column: str = "country") -> pd.DataFrame:
    """
    Filter a DataFrame based on the current user's access permissions.
    
    This is the primary data access control function. All data loading
    should pass through this filter to ensure proper access control.
    
    Args:
        df: pandas DataFrame to filter
        country_column: Name of the column containing country information
    
    Returns:
        Filtered DataFrame with only accessible data
    """
    if df is None or df.empty:
        return df
    
    user_country = get_user_country_filter()
    
    # No filtering needed if user has access to all countries
    if user_country is None:
        return df
    
    # Apply country filter if column exists
    if country_column in df.columns:
        return df[df[country_column].str.lower() == user_country.lower()]
    
    return df


def validate_selected_country(selected_country: str) -> str:
    """
    Validate that the selected country is accessible by the current user.
    
    Args:
        selected_country: The country selected in the UI
    
    Returns:
        The validated country (may be different if user doesn't have access)
    """
    user_country = get_user_country_filter()
    
    # Master users can select any country
    if user_country is None:
        return selected_country
    
    # Non-master users are locked to their assigned country
    return user_country


def load_json(name: str) -> Optional[Dict[str, Any]]:
    """Load a JSON file from the Data directory, returning None on failure."""
    p = DATA_DIR / name
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None


# =============================================================================
# STANDARDIZED FILTERS BASED ON AUDC DATA DICTIONARY
# =============================================================================
# Data Frequencies per AUDC Dictionary:
# - Annual: Access & Coverage (zone-level), National accounts, some Service Quality
# - Quarterly: Coverage growth metrics
# - Monthly: Production, Service Quality, Financial services
# - Daily: Production data only
# Data Range: 2020-01-01 to 2024-12-01

# Page-specific frequency configurations based on AUDC dictionary
PAGE_FREQUENCIES = {
    "access": {
        "allowed": ["Annual", "Quarterly"],
        "default": "Annual",
        "description": "Access & Coverage data is Annual at zone level; Coverage growth is Quarterly"
    },
    "production": {
        "allowed": ["Monthly", "Daily"],
        "default": "Monthly", 
        "description": "Production data is available Daily at source level"
    },
    "quality": {
        "allowed": ["Monthly", "Quarterly", "Annual"],
        "default": "Monthly",
        "description": "Service Quality is Monthly; some governance metrics are Quarterly/Annual"
    },
    "finance": {
        "allowed": ["Monthly", "Annual"],
        "default": "Monthly",
        "description": "Financial services are Monthly; Budget data is Annual"
    }
}


def get_page_frequencies(page: str) -> Dict[str, Any]:
    """
    Get the allowed frequencies for a specific page based on AUDC dictionary.
    
    Args:
        page: Page identifier ('access', 'production', 'quality', 'finance')
    
    Returns:
        Dict with 'allowed', 'default', and 'description' keys
    """
    return PAGE_FREQUENCIES.get(page, {
        "allowed": ["Annual", "Monthly"],
        "default": "Monthly",
        "description": "Default frequency configuration"
    })


def render_standardized_filters(
    df: pd.DataFrame,
    page: str,
    key_prefix: str,
    country_col: str = "country",
    zone_col: str = "zone",
    year_col: str = "year",
    month_col: str = "month",
    show_period: bool = True,
    show_zone: bool = True,
    show_year: bool = True,
    show_month: bool = False
) -> Dict[str, Any]:
    """
    Render standardized filters for all dashboard pages based on AUDC data dictionary.
    
    This function creates consistent filter UI across all pages while respecting:
    - User access control (country restrictions based on role)
    - AUDC data dictionary frequencies (Annual/Quarterly/Monthly/Daily)
    - Session state for persistence across page navigation
    
    Args:
        df: DataFrame to extract filter options from
        page: Page identifier for frequency config ('access', 'production', 'quality', 'finance')
        key_prefix: Unique prefix for Streamlit widget keys
        country_col: Column name for country data
        zone_col: Column name for zone data  
        year_col: Column name for year data
        month_col: Column name for month data
        show_period: Whether to show period/frequency selector
        show_zone: Whether to show zone filter
        show_year: Whether to show year filter
        show_month: Whether to show month filter (overridden by period selection)
    
    Returns:
        Dict with selected filter values:
        - 'period': Selected period (Annual/Quarterly/Monthly/Daily)
        - 'country': Selected country
        - 'zone': Selected zone(s)
        - 'year': Selected year or year range
        - 'month': Selected month (if applicable)
        - 'is_locked': Whether country is locked for user
    """
    # Get user access restrictions
    try:
        from auth import get_current_user, UserRole, get_allowed_countries
        user = get_current_user()
        allowed_countries = get_allowed_countries()
        is_master_user = user is not None and user.role == UserRole.MASTER_USER
    except ImportError:
        user = None
        allowed_countries = []
        is_master_user = True  # Default to no restrictions if auth not available
    
    # Get page-specific frequency config
    freq_config = get_page_frequencies(page)
    
    # Determine column layout based on what's shown
    num_cols = sum([show_period, True, show_zone, show_year])  # Country always shown
    col_widths = []
    if show_period:
        col_widths.append(1.5)
    col_widths.append(2.5)  # Country
    if show_zone:
        col_widths.append(2.5)
    if show_year:
        col_widths.append(1.5)
    if show_month:
        col_widths.append(1.5)  # keep month in the same row as country/year

    cols = st.columns(col_widths)
    col_idx = 0
    
    # Initialize return dict
    result = {
        'period': freq_config['default'],
        'country': 'All',
        'zone': 'All',
        'year': None,
        'month': 'All',
        'is_locked': False
    }
    
    # Period Filter (based on AUDC frequencies for this page)
    if show_period:
        with cols[col_idx]:
            result['period'] = st.radio(
                "View Period",
                freq_config['allowed'],
                horizontal=True,
                key=f"{key_prefix}_period",
                help=freq_config['description']
            )
        col_idx += 1
    
    # Country Filter (with access control)
    with cols[col_idx]:
        if is_master_user:
            countries = ['All'] + sorted(df[country_col].unique().tolist()) if country_col in df.columns else ['All']
        else:
            countries = allowed_countries if allowed_countries else ['All']
        
        # Get default from session state
        default_country_idx = 0
        if "selected_country" in st.session_state:
            validated = validate_selected_country(st.session_state.selected_country)
            if validated in countries:
                default_country_idx = countries.index(validated)
        
        # Check if locked
        is_locked = not is_master_user and len(countries) == 1
        result['is_locked'] = is_locked
        
        if is_locked:
            st.markdown(f"""
            <div style='background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; 
                        padding: 10px 14px; display: flex; align-items: center; gap: 8px; margin-top: 24px;'>
                <span style='font-size: 1rem;'>🔒</span>
                <span style='font-weight: 600; color: #334155;'>{countries[0]}</span>
            </div>
            """, unsafe_allow_html=True)
            result['country'] = countries[0]
        else:
            result['country'] = st.selectbox(
                "Country", 
                countries, 
                index=default_country_idx, 
                key=f"{key_prefix}_country"
            )
            result['country'] = validate_selected_country(result['country'])
    col_idx += 1
    
    # Zone Filter (dependent on country)
    if show_zone:
        with cols[col_idx]:
            if zone_col in df.columns:
                if result['country'] != 'All':
                    zones = ['All'] + sorted(
                        df[df[country_col].str.lower() == result['country'].lower()][zone_col].unique().tolist()
                    )
                else:
                    zones = ['All'] + sorted(df[zone_col].unique().tolist())
            else:
                zones = ['All']
            
            default_zone_idx = 0
            if "selected_zone" in st.session_state and st.session_state.selected_zone in zones:
                default_zone_idx = zones.index(st.session_state.selected_zone)
            
            result['zone'] = st.selectbox(
                "Zone/City",
                zones,
                index=default_zone_idx,
                key=f"{key_prefix}_zone"
            )
        col_idx += 1
    
    # Year Filter
    if show_year:
        with cols[col_idx]:
            if year_col in df.columns:
                years = sorted(df[year_col].dropna().unique().tolist(), reverse=True)
                # Convert to int if possible
                try:
                    years = [int(y) for y in years]
                except (ValueError, TypeError):
                    pass
            else:
                years = list(range(2024, 2019, -1))  # Default 2024-2020
            
            default_year_idx = 0
            if "selected_year" in st.session_state and st.session_state.selected_year in years:
                default_year_idx = years.index(st.session_state.selected_year)
            
            result['year'] = st.selectbox(
                "Year",
                years,
                index=default_year_idx,
                key=f"{key_prefix}_year"
            )
        col_idx += 1
    
    # Month filter. When show_month is True it sits in the same row as
    # country/year (a column was reserved above); otherwise it appears in its own
    # row only for Monthly/Daily periods.
    month_names = ['All', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    default_month_idx = 0
    if "selected_month" in st.session_state and st.session_state.selected_month in month_names:
        default_month_idx = month_names.index(st.session_state.selected_month)

    if show_month:
        with cols[col_idx]:
            result['month'] = st.selectbox(
                "Month", month_names, index=default_month_idx, key=f"{key_prefix}_month",
            )
        col_idx += 1
    elif result['period'] in ['Monthly', 'Daily']:
        result['month'] = st.selectbox(
            "Month", month_names, index=default_month_idx, key=f"{key_prefix}_month",
        )

    # ------------------------------------------------------------------
    # Write selections back to the GLOBAL session keys so that the choice
    # persists across pages and stays consistent with the Executive page
    # (single source of truth). Without this, each page's prefixed widget
    # kept its own private state and selections did not propagate.
    # ------------------------------------------------------------------
    st.session_state["selected_country"] = result['country']
    if show_zone:
        st.session_state["selected_zone"] = result['zone']
    if show_year and result['year'] is not None:
        st.session_state["selected_year"] = result['year']
    st.session_state["selected_month"] = result['month']

    return result


def apply_standard_filters(
    df: pd.DataFrame,
    filters: Dict[str, Any],
    country_col: str = "country",
    zone_col: str = "zone", 
    year_col: str = "year",
    month_col: str = "month"
) -> pd.DataFrame:
    """
    Apply standardized filter selections to a DataFrame.
    
    Args:
        df: DataFrame to filter
        filters: Filter dict from render_standardized_filters()
        country_col: Column name for country data
        zone_col: Column name for zone data
        year_col: Column name for year data
        month_col: Column name for month data
    
    Returns:
        Filtered DataFrame
    """
    df_filtered = df.copy()
    
    # Country filter
    if filters.get('country') and filters['country'] != 'All' and country_col in df_filtered.columns:
        df_filtered = df_filtered[df_filtered[country_col].str.lower() == filters['country'].lower()]
    
    # Zone filter
    if filters.get('zone') and filters['zone'] != 'All' and zone_col in df_filtered.columns:
        df_filtered = df_filtered[df_filtered[zone_col].str.lower() == filters['zone'].lower()]
    
    # Year filter
    if filters.get('year') and year_col in df_filtered.columns:
        try:
            year_val = int(filters['year'])
            df_filtered = df_filtered[df_filtered[year_col] == year_val]
        except (ValueError, TypeError):
            df_filtered = df_filtered[df_filtered[year_col] == filters['year']]
    
    # Month filter
    if filters.get('month') and filters['month'] != 'All' and month_col in df_filtered.columns:
        month_map = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }
        if filters['month'] in month_map:
            df_filtered = df_filtered[df_filtered[month_col] == month_map[filters['month']]]
    
    return df_filtered


def get_month_number(month_name: str) -> Optional[int]:
    """Convert month name to number. Returns None for 'All'."""
    month_map = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    return month_map.get(month_name)


# =============================================================================
# UI COMPONENT HELPERS
# =============================================================================
# These render reusable design-system pieces. All chrome uses neutral surfaces +
# the brand color; domain colors (water/sanitation) live inside charts only.


@dataclass
class KPI:
    """A single KPI tile in a kpi-row.

    delta_kind controls the color: 'positive' = green, 'negative' = red,
    'neutral' = grey. Passing a delta string starting with '+' / '-' / '↑' / '↓'
    will auto-classify if delta_kind is left as 'auto'.

    `icon` is an optional Material Symbols name (e.g. "trending_up") shown
    in the card corner. `sparkline` is an optional list of numbers — when
    provided, an inline 80x22 SVG sparkline renders below the value.
    """
    label: str
    value: str
    delta: Optional[str] = None
    delta_kind: str = "auto"  # auto | positive | negative | neutral
    footnote: Optional[str] = None
    icon: Optional[str] = None
    sparkline: Optional[List[float]] = None
    donut: Optional[float] = None    # 0–100 — renders a mini donut instead of a sparkline
    help: Optional[str] = None       # tooltip text shown on an ⓘ next to the label
    metric_key: Optional[str] = None  # METRIC_REGISTRY key — auto-fills `help`


def _classify_delta(delta: str, kind: str) -> str:
    if kind != "auto":
        return kind
    s = delta.strip()
    if not s:
        return "neutral"
    if s.startswith(("+", "↑", "▲")):
        return "positive"
    if s.startswith(("-", "↓", "▼", "−")):
        return "negative"
    return "neutral"


def _sparkline_svg(values: List[float], width: int = 80, height: int = 22, color: str = "var(--brand)") -> str:
    """Render a compact sparkline SVG inline. Empty / constant series render flat."""
    vs = [v for v in values if v is not None]
    if len(vs) < 2:
        return ""
    lo, hi = min(vs), max(vs)
    rng = hi - lo if hi != lo else 1.0
    step = width / max(len(vs) - 1, 1)
    pts = []
    for i, v in enumerate(vs):
        x = i * step
        y = height - ((v - lo) / rng) * height
        pts.append(f"{x:.1f},{y:.1f}")
    poly = " ".join(pts)
    # Build an area fill underneath the line
    area = f"0,{height} {poly} {width:.1f},{height}"
    return (
        f'<svg class="kpi-card__spark" viewBox="0 0 {width} {height}" preserveAspectRatio="none" '
        f'width="{width}" height="{height}" aria-hidden="true">'
        f'<polygon points="{area}" fill="{color}" fill-opacity="0.08" stroke="none"/>'
        f'<polyline points="{poly}" fill="none" stroke="{color}" stroke-width="1.5" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
        '</svg>'
    )


def _donut_svg(pct: float, size: int = 40, stroke: int = 6, color: str = "var(--brand)") -> str:
    """Render a compact donut showing `pct` (0–100) of a ring filled. Used as an
    alternative mini-viz to the sparkline on a KPI card."""
    try:
        p = max(0.0, min(100.0, float(pct)))
    except (TypeError, ValueError):
        return ""
    r = (size - stroke) / 2
    cx = cy = size / 2
    import math
    circ = 2 * math.pi * r
    dash = circ * p / 100.0
    return (
        f'<svg class="kpi-card__donut" viewBox="0 0 {size} {size}" width="{size}" height="{size}" '
        f'aria-hidden="true">'
        f'<circle cx="{cx}" cy="{cy}" r="{r:.2f}" fill="none" stroke="var(--divider)" '
        f'stroke-width="{stroke}"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r:.2f}" fill="none" stroke="{color}" '
        f'stroke-width="{stroke}" stroke-linecap="round" '
        f'stroke-dasharray="{dash:.2f} {circ - dash:.2f}" '
        f'transform="rotate(-90 {cx} {cy})"/>'
        f'<text x="{cx}" y="{cy}" text-anchor="middle" dominant-baseline="central" '
        f'class="kpi-card__donut-label">{p:.0f}%</text>'
        '</svg>'
    )


def render_kpi_row(items: Iterable[KPI]) -> None:
    """Render a row of KPI cards in the canonical design-system style.

    All KPIs across the app should use this helper so they share typography,
    padding, hover behavior, and tabular numerics. The grid auto-fits.
    """
    parts: List[str] = ['<div class="kpi-row">']
    for it in items:
        delta_html = ""
        if it.delta:
            kind = _classify_delta(it.delta, it.delta_kind)
            delta_html = f'<div class="kpi-card__delta kpi-card__delta--{kind}">{_html.escape(it.delta)}</div>'
        footnote_html = (
            f'<div class="kpi-card__footnote">{_html.escape(it.footnote)}</div>'
            if it.footnote else ""
        )
        icon_html = (
            f'<span class="icon icon-muted kpi-card__icon">{_html.escape(it.icon)}</span>'
            if it.icon else ""
        )
        help_text = it.help or (metric_tooltip(it.metric_key) if it.metric_key else None)
        help_html = (
            f'<span class="kpi-help" tabindex="0" role="note" aria-label="{_html.escape(help_text)}">'
            f'<span class="icon kpi-help__icon">info</span>'
            f'<span class="kpi-help__bubble">{_html.escape(help_text)}</span>'
            f'</span>'
            if help_text else ""
        )
        if it.donut is not None:
            viz_html = _donut_svg(it.donut)
        elif it.sparkline:
            viz_html = _sparkline_svg(it.sparkline)
        else:
            viz_html = ""

        parts.append(
            '<div class="kpi-card">'
            f'<div class="kpi-card__head">'
            f'<div class="kpi-card__label">{_html.escape(it.label)}{help_html}</div>'
            f'{icon_html}'
            f'</div>'
            f'<div class="kpi-card__value">{_html.escape(it.value)}</div>'
            f'{viz_html}'
            f'{delta_html}'
            f'{footnote_html}'
            '</div>'
        )
    parts.append('</div>')
    st.markdown("".join(parts), unsafe_allow_html=True)


# =============================================================================
# DAILY-BRIEFING HELPERS — manager-style framing on the Home page.
# =============================================================================

def render_status_badge(status: str, label: Optional[str] = None) -> str:
    """Return inline HTML for a Green / Amber / Red status pill.

    `status` is one of "good" | "warn" | "critical" | "neutral"."""
    palette = {
        "good":     ("var(--success)",  "var(--success-soft)",  "All systems healthy"),
        "warn":     ("var(--warning)",  "var(--warning-soft)",  "Watch list"),
        "critical": ("var(--danger)",   "var(--danger-soft)",   "Action required"),
        "neutral":  ("var(--text-secondary)", "var(--surface-muted)", "—"),
    }
    color, bg, default_label = palette.get(status, palette["neutral"])
    text = _html.escape(label or default_label)
    return (
        f'<span class="status-badge" style="display:inline-flex;align-items:center;gap:6px;'
        f'padding:4px 10px;border-radius:9999px;background:{bg};color:{color};'
        f'font-size:12px;font-weight:600;letter-spacing:.01em;">'
        f'<span style="width:6px;height:6px;border-radius:50%;background:{color};"></span>'
        f'{text}</span>'
    )


def render_target_bar(label: str, value: float, target: float,
                       *, unit: str = "%", direction: str = "higher_is_better",
                       icon: Optional[str] = None) -> None:
    """Render a single "actual vs target" progress bar card.

    For `higher_is_better` metrics the bar fills with the share of target met
    (capped at 100%). For `lower_is_better` it shows the share *over* target
    in red, or "under target" in green.
    """
    if target <= 0:
        target = 1.0
    if direction == "higher_is_better":
        pct = max(0.0, min(value / target, 1.5)) * 100.0
        is_good = value >= target
    else:
        # Lower is better — show value / target where >100% is bad.
        pct = max(0.0, min(value / target, 2.0)) * 100.0
        is_good = value <= target
    fill_color = "var(--success)" if is_good else ("var(--warning)" if pct < 130 else "var(--danger)")
    icon_html = (
        f'<span class="icon icon-sm icon-muted" style="margin-right:6px;">{_html.escape(icon)}</span>'
        if icon else ""
    )
    arrow = "↑" if direction == "higher_is_better" else "↓"
    target_label = f"target {arrow} {target:g}{unit}"
    st.markdown(
        f'<div class="target-bar">'
        f'<div class="target-bar__head">'
        f'<div class="target-bar__label">{icon_html}{_html.escape(label)}</div>'
        f'<div class="target-bar__target">{_html.escape(target_label)}</div>'
        f'</div>'
        f'<div class="target-bar__track">'
        f'<div class="target-bar__fill" style="width:{min(pct, 100):.0f}%;background:{fill_color};"></div>'
        f'<div class="target-bar__marker" style="left:{min(100, 100):.0f}%;"></div>'
        f'</div>'
        f'<div class="target-bar__value">'
        f'<span class="target-bar__actual" style="color:{fill_color};">{value:.1f}{unit}</span>'
        f'<span class="target-bar__delta">{pct:.0f}% of target</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_risk_card(title: str, items: List[Dict[str, str]], *, tone: str = "warn",
                     bare: bool = False) -> None:
    """Render a list of risk / win items inside a single card.

    Each item is `{"label": str, "detail": str, "action": str (optional)}`.
    `tone` selects the accent: "warn" (amber), "danger" (red), "good" (green).
    When `bare=True` the outer `.risk-card` wrapper is omitted so the title +
    list can sit inside an existing container (e.g. below a toggle).
    """
    accent = {
        "good":   "var(--success)",
        "warn":   "var(--warning)",
        "danger": "var(--danger)",
    }.get(tone, "var(--text-secondary)")
    icon_for_tone = {
        "good":   "trending_up",
        "warn":   "warning",
        "danger": "priority_high",
    }.get(tone, "info")
    rows = []
    for it in items:
        action_html = (
            f'<div class="risk-card__action">{_html.escape(it.get("action", ""))}</div>'
            if it.get("action") else ""
        )
        rows.append(
            f'<li class="risk-card__row">'
            f'<div class="risk-card__label">{_html.escape(it.get("label", ""))}</div>'
            f'<div class="risk-card__detail">{_html.escape(it.get("detail", ""))}</div>'
            f'{action_html}'
            f'</li>'
        )
    body = "".join(rows) if rows else '<li class="risk-card__empty">Nothing flagged.</li>'
    inner = (
        f'<div class="risk-card__title">'
        f'<span class="icon icon-sm" style="color:{accent};">{icon_for_tone}</span>'
        f'<span>{_html.escape(title)}</span>'
        f'</div>'
        f'<ul class="risk-card__list">{body}</ul>'
    )
    if bare:
        st.markdown(
            f'<div class="risk-card risk-card--bare" style="--risk-accent:{accent};">{inner}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="risk-card" style="--risk-accent:{accent};">{inner}</div>',
            unsafe_allow_html=True,
        )


def render_action_checklist(title: str, items: List[Dict[str, str]]) -> None:
    """Render the "Today's actions" checklist card.

    Each item: `{"text": str, "page": str (optional), "label": str (optional)}`.
    Pages route via st.page_link below the checklist body.
    """
    if not items:
        return
    rows = "".join(
        f'<li class="action-checklist__row">'
        f'<span class="icon icon-sm icon-muted">check_box_outline_blank</span>'
        f'<span class="action-checklist__text">{_html.escape(it.get("text", ""))}</span>'
        f'</li>'
        for it in items
    )
    st.markdown(
        f'<div class="action-checklist">'
        f'<div class="action-checklist__title">'
        f'<span class="icon icon-sm icon-brand">task_alt</span>'
        f'<span>{_html.escape(title)}</span>'
        f'</div>'
        f'<ul class="action-checklist__list">{rows}</ul>'
        f'</div>',
        unsafe_allow_html=True,
    )
    # Render st.page_link rows immediately after so they remain interactive.
    link_items = [it for it in items if it.get("page")]
    if link_items:
        cols = st.columns(min(len(link_items), 4))
        for i, it in enumerate(link_items):
            with cols[i % len(cols)]:
                try:
                    st.page_link(
                        it["page"],
                        label=it.get("label", "Open"),
                        icon=":material/arrow_forward:",
                        width="stretch",
                    )
                except Exception:
                    pass


def render_majibot_todo(title: str, items: List[Dict[str, str]]) -> None:
    """Render MajiBot's to-do list as a dark navy card (matches the MajiBot
    panel). Each item is `{"text": str}`. Sits beside the risks/wins toggle."""
    rows = "".join(
        f'<li class="majibot-todo__row">'
        f'<span class="icon icon-sm majibot-todo__check">check_box_outline_blank</span>'
        f'<span class="majibot-todo__text">{_html.escape(it.get("text", ""))}</span>'
        f'</li>'
        for it in items
    ) or '<li class="majibot-todo__empty">Nothing on the list — all clear.</li>'
    st.markdown(
        f'<div class="majibot-todo">'
        f'<div class="majibot-todo__title">'
        f'<span class="majibot-todo__avatar"><span class="icon icon-sm">auto_awesome</span></span>'
        f'<span>{_html.escape(title)}</span>'
        f'</div>'
        f'<ul class="majibot-todo__list">{rows}</ul>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_page_header(
    title: str,
    *,
    subtitle: Optional[str] = None,
    eyebrow: Optional[str] = None,
    icon: Optional[str] = None,
    badges: Optional[List[Dict[str, str]]] = None,
    show_clock: bool = False,
    meta_text: Optional[str] = None,
) -> None:
    """Render the canonical page header.

    `icon` is a Material Symbols name (e.g. "dashboard", "water_drop"). When
    provided it renders to the left of the title.

    `badges` is a list of dicts: {"label": "Uganda Only", "kind": "brand"}
    where kind is one of: brand, success, warning, danger, info, neutral.

    `show_clock` adds a right-aligned date/time block. Use only on the
    Executive page where it conveys "live" status; sub-pages should leave
    it off and use `meta_text` for a refresh timestamp instead.
    """
    from datetime import datetime

    # Page-header eyebrow removed globally by design (kept param for back-compat).
    eyebrow_html = ""
    subtitle_html = (
        f'<p class="page-header__subtitle">{_html.escape(subtitle)}</p>'
        if subtitle else ""
    )
    icon_html = (
        f'<span class="icon icon-xl icon-brand page-header__icon">{_html.escape(icon)}</span>'
        if icon else ""
    )

    badges_html = ""
    if badges:
        badge_parts: List[str] = []
        for b in badges:
            kind = b.get("kind", "neutral")
            cls = f'pill pill--{kind}' if kind != "neutral" else 'pill'
            badge_parts.append(f'<span class="{cls}">{_html.escape(b["label"])}</span>')
        badges_html = f'<div class="page-header__badges">{"".join(badge_parts)}</div>'

    meta_html = ""
    if show_clock:
        now = datetime.now()
        meta_html = (
            '<div class="page-header__meta">'
            f'<div class="page-header__meta-time">{now.strftime("%H:%M")}</div>'
            f'<div>{now.strftime("%a, %d %b %Y")}</div>'
            '<div class="page-header__meta-status"><span class="dot dot--good"></span>Live data</div>'
            '</div>'
        )
    elif meta_text:
        meta_html = (
            '<div class="page-header__meta">'
            f'<div>{_html.escape(meta_text)}</div>'
            '</div>'
        )

    title_html = (
        f'<h1 class="page-header__title">{icon_html}{_html.escape(title)}</h1>'
    )

    st.markdown(
        '<div class="page-header">'
        '<div class="page-header__row">'
        '<div class="page-header__main">'
        f'{eyebrow_html}'
        f'{title_html}'
        f'{subtitle_html}'
        f'{badges_html}'
        '</div>'
        f'{meta_html}'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_section_header(
    title: str,
    *,
    eyebrow: Optional[str] = None,
    icon: Optional[str] = None,
    meta: Optional[str] = None,
    domain: Optional[str] = None,  # legacy; ignored
) -> None:
    """Render a section header inside a page.

    `icon` is a Material Symbols name (e.g. "trending_up", "savings"). When
    provided it renders to the left of the title.

    The `domain` argument is preserved for backwards compatibility with
    existing callers but no longer applies a colored border — chrome stays
    neutral.
    """
    eyebrow_html = (
        f'<div class="section-header__eyebrow">{_html.escape(eyebrow)}</div>'
        if eyebrow else ""
    )
    meta_html = (
        f'<div class="section-header__meta">{_html.escape(meta)}</div>'
        if meta else ""
    )
    icon_html = (
        f'<span class="icon icon-lg icon-muted section-header__icon">{_html.escape(icon)}</span>'
        if icon else ""
    )
    st.markdown(
        '<div class="section-header">'
        '<div class="section-header__lead">'
        f'{eyebrow_html}'
        f'<h2 class="section-header__title">{icon_html}{_html.escape(title)}</h2>'
        '</div>'
        f'{meta_html}'
        '</div>',
        unsafe_allow_html=True,
    )


def render_domain_pill(domain: str, text: Optional[str] = None) -> str:
    """Return inline HTML for a small domain pill.

    Reserved for use inside chart legends or data labels — not chrome.
    """
    label = text or ('💧 Water' if domain == 'water' else '🚿 Sanitation')
    return f'<span class="domain-pill">{_html.escape(label)}</span>'


def render_granularity_badge(frequency: str, granularity: str) -> str:
    """Return HTML for a data granularity badge.

    Neutral styling — uses the .granularity-badge class from styles.css.
    """
    return (
        '<span class="granularity-badge">'
        f'{_html.escape(frequency.title())} · {_html.escape(granularity)}'
        '</span>'
    )


@contextmanager
def chart_card(title: str, *, meta: Optional[str] = None, footnote: Optional[str] = None):
    """Context manager that wraps a chart in the canonical chart-card chrome.

    Usage:
        with chart_card("Revenue vs costs", meta="Last 12 months"):
            st.plotly_chart(fig, use_container_width=True)
    """
    meta_html = (
        f'<div class="chart-card__meta">{_html.escape(meta)}</div>'
        if meta else ""
    )
    st.markdown(
        '<div class="chart-card">'
        '<div class="chart-card__header">'
        f'<h3 class="chart-card__title">{_html.escape(title)}</h3>'
        f'{meta_html}'
        '</div>',
        unsafe_allow_html=True,
    )
    try:
        yield
    finally:
        if footnote:
            st.markdown(
                f'<div class="chart-card__footnote">{_html.escape(footnote)}</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)


def render_chart_container(title: str, source: Optional[str] = None, help_text: Optional[str] = None) -> None:
    """Legacy: open a chart container. Prefer `chart_card` context manager.

    Callers must close with st.markdown('</div>', unsafe_allow_html=True).
    Kept for backwards compatibility with pages that haven't migrated yet.
    """
    meta_bits: List[str] = []
    if help_text:
        meta_bits.append(_html.escape(help_text))
    if source:
        meta_bits.append(f'Source: {_html.escape(source)}')
    meta_html = (
        f'<div class="chart-card__meta">{" · ".join(meta_bits)}</div>'
        if meta_bits else ""
    )
    st.markdown(
        '<div class="chart-card">'
        '<div class="chart-card__header">'
        f'<h3 class="chart-card__title">{_html.escape(title)}</h3>'
        f'{meta_html}'
        '</div>',
        unsafe_allow_html=True,
    )


def render_empty_state(icon: str, title: str, description: str) -> None:
    """Render an empty state when no data is available."""
    st.markdown(
        '<div class="empty-state">'
        f'<div class="empty-state__icon">{_html.escape(icon)}</div>'
        f'<div class="empty-state__title">{_html.escape(title)}</div>'
        f'<div class="empty-state__description">{_html.escape(description)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_no_data_panel(
    title: str,
    description: str,
    *,
    icon: str = "insights",
    tag: Optional[str] = "Not yet collected",
) -> None:
    """Render a tasteful 'data not collected yet' placeholder.

    Use this instead of blurred fake charts. It reads clearly as an intentional
    empty state (sunken, dashed-border card with a soft icon chip) rather than a
    broken visualization. `icon` is a Material Symbols name; `tag` is an optional
    uppercase pill (pass None to hide it).
    """
    tag_html = (
        f'<div class="empty-panel__tag">{_html.escape(tag)}</div>' if tag else ""
    )
    st.markdown(
        '<div class="empty-panel">'
        f'<span class="icon empty-panel__icon">{_html.escape(icon)}</span>'
        f'<div class="empty-panel__title">{_html.escape(title)}</div>'
        f'<div class="empty-panel__desc">{_html.escape(description)}</div>'
        f'{tag_html}'
        '</div>',
        unsafe_allow_html=True,
    )


# Legacy shim — existing pages call render_page_hero(title, icon, filters, metrics)
def render_page_hero(
    title: str,
    icon: str,
    filters: Dict[str, str],
    metrics: Optional[List[Dict[str, str]]] = None,
    data_freshness: Optional[str] = None,
) -> None:
    """Legacy hero. Prefer render_page_header + render_kpi_row in new code.

    `icon` is a Material Symbols name (e.g. "savings"). Callers that still
    pass an emoji are rendered as a plain title without an icon.
    """
    from datetime import datetime

    badges: List[Dict[str, str]] = []
    for k, v in (filters or {}).items():
        if v and v != "All":
            badges.append({"label": f"{k}: {v}", "kind": "neutral"})

    # If `icon` looks like a Material Symbols name (snake_case ASCII), pass it
    # through; otherwise drop it. This makes the migration of legacy emoji
    # callers a one-line change.
    icon_name = icon if icon and icon.replace("_", "").isascii() and icon.isidentifier() else None

    meta_text = data_freshness or datetime.now().strftime("Updated %Y-%m-%d %H:%M")
    render_page_header(
        title,
        icon=icon_name,
        badges=badges,
        meta_text=meta_text,
    )

    if metrics:
        kpis: List[KPI] = []
        for m in metrics:
            kpis.append(KPI(
                label=str(m.get("label", "")),
                value=str(m.get("value", "")),
                delta=m.get("delta") or None,
            ))
        render_kpi_row(kpis)


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
def _load_raw_access_data() -> Dict[str, Any]:
    """
    Load and process raw access data from DuckDB (internal, cached).
    This loads all data without access filtering.
    """
    _ensure_pipeline()
    water_df = normalise_access_df(
        query("SELECT * FROM w_access"), prefix="w_", extra_pct_cols=["municipal_coverage"]
    )
    sewer_df = normalise_access_df(
        query("SELECT * FROM s_access"), prefix="s_"
    )
    return {"water": water_df, "sewer": sewer_df}


def prepare_access_data() -> Dict[str, Any]:
    """
    Prepare derived access datasets for the Access & Coverage scene.
    Returns cached water/sewer snapshots, full histories, and zone-level summaries.
    
    Note: Data is filtered based on the current user's access permissions.
    Access filtering is applied AFTER caching to ensure proper isolation.
    """
    # Load raw cached data
    raw_data = _load_raw_access_data()
    water_df = raw_data["water"].copy()
    sewer_df = raw_data["sewer"].copy()
    
    # Apply access control filtering based on user permissions
    # This happens on each call to ensure proper user isolation
    water_df = filter_df_by_user_access(water_df, "country")
    sewer_df = filter_df_by_user_access(sewer_df, "country")

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
            "popn_total",
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
        additional_columns=["s_safely_managed", "s_basic", "s_limited", "s_unimproved", "open_def", "popn_total"],
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
def _load_raw_service_data() -> pd.DataFrame:
    """
    Load service quality data from DuckDB with derived metrics (internal, cached).
    This loads all data without access filtering.
    """
    _ensure_pipeline()
    df = query("""
        SELECT *,
               date AS date_orig
        FROM v_service_quality
        ORDER BY date
    """)

    if "date_label" in df.columns:
        df = df.drop(columns=["date_label"], errors="ignore")
    if "date_orig" in df.columns:
        df = df.drop(columns=["date_orig"], errors="ignore")

    return df


def prepare_service_data() -> Dict[str, Any]:
    """
    Prepare service quality data for visualization.
    Returns a dictionary containing processed service data including:
    - Full service data DataFrame
    - Latest snapshots by zone
    - Aggregated time series for key metrics
    
    Note: Data is filtered based on the current user's access permissions.
    Access filtering is applied AFTER caching to ensure proper isolation.
    """
    # Load raw cached data
    df = _load_raw_service_data().copy()
    
    # Apply access control filtering based on user permissions
    # This happens on each call to ensure proper user isolation
    df = filter_df_by_user_access(df, "country")

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
        "access": "pages/2_Access_&_Coverage.py",
        "quality": "pages/3_Service_Quality.py",
        "finance": "pages/4_Financial_Health.py",
        "production": "pages/5_Production.py",
    }
    return mapping.get(scene_key)


# =============================================================================
# CANONICAL DATA LOADERS
# =============================================================================
# One cached read per table, shared by every page (including the Executive
# scene) so a table is cached exactly once. The `*_raw` loaders return
# unfiltered data; the public `load_*_data` wrappers apply per-user access
# control on a copy.

@st.cache_data
def load_billing_raw() -> pd.DataFrame:
    """Billing fact table (rows with a valid date), unfiltered. Cached once."""
    _ensure_pipeline()
    return query("SELECT * FROM billing WHERE date IS NOT NULL")


@st.cache_data
def load_financial_raw() -> pd.DataFrame:
    """Sanitation/financial service table, unfiltered. Cached once."""
    _ensure_pipeline()
    return query("SELECT * FROM fin_service")


@st.cache_data
def load_production_raw() -> pd.DataFrame:
    """Production table enriched with zone/country from the billing source map
    (production is keyed by source), unfiltered. Cached once."""
    _ensure_pipeline()
    prod = query("SELECT * FROM production")
    billing = load_billing_raw()
    if not billing.empty:
        source_map = billing[["source", "zone", "country"]].drop_duplicates().dropna()
        prod = prod.merge(source_map, on=["source", "country"], how="left")
        prod["zone"] = prod["zone"].fillna("Unknown")
    return prod


@st.cache_data
def load_national_raw() -> pd.DataFrame:
    """National accounts table, unfiltered. Cached once."""
    _ensure_pipeline()
    return query("SELECT * FROM national_accounts")


def load_billing_data() -> pd.DataFrame:
    """Billing with per-user access control applied."""
    return filter_df_by_user_access(load_billing_raw().copy(), "country")


def load_production_data() -> pd.DataFrame:
    """Production with per-user access control applied."""
    return filter_df_by_user_access(load_production_raw().copy(), "country")


def load_financial_data() -> pd.DataFrame:
    """Financial/service with per-user access control applied."""
    return filter_df_by_user_access(load_financial_raw().copy(), "country")
