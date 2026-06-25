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
# Design tokens — SINGLE SOURCE OF TRUTH shared with styles.css :root.
# -----------------------------------------------------------------------------
# Every value here is an EXACT mirror of a CSS custom property in styles.css so
# that charts and chrome read as one product. If you change a token here, change
# the matching --var in styles.css (and vice-versa). The previous palette used a
# warm Apple-grey set for charts while the chrome used cool Stripe slates, so
# figures never quite matched the cards around them — these are now reconciled.

FONT_FAMILY = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

# Text — mirrors --text-primary / --text-secondary / --text-tertiary
TEXT_PRIMARY = "#0f1729"
TEXT_SECONDARY = "#525f7f"
TEXT_TERTIARY = "#8792a3"

# Surfaces & hairlines — mirror --surface / --divider / --border
SURFACE = "#ffffff"
GRID = "#eef1f6"        # --divider  (hairline gridlines, same as chrome dividers)
AXIS_LINE = "#e4e9f1"   # --border   (axis baselines match card borders)

# Brand — mirrors --brand / --brand-strong
BRAND = "#0071e3"
BRAND_STRONG = "#0058b8"

# Categorical colorway — harmonised qualitative ramp anchored on the brand blue
# and sanitation teal, then tonally-consistent hues. Amber/green now equal the
# semantic warning/success tokens so a series and a status never clash.
DATA_SERIES = [
    "#0071e3",  # brand blue (water)
    "#00c1d4",  # teal (sanitation)
    "#b06000",  # amber  (= --warning)
    "#0e7e51",  # green  (= --success)
    "#6e3ad6",  # violet
    "#b3261e",  # red    (= --danger)
    "#0a6b8a",  # deep teal
    "#8792a3",  # neutral grey (= --text-tertiary, for "other")
]

# Stable named colors for domain semantics. Used selectively, not by default.
DATA_WATER = "#0071e3"        # --data-water
DATA_SANITATION = "#00c1d4"   # --data-sanitation

# Status / threshold colors — mirror --success / --warning / --danger.
STATUS_GOOD = "#0e7e51"
STATUS_WARNING = "#b06000"
STATUS_CRITICAL = "#b3261e"
STATUS_NEUTRAL = "#525f7f"

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
        bargap=0.36,
        bargroupgap=0.14,
        barcornerradius=6,
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
        # Title sits on its own line above the plot; give it room so a top
        # legend never collides with it.
        updates["title"] = dict(text=title, x=0, xanchor="left", y=0.97, yanchor="top")
    if show_legend is not None:
        updates["showlegend"] = show_legend
    if legend_top:
        # Place the legend top-RIGHT, opposite a left-aligned title on the same
        # band, so the two never overlap. Add top margin to fit the band.
        updates["legend"] = dict(
            orientation="h", y=1.02, yanchor="bottom", x=1.0, xanchor="right",
            font=dict(family=FONT_FAMILY, size=11, color=TEXT_SECONDARY),
            bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)",
        )
        updates["margin"] = dict(l=48, r=20, t=64 if title else 48, b=44)
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
