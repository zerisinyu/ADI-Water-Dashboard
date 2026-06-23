"""
ADI Dashboard — Plotly chart system.

Single source of truth for chart styling so every figure across every page
inherits the same typography, colors, gridlines, and spacing. Pages should
import from here rather than calling update_layout() with bespoke styling.
"""
from __future__ import annotations

from typing import Iterable, Optional

import plotly.graph_objects as go
import plotly.io as pio


# -----------------------------------------------------------------------------
# Design tokens (mirror styles.css — keep in sync)
# -----------------------------------------------------------------------------

FONT_FAMILY = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

TEXT_PRIMARY = "#1d1d1f"
TEXT_SECONDARY = "#6e6e73"
TEXT_TERTIARY = "#86868b"

SURFACE = "#ffffff"
GRID = "rgba(0, 0, 0, 0.06)"
AXIS_LINE = "rgba(0, 0, 0, 0.12)"

BRAND = "#0071e3"
BRAND_STRONG = "#0058b8"

# Chart-only data colorway. Used for default categorical encoding.
DATA_SERIES = [
    "#0071e3",  # blue (water default)
    "#00c1d4",  # teal (sanitation default)
    "#b25e09",  # amber
    "#1d8348",  # green
    "#6e3ad6",  # violet
    "#b3261e",  # red
    "#0a6b8a",  # deep teal
    "#7d6608",  # ochre
]

# Stable named colors for domain semantics. Used selectively, not by default.
DATA_WATER = "#0071e3"
DATA_SANITATION = "#00c1d4"

# Status / threshold colors (muted, business-grade).
STATUS_GOOD = "#1d8348"
STATUS_WARNING = "#b25e09"
STATUS_CRITICAL = "#b3261e"
STATUS_NEUTRAL = "#6e6e73"

# Joint Monitoring Programme (JMP) ladder palette — preserved for the access
# page. These are reference standards from the JMP framework, not arbitrary.
JMP_COLORS = {
    "safely_managed": "#0071e3",
    "basic":          "#5ac8fa",
    "limited":        "#f5c518",
    "unimproved":     "#ec8a1a",
    "surface_water":  "#b3261e",
}


# -----------------------------------------------------------------------------
# Template registration
# -----------------------------------------------------------------------------

_TEMPLATE_NAME = "adi"
_REGISTERED = False


def register_adi_template() -> None:
    """Register the ADI Plotly template and set it as the global default.

    Idempotent — safe to call multiple times.
    """
    global _REGISTERED
    if _REGISTERED:
        return

    layout = go.Layout(
        font=dict(family=FONT_FAMILY, size=12, color=TEXT_PRIMARY),
        title=dict(
            font=dict(family=FONT_FAMILY, size=14, color=TEXT_PRIMARY),
            x=0,
            xanchor="left",
            y=0.97,
            yanchor="top",
            pad=dict(l=4, t=4, b=8),
        ),
        plot_bgcolor=SURFACE,
        paper_bgcolor=SURFACE,
        colorway=DATA_SERIES,
        margin=dict(l=44, r=16, t=44, b=44),
        # Bar geometry — slimmer, well-spaced, softly rounded bars are the
        # single biggest readability win for grouped/stacked charts. Set once
        # here so every figure inherits it instead of chunky full-width bars.
        bargap=0.34,
        bargroupgap=0.12,
        barcornerradius=4,
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=TEXT_PRIMARY,
            bordercolor=TEXT_PRIMARY,
            font=dict(family=FONT_FAMILY, size=12, color="#ffffff"),
            align="left",
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.18,
            xanchor="left",
            x=0,
            font=dict(family=FONT_FAMILY, size=11, color=TEXT_SECONDARY),
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            gridcolor=GRID,
            linecolor=AXIS_LINE,
            zerolinecolor=AXIS_LINE,
            zerolinewidth=1,
            tickcolor=AXIS_LINE,
            ticks="outside",
            ticklen=4,
            tickfont=dict(family=FONT_FAMILY, size=11, color=TEXT_SECONDARY),
            title=dict(
                font=dict(family=FONT_FAMILY, size=11, color=TEXT_SECONDARY),
                standoff=8,
            ),
            showline=False,
            mirror=False,
        ),
        yaxis=dict(
            gridcolor=GRID,
            linecolor=AXIS_LINE,
            zerolinecolor=AXIS_LINE,
            zerolinewidth=1,
            tickcolor=AXIS_LINE,
            ticks="outside",
            ticklen=4,
            tickfont=dict(family=FONT_FAMILY, size=11, color=TEXT_SECONDARY),
            title=dict(
                font=dict(family=FONT_FAMILY, size=11, color=TEXT_SECONDARY),
                standoff=8,
            ),
            showline=False,
            mirror=False,
        ),
    )

    pio.templates[_TEMPLATE_NAME] = go.layout.Template(layout=layout)
    pio.templates.default = f"plotly_white+{_TEMPLATE_NAME}"
    _REGISTERED = True


# -----------------------------------------------------------------------------
# Chart helpers
# -----------------------------------------------------------------------------

def style_fig(
    fig: go.Figure,
    *,
    title: Optional[str] = None,
    height: int = 320,
    show_legend: Optional[bool] = None,
    legend_top: bool = False,
) -> go.Figure:
    """Apply ADI defaults to an existing figure.

    Most pages should call this once after building a figure rather than
    setting layout properties piecemeal. Returns the same figure for chaining.
    """
    register_adi_template()
    updates: dict = {"height": height, "template": pio.templates.default}
    if title is not None:
        updates["title"] = dict(text=title, x=0, xanchor="left")
    if show_legend is not None:
        updates["showlegend"] = show_legend
    if legend_top:
        updates["legend"] = dict(orientation="h", y=1.08, x=0, yanchor="bottom", xanchor="left")
    fig.update_layout(**updates)
    return fig


def style_bar(
    fig: go.Figure,
    *,
    title: Optional[str] = None,
    height: int = 340,
    show_legend: Optional[bool] = None,
    legend_top: bool = False,
    max_bar_width: Optional[float] = None,
) -> go.Figure:
    """Apply ADI defaults tuned for bar charts.

    Wraps :func:`style_fig` and, for charts with only a handful of categories,
    caps the bar thickness so two or three bars don't balloon to fill the whole
    container width. ``max_bar_width`` is in data-axis units; when omitted a
    sensible cap is applied only if the trace has <= 5 categories.
    """
    style_fig(fig, title=title, height=height, show_legend=show_legend, legend_top=legend_top)
    bar_traces = [t for t in fig.data if getattr(t, "type", "") == "bar"]
    # Only cap explicit bar width for SINGLE-series charts — setting width on
    # grouped bars fights plotly's offset logic and causes overlap. Grouped
    # charts rely on the template's bargap/bargroupgap instead.
    if max_bar_width is not None:
        fig.update_traces(width=max_bar_width, selector=dict(type="bar"))
    elif len(bar_traces) == 1:
        try:
            n_cat = len(bar_traces[0].x) if bar_traces[0].x is not None else 0
        except TypeError:
            n_cat = 0
        if 0 < n_cat <= 4:
            # Keep 2-4 standalone bars slim rather than ballooning full-width.
            fig.update_traces(width=0.55, selector=dict(type="bar"))
    return fig


def apply_axis_currency(fig: go.Figure, axis: str = "y", prefix: str = "$") -> go.Figure:
    """Format an axis as currency with thousand separators."""
    cfg = dict(tickprefix=prefix, separatethousands=True)
    if axis == "y":
        fig.update_yaxes(**cfg)
    else:
        fig.update_xaxes(**cfg)
    return fig


def apply_axis_percent(fig: go.Figure, axis: str = "y") -> go.Figure:
    """Format an axis as percentage values (assumes data is 0-100, not 0-1)."""
    cfg = dict(ticksuffix="%")
    if axis == "y":
        fig.update_yaxes(**cfg)
    else:
        fig.update_xaxes(**cfg)
    return fig


def apply_axis_thousands(fig: go.Figure, axis: str = "y") -> go.Figure:
    """Add thousand separators to numeric ticks."""
    cfg = dict(separatethousands=True)
    if axis == "y":
        fig.update_yaxes(**cfg)
    else:
        fig.update_xaxes(**cfg)
    return fig


# -----------------------------------------------------------------------------
# Threshold helper
# -----------------------------------------------------------------------------

def status_color(value: float, *, good: float, warning: float, higher_is_better: bool = True) -> str:
    """Return a status color hex based on thresholds.

    Replaces inline conditional color logic scattered across pages.
    """
    if higher_is_better:
        if value >= good:
            return STATUS_GOOD
        if value >= warning:
            return STATUS_WARNING
        return STATUS_CRITICAL
    else:
        if value <= good:
            return STATUS_GOOD
        if value <= warning:
            return STATUS_WARNING
        return STATUS_CRITICAL


def status_label(value: float, *, good: float, warning: float, higher_is_better: bool = True) -> str:
    """Return a 'good' / 'warning' / 'critical' label for the given value."""
    if higher_is_better:
        if value >= good:
            return "good"
        if value >= warning:
            return "warning"
        return "critical"
    else:
        if value <= good:
            return "good"
        if value <= warning:
            return "warning"
        return "critical"


# -----------------------------------------------------------------------------
# Convenience
# -----------------------------------------------------------------------------

def colorway() -> list[str]:
    """Return a copy of the default categorical colorway."""
    return list(DATA_SERIES)


def color_for(index: int) -> str:
    """Pick a color from the default series by index (wraps)."""
    return DATA_SERIES[index % len(DATA_SERIES)]
