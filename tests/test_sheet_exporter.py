"""
Tests for the printable scale/chord sheet (src/sheet_exporter.py).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sheet_exporter import ChordItem, ScaleItem, export_sheet

NAMES_6 = ["E", "B", "G", "D", "A", "E"]


def _scale(n_strings=6):
    names = (NAMES_6 * 2)[:n_strings]
    cells = {(s, f): ("A", f == 5) for s in range(n_strings) for f in (0, 5, 12)}
    return ScaleItem("A Minor Pentatonic", "A C D E G", names, cells)


def _chord(frets=(0, 1, 2, 2, 0, -1), title="Am"):
    return ChordItem(title, "x02210", NAMES_6, tuple(frets),
                     labels=["E", "C", "A", "E", "A", ""],
                     roots=[False, False, True, False, True, False])


class TestSheetExporter(unittest.TestCase):
    def _export(self, items, **kw):
        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        self.addCleanup(os.remove, path)
        pages = export_sheet(items, path, **kw)
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(5), b"%PDF-")
        return pages

    def test_mixed_sheet_fits_one_page(self):
        items = [_scale(), _scale()] + [_chord() for _ in range(8)]
        self.assertEqual(self._export(items, title="Practice"), 1)

    def test_long_sheet_breaks_pages(self):
        items = [_scale() for _ in range(10)]
        self.assertGreaterEqual(self._export(items), 3)

    def test_high_position_chord_and_lefty(self):
        barre = _chord(frets=(7, 8, 9, 9, 7, -1), title="Em/B")
        self.assertEqual(self._export([barre, _scale(12)], lefty=True), 1)

    def test_empty_sheet_still_writes_pdf(self):
        self.assertEqual(self._export([]), 1)


if __name__ == "__main__":
    unittest.main()
