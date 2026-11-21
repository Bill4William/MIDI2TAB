/*
 * Draws a laid-out sheet into a PDF with Android's PdfDocument. Geometry and
 * styling follow the desktop app's src/sheet_exporter.py (scales as neck
 * diagrams, chords as boxes), converted to top-down coordinates.
 */
package com.midi2tab.fretboard.sheet

import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import com.midi2tab.fretboard.model.ChordSheetItem
import com.midi2tab.fretboard.model.NUM_FRETS
import com.midi2tab.fretboard.model.PAGE_HEIGHT
import com.midi2tab.fretboard.model.PAGE_MARGIN
import com.midi2tab.fretboard.model.PAGE_WIDTH
import com.midi2tab.fretboard.model.Placed
import com.midi2tab.fretboard.model.ScaleSheetItem
import com.midi2tab.fretboard.model.SheetItem
import com.midi2tab.fretboard.model.layoutSheet
import com.midi2tab.fretboard.model.scaleRowHeight
import com.midi2tab.fretboard.theory.MUTED
import java.io.OutputStream
import kotlin.math.min

private val ROOT_FILL = Color.rgb(232, 89, 13)
private val NOTE_FILL = Color.rgb(38, 38, 38)
private val GREY = Color.rgb(102, 102, 102)
private val INLAY = Color.rgb(217, 217, 217)
private val INLAYS = listOf(3, 5, 7, 9)

/** Writes the sheet as a PDF to [out]; returns the number of pages. */
fun writeSheetPdf(items: List<SheetItem>, title: String, lefty: Boolean, out: OutputStream): Int {
    val pages = layoutSheet(items)
    val doc = PdfDocument()
    try {
        pages.forEachIndexed { index, placed ->
            val info = PdfDocument.PageInfo.Builder(PAGE_WIDTH.toInt(), PAGE_HEIGHT.toInt(), index + 1).create()
            val page = doc.startPage(info)
            drawSheetPage(page.canvas, placed, title, index + 1, lefty)
            doc.finishPage(page)
        }
        doc.writeTo(out)
    } finally {
        doc.close()
    }
    return pages.size
}

/** Draws one laid-out page (in points, top-down) onto any canvas. */
fun drawSheetPage(c: Canvas, placed: List<Placed>, title: String, pageNumber: Int, lefty: Boolean) {
    drawHeader(c, title, pageNumber)
    for (p in placed) {
        when (val item = p.item) {
            is ScaleSheetItem -> drawScale(c, item, p.x, p.top, p.width, lefty)
            is ChordSheetItem -> drawChord(c, item, p.x, p.top, p.width, lefty)
        }
    }
}

private fun paint(color: Int = Color.BLACK, size: Float = 8f, bold: Boolean = false, fill: Boolean = true) =
    Paint(Paint.ANTI_ALIAS_FLAG).apply {
        this.color = color
        textSize = size
        typeface = if (bold) Typeface.DEFAULT_BOLD else Typeface.DEFAULT
        style = if (fill) Paint.Style.FILL else Paint.Style.STROKE
    }

private fun Canvas.textCentered(text: String, x: Float, baseline: Float, p: Paint) {
    p.textAlign = Paint.Align.CENTER
    drawText(text, x, baseline, p)
}

private fun Canvas.line(x1: Float, y1: Float, x2: Float, y2: Float, width: Float, color: Int = Color.BLACK) {
    drawLine(x1, y1, x2, y2, paint(color).apply { strokeWidth = width; style = Paint.Style.STROKE })
}

private fun drawHeader(c: Canvas, title: String, page: Int) {
    c.drawText(title, PAGE_MARGIN, PAGE_MARGIN + 12f, paint(size = 15f, bold = true))
    val p = paint(Color.rgb(128, 128, 128), 7f).apply { textAlign = Paint.Align.RIGHT }
    c.drawText("MIDI2TAB  ·  page $page", PAGE_WIDTH - PAGE_MARGIN, PAGE_MARGIN + 12f, p)
}

private fun dot(c: Canvas, x: Float, y: Float, r: Float, label: String, root: Boolean) {
    c.drawCircle(x, y, r, paint(if (root) ROOT_FILL else NOTE_FILL))
    if (label.isNotEmpty()) {
        val size = if (label.length < 3) min(r * 1.15f, 8f) else min(r * 0.95f, 7f)
        c.textCentered(label, x, y + size * 0.35f, paint(Color.WHITE, size, bold = true))
    }
}

private fun drawScale(c: Canvas, item: ScaleSheetItem, x0: Float, top: Float, width: Float, lefty: Boolean) {
    val n = item.stringNames.size
    val rh = scaleRowHeight(n)
    c.drawText(item.title, x0, top + 11f, paint(size = 11f, bold = true))
    c.drawText(item.subtitle, x0, top + 22f, paint(size = 8f))

    val labelW = 22f
    val cols = NUM_FRETS + 1
    val cw = (width - labelW) / cols
    val yTop = top + 30f
    val boardBottom = yTop + rh * n
    fun yOf(s: Int) = yTop + rh * (s + 0.5f)
    fun xe(col: Int): Float {
        val x = x0 + labelW + col * cw
        return if (lefty) (2 * x0 + width) - x else x
    }
    fun xc(col: Int) = (xe(col) + xe(col + 1)) / 2

    val numbers = paint(GREY, 6.5f)
    for (f in 1 until cols) c.textCentered("$f", xc(f), boardBottom + 9f, numbers)

    val inlay = paint(INLAY)
    val mid = (yTop + boardBottom) / 2
    for (f in INLAYS) c.drawCircle(xc(f), mid, 2.4f, inlay)
    c.drawCircle(xc(12), mid - rh * n * 0.2f, 2.4f, inlay)
    c.drawCircle(xc(12), mid + rh * n * 0.2f, 2.4f, inlay)

    for (f in 1..cols) c.line(xe(f), yTop, xe(f), boardBottom, if (f == 1) 2.5f else 0.6f)
    val names = paint(size = 8f, bold = true)
    for (s in 0 until n) {
        c.line(xe(0), yOf(s), xe(cols), yOf(s), 0.5f)
        val lx = if (!lefty) x0 + labelW / 2 - 3 else x0 + width - labelW / 2 + 3
        c.textCentered(item.stringNames[s], lx, yOf(s) + 3f, names)
    }

    val r = min(cw, rh) * 0.42f
    for ((pos, value) in item.cells) {
        val (s, f) = pos
        if (s in 0 until n && f in 0 until cols) dot(c, xc(f), yOf(s), r, value.first, value.second)
    }
}

private fun drawChord(c: Canvas, item: ChordSheetItem, x0: Float, top: Float, width: Float, lefty: Boolean) {
    val n = item.stringNames.size
    c.textCentered(item.title, x0 + width / 2, top + 12f, paint(size = 12f, bold = true))
    c.textCentered(item.subtitle, x0 + width / 2, top + 22f, paint(size = 7.5f))

    val rows = 5
    val fh = 18f
    val gridW = min(width - 24f, 14f * maxOf(n - 1, 1))
    val gx0 = x0 + (width - gridW) / 2
    val sp = gridW / maxOf(n - 1, 1)
    val yTop = top + 38f
    val fretted = item.frets.filter { it > 0 }
    val start = if (fretted.isEmpty() || fretted.max() <= rows) 1 else fretted.min()

    // Low string on the left (mirrored for left-handed players).
    fun sx(s: Int): Float {
        val col = if (!lefty) n - 1 - s else s
        return if (n > 1) gx0 + col * sp else gx0 + gridW / 2
    }

    for (r in 0..rows) {
        val y = yTop + r * fh
        c.line(gx0, y, gx0 + gridW, y, if (r == 0 && start == 1) 2.5f else 0.6f)
    }
    for (s in 0 until n) c.line(sx(s), yTop, sx(s), yTop + rows * fh, 0.6f)
    if (start > 1) {
        val p = paint(size = 8f).apply { textAlign = if (lefty) Paint.Align.RIGHT else Paint.Align.LEFT }
        c.drawText("${start}fr", if (!lefty) gx0 + gridW + 4 else gx0 - 4, yTop + fh * 0.5f + 3, p)
    }

    val r = if (n > 1) min(sp * 0.42f, fh * 0.38f) else fh * 0.38f
    item.frets.forEachIndexed { s, f ->
        val x = sx(s)
        when {
            f == MUTED -> c.textCentered("×", x, yTop - 3f, paint(size = 8f))
            f == 0 -> c.drawCircle(x, yTop - 6f, min(r, 3.2f), paint(fill = false).apply { strokeWidth = 0.8f })
            else -> {
                val row = f - start
                if (row in 0 until rows) {
                    dot(c, x, yTop + (row + 0.5f) * fh, r, item.labels.getOrElse(s) { "" }, item.roots.getOrElse(s) { false })
                }
            }
        }
    }
    val names = paint(GREY, 6.5f)
    for (s in 0 until n) c.textCentered(item.stringNames[s], sx(s), yTop + rows * fh + 9f, names)
}
