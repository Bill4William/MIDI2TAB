"""
Printable reference sheets for the Fretboard Explorer.

Scales are drawn as full-width neck diagrams (open → 12th fret); chords are
drawn as classic vertical chord boxes, four per row. Items keep the order
the user chose, and pages break automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple, Union

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas as rl_canvas

_MARGIN = 36.0          # 0.5 inch
_GAP = 14.0             # space between items
_CHORDS_PER_ROW = 4
_MUTED = -1

_ROOT_FILL = (0.91, 0.35, 0.05)
_NOTE_FILL = (0.15, 0.15, 0.15)
_INLAYS = (3, 5, 7, 9)


@dataclass
class ScaleItem:
    title: str
    subtitle: str
    string_names: List[str]                       # high → low
    cells: Dict[Tuple[int, int], Tuple[str, bool]]  # (string, fret) → (label, is_root)
    num_frets: int = 12


@dataclass
class ChordItem:
    title: str
    subtitle: str
    string_names: List[str]                       # high → low
    frets: Tuple[int, ...]                        # high → low, -1 = muted
    labels: List[str] = field(default_factory=list)   # per string, high → low
    roots: List[bool] = field(default_factory=list)   # per string, high → low


SheetItem = Union[ScaleItem, ChordItem]


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _dot(c, x: float, y: float, r: float, label: str, root: bool) -> None:
    c.setFillColorRGB(*(_ROOT_FILL if root else _NOTE_FILL))
    c.circle(x, y, r, stroke=0, fill=1)
    if label:
        c.setFillColorRGB(1, 1, 1)
        size = min(r * 1.15, 8.0) if len(label) < 3 else min(r * 0.95, 7.0)
        c.setFont("Helvetica-Bold", size)
        c.drawCentredString(x, y - size * 0.35, label)
    c.setFillColorRGB(0, 0, 0)


def _scale_height(item: ScaleItem) -> float:
    return 30 + _scale_row_h(item) * len(item.string_names) + 14


def _scale_row_h(item: ScaleItem) -> float:
    return max(9.0, min(16.0, 150.0 / max(len(item.string_names), 1)))


def _draw_scale(c, item: ScaleItem, x0: float, top: float, width: float,
                lefty: bool) -> None:
    n = len(item.string_names)
    rh = _scale_row_h(item)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x0, top - 11, item.title)
    c.setFont("Helvetica", 8)
    c.drawString(x0, top - 22, item.subtitle)

    label_w = 22.0
    cols = item.num_frets + 1
    cw = (width - label_w) / cols
    y_top = top - 30
    y_of = lambda s: y_top - rh * (s + 0.5)
    board_bottom = y_top - rh * n

    def xe(col: float) -> float:
        x = x0 + label_w + col * cw
        return (2 * x0 + width) - x if lefty else x

    def xc(col: int) -> float:
        return (xe(col) + xe(col + 1)) / 2

    # Fret numbers along the bottom
    c.setFont("Helvetica", 6.5)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    for f in range(1, cols):
        c.drawCentredString(xc(f), board_bottom - 9, str(f))
    c.setFillColorRGB(0, 0, 0)

    # Inlays
    c.setFillColorRGB(0.85, 0.85, 0.85)
    mid = (y_top + board_bottom) / 2
    for f in _INLAYS:
        c.circle(xc(f), mid, 2.4, stroke=0, fill=1)
    for dy in (rh * n * 0.2, -rh * n * 0.2):
        c.circle(xc(12), mid + dy, 2.4, stroke=0, fill=1)
    c.setFillColorRGB(0, 0, 0)

    # Frets (nut thick) and strings
    for f in range(1, cols + 1):
        c.setLineWidth(2.5 if f == 1 else 0.6)
        c.line(xe(f), y_top, xe(f), board_bottom)
    c.setLineWidth(0.5)
    for s in range(n):
        c.line(xe(0), y_of(s), xe(cols), y_of(s))
        c.setFont("Helvetica-Bold", 8)
        lx = x0 + label_w / 2 - 3 if not lefty else x0 + width - label_w / 2 + 3
        c.drawCentredString(lx, y_of(s) - 3, item.string_names[s])

    r = min(cw, rh) * 0.42
    for (s, f), (label, root) in item.cells.items():
        if 0 <= s < n and 0 <= f < cols:
            _dot(c, xc(f), y_of(s), r, label, root)


def _chord_height(item: ChordItem) -> float:
    return 30 + 5 * 18 + 22


def _draw_chord(c, item: ChordItem, x0: float, top: float, width: float,
                lefty: bool) -> None:
    n = len(item.string_names)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(x0 + width / 2, top - 12, item.title)
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(x0 + width / 2, top - 22, item.subtitle)

    rows = 5
    fh = 18.0
    grid_w = min(width - 24, 14.0 * max(n - 1, 1))
    gx0 = x0 + (width - grid_w) / 2
    sp = grid_w / max(n - 1, 1)
    y_top = top - 38
    fretted = [f for f in item.frets if f > 0]
    start = 1 if not fretted or max(fretted) <= rows else min(fretted)

    # Column for string s (high → low index); low string on the left.
    def sx(s: int) -> float:
        col = (n - 1 - s) if not lefty else s
        return gx0 + col * sp if n > 1 else gx0 + grid_w / 2

    # Grid
    c.setLineWidth(0.6)
    for r_ in range(rows + 1):
        y = y_top - r_ * fh
        c.setLineWidth(2.5 if (r_ == 0 and start == 1) else 0.6)
        c.line(gx0, y, gx0 + grid_w, y)
    c.setLineWidth(0.6)
    for s in range(n):
        c.line(sx(s), y_top, sx(s), y_top - rows * fh)
    if start > 1:
        c.setFont("Helvetica", 8)
        side = gx0 + grid_w + 4 if not lefty else gx0 - 4
        (c.drawString if not lefty else c.drawRightString)(
            side, y_top - fh * 0.5 - 3, f"{start}fr")

    r = min(sp * 0.42, fh * 0.38) if n > 1 else fh * 0.38
    for s, f in enumerate(item.frets):
        x = sx(s)
        label = item.labels[s] if s < len(item.labels) else ""
        root = item.roots[s] if s < len(item.roots) else False
        if f == _MUTED:
            c.setFont("Helvetica", 8)
            c.drawCentredString(x, y_top + 3, "×")
        elif f == 0:
            c.circle(x, y_top + 6, min(r, 3.2), stroke=1, fill=0)
        else:
            row = f - start
            if 0 <= row < rows:
                _dot(c, x, y_top - (row + 0.5) * fh, r, label, root)
    # String names under the grid
    c.setFont("Helvetica", 6.5)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    for s in range(n):
        c.drawCentredString(sx(s), y_top - rows * fh - 9, item.string_names[s])
    c.setFillColorRGB(0, 0, 0)


# ── Public API ────────────────────────────────────────────────────────────────

def export_sheet(items: Sequence[SheetItem], output_path: str,
                 title: str = "Scales & Chords", lefty: bool = False) -> int:
    """Write the sheet to `output_path`. Returns the number of pages."""
    width, height = letter
    content_w = width - 2 * _MARGIN
    c = rl_canvas.Canvas(output_path, pagesize=letter)
    c.setTitle(title)
    pages = 1

    def header() -> float:
        c.setFont("Helvetica-Bold", 15)
        c.drawString(_MARGIN, height - _MARGIN - 12, title)
        c.setFont("Helvetica", 7)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.drawRightString(width - _MARGIN, height - _MARGIN - 12,
                          f"MIDI2TAB  ·  page {pages}")
        c.setFillColorRGB(0, 0, 0)
        return height - _MARGIN - 30

    y = header()
    i = 0
    while i < len(items):
        item = items[i]
        if isinstance(item, ScaleItem):
            block = [item]
            h = _scale_height(item)
        else:
            block = []
            while (i + len(block) < len(items) and len(block) < _CHORDS_PER_ROW
                   and isinstance(items[i + len(block)], ChordItem)):
                block.append(items[i + len(block)])
            h = max(_chord_height(b) for b in block)
        if y - h < _MARGIN and y < height - _MARGIN - 30:
            c.showPage()
            pages += 1
            y = header()
        if isinstance(item, ScaleItem):
            _draw_scale(c, item, _MARGIN, y, content_w, lefty)
        else:
            cell_w = content_w / _CHORDS_PER_ROW
            for k, ch in enumerate(block):
                _draw_chord(c, ch, _MARGIN + k * cell_w, y, cell_w, lefty)
        y -= h + _GAP
        i += len(block)

    c.save()
    return pages
