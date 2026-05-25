from src.tab_formatter import measures_per_line_for_width, PDF_MAX_CHARS, TXT_MAX_CHARS, COLUMN_WIDTH
from src.pdf_exporter import export_pdf, _MARGIN
from src.gui import App

beats = 4
grids = beats * 4
chars_per_measure = grids * COLUMN_WIDTH + 1
label_w = 4

pdf_mpl = measures_per_line_for_width(PDF_MAX_CHARS, beats, label_w)
txt_mpl = measures_per_line_for_width(TXT_MAX_CHARS, beats, label_w)

print("PDF_MAX_CHARS :", PDF_MAX_CHARS, "(at 8pt Courier)")
print("TXT_MAX_CHARS :", TXT_MAX_CHARS, "(at 10pt Courier)")
print("chars/measure :", chars_per_measure, "(16 slots x 3 + 1 bar)")
print("PDF mpl (4/4) :", pdf_mpl, "measures ->", label_w + pdf_mpl * chars_per_measure, "chars")
print("TXT mpl (4/4) :", txt_mpl, "measures ->", label_w + txt_mpl * chars_per_measure, "chars")
print("PDF margin    :", _MARGIN, "pt (0.5 inch)")
print("All imports OK")
