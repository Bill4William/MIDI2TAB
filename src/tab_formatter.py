from typing import List, Optional

from .tab_generator import PlacedNote, note_name

COLUMN_WIDTH = 3  # characters per 16th-note grid slot

# Page geometry for 8.5 × 11 with 0.5" margins (used by both PDF and TXT targets)
_PAGE_WIDTH_PT = 612.0
_MARGIN_PT     = 36.0                          # 0.5 inch = 36 pt
_AVAILABLE_PT  = _PAGE_WIDTH_PT - 2 * _MARGIN_PT   # 540 pt

# Max characters that fit per line at each target's assumed font size
PDF_MAX_CHARS = int(_AVAILABLE_PT / (8.0  * 0.6))   # 8 pt Courier  → 112 chars
TXT_MAX_CHARS = int(_AVAILABLE_PT / (10.0 * 0.6))   # 10 pt Courier → 90  chars


def measures_per_line_for_width(
    max_chars: int,
    beats_per_measure: int = 4,
    label_width: int = 4,
    column_width: int = COLUMN_WIDTH,
    grid_divisions: int = 16,
) -> int:
    """Return the most measures that fit in `max_chars` columns.

    label_width  — chars consumed by the string label + opening bar line,
                   e.g. 'A#3|' = 4.  Use the actual max label length + 1.
    """
    grids_per_measure = beats_per_measure * (grid_divisions // 4)
    chars_per_measure = grids_per_measure * column_width + 1   # +1 for bar line
    return max(1, (max_chars - label_width) // chars_per_measure)


def _cell(fret: Optional[int]) -> str:
    """Render one grid slot: fret number left-aligned, padded with dashes."""
    if fret is None:
        return "-" * COLUMN_WIDTH
    raw = str(fret)
    return (raw + "-" * COLUMN_WIDTH)[:COLUMN_WIDTH]


def _measure_is_silent(
    grid: List[List[Optional[int]]],
    measure_idx: int,
    grids_per_measure: int,
) -> bool:
    g_start = measure_idx * grids_per_measure
    g_end = g_start + grids_per_measure
    for string_row in grid:
        for g in range(g_start, min(g_end, len(string_row))):
            if string_row[g] is not None:
                return False
    return True


def format_tab(
    placed_notes: List[PlacedNote],
    num_strings: int,
    tuning: List[int],
    beats_per_measure: int = 4,
    measures_per_line: int = 4,
    grid_divisions: int = 16,
    song_info: Optional[str] = None,
    instrument_info: Optional[str] = None,
) -> str:
    """
    Render placed notes as ASCII tablature.

    Each system (line group) spans `measures_per_line` measures.
    Runs of silent measures are collapsed to a single annotation line.
    Optional song_info and instrument_info are prepended as a header.
    """
    if not placed_notes:
        return "(no notes)"

    grids_per_measure = beats_per_measure * (grid_divisions // 4)
    max_grid = max(n.grid_pos for n in placed_notes) + 1
    total_measures = max(1, -(-max_grid // grids_per_measure))  # ceiling division
    total_cells = total_measures * grids_per_measure

    # Build grid[string_idx][grid_pos] = fret | None
    grid: List[List[Optional[int]]] = [
        [None] * total_cells for _ in range(num_strings)
    ]
    for note in placed_notes:
        if note.grid_pos < total_cells:
            if grid[note.string_idx][note.grid_pos] is None:
                grid[note.string_idx][note.grid_pos] = note.fret

    # Classify each measure as silent or active, then trim trailing silence
    silent_flags = [
        _measure_is_silent(grid, m, grids_per_measure)
        for m in range(total_measures)
    ]
    while len(silent_flags) > 1 and silent_flags[-1]:
        silent_flags.pop()
    total_measures = len(silent_flags)

    # Group consecutive measures into (is_silent, start, end_exclusive) segments
    segments: List[tuple] = []
    i = 0
    while i < total_measures:
        is_silent = silent_flags[i]
        j = i
        while j < total_measures and silent_flags[j] == is_silent:
            j += 1
        segments.append((is_silent, i, j))
        i = j

    # String labels, padded to uniform width
    labels = [note_name(p) for p in tuning]
    lw = max(len(lbl) for lbl in labels)

    output_blocks: List[str] = []

    # Prepend metadata header
    header_lines = []
    if song_info:
        header_lines.append(song_info)
    if instrument_info:
        header_lines.append(instrument_info)
    if header_lines:
        output_blocks.append("\n".join(header_lines))

    for is_silent, seg_start, seg_end in segments:
        count = seg_end - seg_start
        if is_silent:
            label = "Measure" if count == 1 else "Measures"
            output_blocks.append(f"Silent for {count} {label}")
        else:
            # Render active segment as systems of measures_per_line each
            for sys_start in range(seg_start, seg_end, measures_per_line):
                sys_end = min(sys_start + measures_per_line, seg_end)
                g_start = sys_start * grids_per_measure
                g_end = sys_end * grids_per_measure

                rows: List[str] = []
                for s in range(num_strings):
                    label = labels[s].ljust(lw)
                    row = label + "|"
                    for g in range(g_start, g_end):
                        row += _cell(grid[s][g])
                        if (g - g_start + 1) % grids_per_measure == 0:
                            row += "|"
                    rows.append(row)

                output_blocks.append("\n".join(rows))

    return "\n\n".join(output_blocks)
