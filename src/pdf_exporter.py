import os
from typing import List

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as rl_canvas


# Courier character width is 0.6× the font size (fixed pitch)
_COURIER_WIDTH_RATIO = 0.6


_MARGIN = 36.0   # 0.5 inch in points


def _font_size_for_lines(lines: List[str], page_width: float, margin: float) -> float:
    """Choose a font size so the widest line fits within the available width.

    Clamped to 6–9 pt so the result is always legible and never oversized.
    """
    available = page_width - 2 * margin
    if not lines:
        return 8.0
    max_chars = max(len(line) for line in lines) or 1
    size = available / (max_chars * _COURIER_WIDTH_RATIO)
    return max(6.0, min(9.0, size))


def export_pdf(tab_text: str, output_path: str, title: str = "Tablature") -> None:
    """
    Render `tab_text` as a monospaced PDF using Courier on 8.5 × 11 paper
    with 0.5-inch margins.  The caller is expected to have already wrapped
    the tab to PDF_MAX_CHARS columns so lines fit at the chosen font size.
    """
    width, height = letter
    margin = _MARGIN
    title_gap = 30.0

    lines = tab_text.splitlines()
    font_size = _font_size_for_lines(lines, width, margin)
    line_height = font_size * 1.35

    c = rl_canvas.Canvas(output_path, pagesize=letter)

    def new_page() -> float:
        c.showPage()
        return height - margin

    # Title
    c.setFont("Courier-Bold", 13)
    c.drawString(margin, height - margin, title)
    y = height - margin - title_gap

    c.setFont("Courier", font_size)

    for line in lines:
        if y < margin + line_height:
            y = new_page()
            c.setFont("Courier", font_size)
        c.drawString(margin, y, line)
        y -= line_height

    c.save()
