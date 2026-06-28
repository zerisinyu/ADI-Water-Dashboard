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

# Text — mirrors --text-primary / --text-secondary / --text-tertiary.
# Primary is a warm navy (matches the reference design + the MajiBot dark panel).
TEXT_PRIMARY = "#1f2d3a"
TEXT_SECONDARY = "#5b6b7b"
TEXT_TERTIARY = "#9aa6b2"

# Surfaces & hairlines — mirror --surface / --divider / --border
SURFACE = "#ffffff"
GRID = "#eef1f6"        # --divider  (hairline gridlines, same as chrome dividers)
AXIS_LINE = "#e4e9f1"   # --border   (axis baselines match card borders)

# Brand — mirrors --brand / --brand-strong. A softer, milder steel-blue (lower
# saturation than the old cobalt) — calmer to live with and the anchor for a
# restrained three-hue system: blue (dominant) · green · orange.
BRAND = "#3f6fa3"
BRAND_STRONG = "#2c5582"

# Categorical colorway — restricted to THREE hues per design: muted blue
# (dominant), sage green, terracotta (5-3-2 emphasis). Ordered blue → green →
# terracotta so a 2-series chart reads blue+green, a 3-series adds terracotta;
# remaining slots are lighter/darker variations of the same three hues. Matches
# the home-page design reference. Series green/terracotta equal the semantic
# success/warning tokens so a series and a status never clash.
DATA_SERIES = [
    "#3f6fa3",  # blue        (water / brand)
    "#5d9279",  # sage green  (sanitation / = --success)
    "#cd8551",  # terracotta  (accent / = --warning)
    "#5b9bc4",  # light blue
    "#2c5582",  # deep blue
    "#7da9d4",  # soft blue
    "#b5713c",  # deep terracotta
    "#9cc4dd",  # pale blue
]

# Stable named colors for domain semantics. Used selectively, not by default.
DATA_WATER = "#3f6fa3"        # --data-water (muted blue)
DATA_SANITATION = "#5d9279"   # --data-sanitation (sage green)

# Status / threshold colors — mirror --success / --warning / --danger. Tuned to
# the reference palette: sage green / terracotta / muted red.
STATUS_GOOD = "#5d9279"
STATUS_WARNING = "#cd8551"
STATUS_CRITICAL = "#c25f54"
STATUS_NEUTRAL = "#7b8794"

# Joint Monitoring Programme (JMP) ladder palette — preserved for the access
# page. These are reference standards from the JMP framework, not arbitrary.
JMP_COLORS = {
    "safely_managed": "#0071e3",
    "basic":          "#5ac8fa",
    "limited":        "#f5c518",
    "unimproved":     "#ec8a1a",
    "surface_water":  "#b3261e",
}

# Access / sanitation ladder bar palettes — the established reference colors from
# the Access & Coverage page. Kept as a DOCUMENTED EXCEPTION to the three-hue
# system (water/sanitation ladders read as a familiar five-step green→amber ramp).
# Single source of truth so the access page and the home-page ladders agree.
# Order: Safely Managed → Basic → Limited → Unimproved → (Surface water / Open def).
LADDER_COLORS = {
    "water":      ["#088BCE", "#48BFE7", "#FDEE79", "#FFD94F", "#FFB02B"],
    "sanitation": ["#349438", "#49B754", "#FDEE79", "#FFD94F", "#FFB02B"],
}

# Tokenised continuous scales — replace ad-hoc RdYlGn / Reds / raw-hex scales so
# every heatmap/choropleth/gradient reads from the same palette.
# Sequential: light → muted brand blue (intensity, coverage, volume).
SEQ_BLUE = [
    [0.0, "#eef3f8"],
    [0.25, "#c3cfdb"],
    [0.5, "#9fbdda"],
    [0.75, "#5b9bc4"],
    [1.0, "#2c5582"],
]
# Sequential warm (debt, losses — "more is worse").
SEQ_WARM = [
    [0.0, "#fbf6f1"],
    [0.5, "#e2cf9a"],
    [1.0, "#cd8551"],
]


def performance_scale(higher_is_better: bool = True) -> list:
    """Diverging red→amber→green scale built from the status tokens.

    For `higher_is_better` metrics (e.g. collection rate) low=red, high=green.
    For `lower_is_better` (e.g. NRW) the ramp is reversed.
    """
    ramp = [
        [0.0, STATUS_CRITICAL],
        [0.5, STATUS_WARNING],
        [1.0, STATUS_GOOD],
    ]
    if higher_is_better:
        return ramp
    return [[1.0 - stop, color] for stop, color in reversed(ramp)]


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


def apply_chart_theme(dark: bool) -> None:
    """Flip the registered chart template between light and dark.

    Called once per run before any figure is built, so every chart inherits the
    current theme. In dark mode the plot/paper backgrounds go transparent (the
    dark page shows through) and the text/grid/axis colors lighten.
    """
    register_adi_template()
    lay = pio.templates[_TEMPLATE_NAME].layout
    if dark:
        text, sub = "#e9eef3", "#aab4be"
        grid, axis = "#2b3a49", "#3a4c5e"
        paper = "rgba(0,0,0,0)"
    else:
        text, sub = TEXT_PRIMARY, TEXT_SECONDARY
        grid, axis = GRID, AXIS_LINE
        paper = SURFACE

    lay.paper_bgcolor = paper
    lay.plot_bgcolor = paper
    lay.font.color = text
    lay.title.font.color = text
    lay.legend.font.color = sub
    for ax in (lay.xaxis, lay.yaxis):
        ax.gridcolor = grid
        ax.linecolor = axis
        ax.zerolinecolor = axis
        ax.tickcolor = axis
        ax.tickfont.color = sub
        ax.title.font.color = sub
    pio.templates.default = (f"plotly_dark+{_TEMPLATE_NAME}" if dark
                             else f"plotly_white+{_TEMPLATE_NAME}")


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


def _is_categorical(values) -> bool:
    """True when axis values are discrete labels (strings), not numbers/dates."""
    try:
        sample = next(v for v in values if v is not None)
    except (StopIteration, TypeError):
        return False
    return isinstance(sample, str)


def _autosize_category_bars(fig: go.Figure, *, target_slots: int = 5) -> None:
    """Auto-size bars to a comfortable width on sparse categorical charts.

    Plotly bars stretch to fill the container, so a couple of categories render
    as absurdly thick slabs. Rather than capping per-trace ``width`` (which
    fights grouped-bar offsets), we pad the *category axis range* so a few bars
    sit centred with whitespace around them.

    The padding is **group-aware**: grouped bars already divide each category
    slot among the series, so they're padded far more gently (otherwise 4
    categories × 2 series become spindly). Stacked / single-series charts use the
    full target. Only categorical (string) axes are touched — numeric/datetime
    axes (year timelines) are left alone.
    """
    bar_traces = [t for t in fig.data if getattr(t, "type", "") == "bar"]
    if not bar_traces:
        return
    horizontal = (getattr(bar_traces[0], "orientation", "v") or "v") == "h"
    cats = None
    for t in bar_traces:
        vals = t.y if horizontal else t.x
        if vals is not None and len(vals) > 0:
            cats = list(vals)
            break
    if not cats or not _is_categorical(cats):
        return
    n = len(dict.fromkeys(cats))  # distinct, order-preserving
    if n <= 0:
        return

    barmode = getattr(fig.layout, "barmode", None)
    is_grouped = len(bar_traces) > 1 and barmode not in ("stack", "relative", "overlay")
    # Grouped charts divide each slot among series, so only the very smallest
    # (n<=2) ever balloon; 3+ grouped categories already fill the width well.
    if is_grouped:
        effective_target = 4 if n <= 2 else n
    else:
        effective_target = target_slots
    if n >= effective_target:
        return
    pad = (effective_target - n) / 2.0
    rng = [-0.5 - pad, (n - 1) + 0.5 + pad]
    (fig.update_yaxes if horizontal else fig.update_xaxes)(range=rng)


def style_bar(
    fig: go.Figure,
    *,
    title: Optional[str] = None,
    height: int = 340,
    show_legend: Optional[bool] = None,
    legend_top: bool = False,
    autosize: bool = True,
    target_slots: int = 6,
    show_values: bool = False,
    value_fmt: str = "%{value}",
) -> go.Figure:
    """Apply ADI defaults tuned for bar charts.

    Wraps :func:`style_fig` and, by default, auto-sizes sparse categorical bar
    charts to a comfortable width (see :func:`_autosize_category_bars`).

    - ``autosize`` / ``target_slots``: control the auto-width behaviour.
    - ``show_values``: draw direct value labels above the bars (best for charts
      with a handful of categories — lets the reader skip the axis). ``value_fmt``
      is a Plotly ``texttemplate`` (e.g. ``"%{value:.0f}%"`` or ``"$%{value:,.0f}"``).
    """
    style_fig(fig, title=title, height=height, show_legend=show_legend, legend_top=legend_top)
    if autosize:
        _autosize_category_bars(fig, target_slots=target_slots)
    if show_values:
        fig.update_traces(
            texttemplate=value_fmt, textposition="outside", cliponaxis=False,
            textfont=dict(family=FONT_FAMILY, size=11, color=TEXT_SECONDARY),
            selector=dict(type="bar"),
        )
    return fig


def format_compact(value: float, *, prefix: str = "", suffix: str = "") -> str:
    """Human-readable compact number: 12_700_000_000 -> '$12.7B'.

    Used for value labels and hover strings so large figures stay legible.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    sign = "-" if v < 0 else ""
    v = abs(v)
    for threshold, unit in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if v >= threshold:
            return f"{sign}{prefix}{v / threshold:.1f}{unit}{suffix}"
    return f"{sign}{prefix}{v:,.0f}{suffix}"


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


def status_heatmap(month_labels: list, rows: list, *, height: int = 240) -> go.Figure:
    """Build a pillar × month status heatmap.

    Each row is a dict ``{label, values, good, warning, higher_is_better, fmt}``
    where ``values`` is aligned to ``month_labels``. Cells are colored good /
    warning / critical by threshold (via :func:`status_label`) and annotated with
    the actual value. Designed as the at-a-glance object on the executive page —
    trajectory reads left→right, cross-pillar comparison reads top→bottom.
    """
    y_labels = [r["label"] for r in rows]
    z, text = [], []
    _rank = {"critical": 0, "warning": 1, "good": 2}
    for r in rows:
        zrow, trow = [], []
        for v in r["values"]:
            if v is None or v != v:  # None or NaN
                zrow.append(None)
                trow.append("")
            else:
                lab = status_label(v, good=r["good"], warning=r["warning"],
                                   higher_is_better=r.get("higher_is_better", True))
                zrow.append(_rank[lab])
                trow.append(r.get("fmt", "{:.0f}").format(v))
        z.append(zrow)
        text.append(trow)

    # Discrete three-step colorscale: critical → warning → good.
    colorscale = [
        [0.0, STATUS_CRITICAL], [0.33, STATUS_CRITICAL],
        [0.34, STATUS_WARNING], [0.66, STATUS_WARNING],
        [0.67, STATUS_GOOD], [1.0, STATUS_GOOD],
    ]
    fig = go.Figure(go.Heatmap(
        z=z, x=month_labels, y=y_labels, text=text,
        texttemplate="%{text}", textfont=dict(color="#ffffff", size=11),
        colorscale=colorscale, zmin=0, zmax=2, showscale=False,
        xgap=3, ygap=3, hoverongaps=False,
        hovertemplate="%{y} · %{x}: %{text}<extra></extra>",
    ))
    style_fig(fig, height=height, show_legend=False)
    fig.update_yaxes(autorange="reversed", showgrid=False, ticksuffix="  ")
    fig.update_xaxes(showgrid=False, side="top")
    return fig


# -----------------------------------------------------------------------------
# Convenience
# -----------------------------------------------------------------------------

def colorway() -> list[str]:
    """Return a copy of the default categorical colorway."""
    return list(DATA_SERIES)


def color_for(index: int) -> str:
    """Pick a color from the default series by index (wraps)."""
    return DATA_SERIES[index % len(DATA_SERIES)]
