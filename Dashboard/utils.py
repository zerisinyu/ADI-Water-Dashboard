from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st


# Base data directory (shared across pages)
DATA_DIR = Path(__file__).resolve().parents[1] / "Data"


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
    
    # Month filter logic (only show for Monthly/Daily periods)
    if show_month or result['period'] in ['Monthly', 'Daily']:
        # Add month selector in a new row if needed
        month_names = ['All', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        default_month_idx = 0
        if "selected_month" in st.session_state and st.session_state.selected_month in month_names:
            default_month_idx = month_names.index(st.session_state.selected_month)
        
        result['month'] = st.selectbox(
            "Month",
            month_names,
            index=default_month_idx,
            key=f"{key_prefix}_month"
        )
    
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

def render_page_hero(
    title: str,
    icon: str,
    filters: Dict[str, str],
    metrics: Optional[List[Dict[str, str]]] = None,
    data_freshness: Optional[str] = None
) -> None:
    """
    Render a consistent page hero section with title, filter pills, and optional metrics.
    
    Args:
        title: Page title text
        icon: Emoji icon for the page
        filters: Dict of filter labels to values (e.g., {"Country": "Uganda", "Zone": "All"})
        metrics: Optional list of metric dicts with keys: label, value, delta (optional)
        data_freshness: Optional timestamp string for data freshness indicator
    """
    from datetime import datetime
    
    freshness = data_freshness or datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # Build filter pills HTML
    filter_pills = ''.join([
        f'<span class="pill">📍 {v}</span>' if k.lower() == 'country' else
        f'<span class="pill">🗺️ {v}</span>' if k.lower() in ['zone', 'city'] else
        f'<span class="pill">📅 {v}</span>' if k.lower() in ['year', 'period'] else
        f'<span class="pill">{v}</span>'
        for k, v in filters.items() if v and v != 'All'
    ])
    
    # Build metrics HTML if provided
    metrics_html = ''
    if metrics:
        metrics_items = ''
        for m in metrics:
            delta_class = 'positive' if m.get('delta', '').startswith('+') else 'negative' if m.get('delta', '').startswith('-') else ''
            delta_html = f'<span class="page-hero-stat-delta {delta_class}">{m.get("delta", "")}</span>' if m.get('delta') else ''
            metrics_items += f'''
            <div class="page-hero-stat">
                <p class="page-hero-stat-label">{m['label']}</p>
                <h3 class="page-hero-stat-value">{m['value']}</h3>
                {delta_html}
            </div>
            '''
        metrics_html = f'<div class="page-hero-stats">{metrics_items}</div>'
    
    st.markdown(f'''
    <div class="page-hero">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
            <div>
                <h1 class="page-hero-title">{icon} {title}</h1>
                <div class="page-hero-filters">{filter_pills}</div>
            </div>
            <div style="text-align: right; color: #6b7280; font-size: 0.85rem;">
                📅 Last refreshed: {freshness}
            </div>
        </div>
        {metrics_html}
    </div>
    ''', unsafe_allow_html=True)


def render_section_header(title: str, domain: Optional[str] = None) -> None:
    """
    Render a consistent section header with optional domain styling.
    
    Args:
        title: Section title (can include emoji)
        domain: Optional domain type ('water' or 'sanitation') for colored border
    """
    domain_class = f'section-header-{domain}' if domain in ['water', 'sanitation'] else ''
    st.markdown(f'<div class="section-header {domain_class}">{title}</div>', unsafe_allow_html=True)


def render_domain_pill(domain: str, text: Optional[str] = None) -> str:
    """
    Return HTML for a domain indicator pill.
    
    Args:
        domain: 'water' or 'sanitation'
        text: Optional custom text (defaults to domain name)
    """
    label = text or ('💧 Water' if domain == 'water' else '🚿 Sanitation')
    return f'<span class="domain-pill domain-pill-{domain}">{label}</span>'


def render_granularity_badge(frequency: str, granularity: str) -> str:
    """
    Return HTML for a data granularity badge.
    
    Args:
        frequency: 'daily', 'monthly', or 'annual'
        granularity: Level description (e.g., 'zone', 'city', 'source')
    """
    freq_lower = frequency.lower()
    return f'''
    <div style="display: inline-flex; gap: 8px; align-items: center;">
        <span class="granularity-badge granularity-{freq_lower}">{frequency.title()}</span>
        <span style="color: #64748b; font-size: 12px;">at {granularity} level</span>
    </div>
    '''


def render_chart_container(title: str, source: Optional[str] = None, help_text: Optional[str] = None) -> None:
    """
    Render opening HTML for a chart container with header.
    Remember to close with st.markdown('</div>', unsafe_allow_html=True) after the chart.
    
    Args:
        title: Chart title
        source: Optional data source attribution
        help_text: Optional tooltip text
    """
    help_icon = f'<span title="{help_text}" style="cursor: help; color: #94a3b8; margin-left: 8px;">ⓘ</span>' if help_text else ''
    source_html = f'<span class="chart-meta">Source: {source}</span>' if source else ''
    
    st.markdown(f'''
    <div class="chart-container">
        <div class="chart-header">
            <h4 class="chart-title">{title}{help_icon}</h4>
            {source_html}
        </div>
    ''', unsafe_allow_html=True)


def render_empty_state(icon: str, title: str, description: str) -> None:
    """
    Render an empty state message when no data is available.
    
    Args:
        icon: Emoji for the empty state
        title: Main message title
        description: Helpful description text
    """
    st.markdown(f'''
    <div class="empty-state">
        <div class="empty-state-icon">{icon}</div>
        <div class="empty-state-title">{title}</div>
        <div class="empty-state-description">{description}</div>
    </div>
    ''', unsafe_allow_html=True)


@st.cache_data
def load_csv_data() -> Dict[str, pd.DataFrame]:
    """Read sewer and water access CSV datasets from disk and cache the resulting DataFrames."""
    csv_map = {
        "sewer": "s_access.csv",
        "water": "w_access.csv",
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
def _load_raw_access_data() -> Dict[str, Any]:
    """
    Load and process raw access data (internal, cached).
    This loads all data without access filtering.
    """
    csv_data = load_csv_data()
    water_df = normalise_access_df(csv_data["water"], prefix="w_", extra_pct_cols=["municipal_coverage"])
    sewer_df = normalise_access_df(csv_data["sewer"], prefix="s_")
    
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
    Load and process raw service data (internal, cached).
    This loads all data without access filtering.
    """
    service_path = DATA_DIR / "sw_service.csv"
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
# DATA LOADING HELPERS (For AI Queries)
# =============================================================================

@st.cache_data
def _load_billing_data_raw() -> pd.DataFrame:
    """Load raw billing data with caching (no access control - internal use)."""
    billing_path = DATA_DIR / "billing.csv"
    if billing_path.exists():
        df = pd.read_csv(billing_path, low_memory=False)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
        return df
    return pd.DataFrame()


def load_billing_data() -> pd.DataFrame:
    """Load billing data with access control applied per-user."""
    df = _load_billing_data_raw()
    # Apply access control AFTER cache to ensure user-specific filtering
    return filter_df_by_user_access(df, "country")


@st.cache_data
def _load_production_data_raw() -> pd.DataFrame:
    """Load raw production data with caching (no access control - internal use)."""
    prod_path = DATA_DIR / "production.csv"
    if prod_path.exists():
        df = pd.read_csv(prod_path, low_memory=False)
        if 'date_YYMMDD' in df.columns:
            df['date'] = pd.to_datetime(df['date_YYMMDD'], format='%Y/%m/%d', errors='coerce')
        return df
    return pd.DataFrame()


def load_production_data() -> pd.DataFrame:
    """Load production data with access control applied per-user."""
    df = _load_production_data_raw()
    # Apply access control AFTER cache to ensure user-specific filtering
    return filter_df_by_user_access(df, "country")


@st.cache_data
def _load_financial_data_raw() -> pd.DataFrame:
    """Load raw financial data with caching (no access control - internal use)."""
    fin_path = DATA_DIR / "all_fin_service.csv"
    if fin_path.exists():
        df = pd.read_csv(fin_path, low_memory=False)
        if 'date_MMYY' in df.columns:
            df['date'] = pd.to_datetime(df['date_MMYY'], format='%b/%y', errors='coerce')
        return df
    return pd.DataFrame()


def load_financial_data() -> pd.DataFrame:
    """Load financial data with access control applied per-user."""
    df = _load_financial_data_raw()
    # Apply access control AFTER cache to ensure user-specific filtering
    return filter_df_by_user_access(df, "country")
