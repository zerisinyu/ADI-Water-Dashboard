"""
PDF report export using fpdf2.

Generates a professional PDF with cover page, KPI summary table,
and narrative sections from the board brief or monthly report.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def generate_pdf_report(
    title: str = "Water Utility Performance Report",
    period: str = "Current Period",
    country: str = "All",
    markdown_content: str = "",
    kpis: Optional[dict[str, str]] = None,
) -> bytes:
    """
    Generate a PDF report from markdown content and KPI data.

    Args:
        title: Report title for the cover page.
        period: Reporting period label.
        country: Country filter applied.
        markdown_content: Markdown text (from board brief or monthly report).
        kpis: Optional dict of KPI label -> value for summary table.

    Returns:
        PDF file as bytes, ready for st.download_button.
    """
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ---- Cover Page ----
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 28)
    pdf.ln(60)
    pdf.cell(0, 15, title, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 16)
    pdf.ln(10)
    pdf.cell(0, 10, f"Reporting Period: {period}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, f"Country: {country}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)
    pdf.set_font("Helvetica", "I", 11)
    pdf.cell(
        0, 10,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        align="C", new_x="LMARGIN", new_y="NEXT",
    )
    pdf.cell(0, 10, "ADI Water Utility Performance Platform", align="C", new_x="LMARGIN", new_y="NEXT")

    # ---- KPI Summary Table ----
    if kpis:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 12, "Key Performance Indicators", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(8)

        pdf.set_font("Helvetica", "B", 11)
        col_w = [90, 90]
        pdf.set_fill_color(59, 130, 246)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(col_w[0], 10, "Metric", border=1, fill=True)
        pdf.cell(col_w[1], 10, "Value", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 11)
        fill = False
        for label, value in kpis.items():
            if fill:
                pdf.set_fill_color(240, 249, 255)
            else:
                pdf.set_fill_color(255, 255, 255)
            pdf.cell(col_w[0], 9, str(label), border=1, fill=True)
            pdf.cell(col_w[1], 9, str(value), border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
            fill = not fill

    # ---- Report Body ----
    if markdown_content:
        pdf.add_page()
        _render_markdown_to_pdf(pdf, markdown_content)

    return pdf.output()


def _render_markdown_to_pdf(pdf, md_text: str) -> None:
    """Convert simplified markdown to PDF text blocks."""
    lines = md_text.strip().split("\n")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            pdf.ln(4)
            continue

        # Headings
        if stripped.startswith("# "):
            pdf.set_font("Helvetica", "B", 18)
            pdf.cell(0, 12, stripped[2:], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)
        elif stripped.startswith("## "):
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 10, stripped[3:], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)
        elif stripped.startswith("### "):
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 9, stripped[4:], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            pdf.set_font("Helvetica", "", 10)
            # Bullet point
            text = stripped[2:]
            text = text.replace("**", "")  # Strip bold markers
            pdf.cell(8, 7, chr(8226))  # bullet character
            pdf.multi_cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
        elif stripped.startswith("|"):
            # Table row — simplified rendering
            pdf.set_font("Helvetica", "", 9)
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if cells and all(c.replace("-", "").strip() == "" for c in cells):
                continue  # Skip separator rows
            col_w = 170 / max(len(cells), 1)
            for cell_text in cells:
                cell_text = cell_text.replace("**", "")
                pdf.cell(col_w, 7, cell_text[:30], border=1)
            pdf.ln()
        else:
            # Regular paragraph
            pdf.set_font("Helvetica", "", 10)
            clean = stripped.replace("**", "")
            pdf.multi_cell(0, 6, clean, new_x="LMARGIN", new_y="NEXT")
