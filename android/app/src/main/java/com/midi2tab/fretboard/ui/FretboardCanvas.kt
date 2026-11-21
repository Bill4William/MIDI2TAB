package com.midi2tab.fretboard.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.sp
import com.midi2tab.fretboard.model.Cell
import com.midi2tab.fretboard.model.NUM_FRETS
import com.midi2tab.fretboard.model.Role
import com.midi2tab.fretboard.theory.MUTED
import com.midi2tab.fretboard.theory.Voicing
import kotlin.math.min

private val INLAYS = listOf(3, 5, 7, 9)
private const val DOUBLE_INLAY = 12

/**
 * Maps (string, fret) to screen positions for either orientation.
 * Vertical: strings are columns (lowest on the left, like a chord chart),
 * frets run downward with the open strings above the nut.
 * Horizontal: strings are rows (highest on top), frets run to the right.
 */
private class NeckGeometry(
    val width: Float, val height: Float, val strings: Int,
    val vertical: Boolean, val lefty: Boolean, density: Float,
) {
    private val labelGutter = 30f * density // string names
    private val numberGutter = 22f * density // fret numbers
    private val endPad = 10f * density
    private val cols = NUM_FRETS + 1 // open + frets 1..12

    // Along the neck (fret axis) and across it (string axis).
    private val alongStart: Float
    private val fretPitch: Float
    private val acrossStart: Float
    val stringPitch: Float

    init {
        if (vertical) {
            fretPitch = (height - labelGutter - endPad) / cols
            alongStart = labelGutter
            stringPitch = min(64f * density, (width - numberGutter - endPad) / strings)
            acrossStart = numberGutter + ((width - numberGutter - endPad) - stringPitch * strings) / 2
        } else {
            fretPitch = (width - labelGutter - endPad) / cols
            alongStart = labelGutter
            stringPitch = min(56f * density, (height - numberGutter - endPad) / strings)
            acrossStart = endPad + ((height - numberGutter - endPad) - stringPitch * strings) / 2
        }
    }

    val cellSize: Float get() = min(fretPitch, stringPitch)

    /** Position of fret line [f] (f = 1 is the nut) along the neck. */
    fun fretLine(f: Int): Float = alongStart + f * fretPitch

    fun fretCenter(f: Int): Float = alongStart + (f + 0.5f) * fretPitch

    /** Across-neck slot of string [s] (0 = highest string). */
    private fun slot(s: Int): Int {
        // Vertical: lowest string leftmost; horizontal: highest string on top.
        val base = if (vertical) strings - 1 - s else s
        return if (lefty && vertical) strings - 1 - base else base
    }

    fun stringCenter(s: Int): Float = acrossStart + (slot(s) + 0.5f) * stringPitch

    val acrossFrom: Float get() = acrossStart
    val acrossTo: Float get() = acrossStart + stringPitch * strings

    /** Converts (along, across) to a screen point, mirroring for left-handed horizontal view. */
    fun point(along: Float, across: Float): Offset =
        if (vertical) Offset(across, along)
        else Offset(if (lefty) width - along else along, across)

    fun center(s: Int, f: Int): Offset = point(fretCenter(f), stringCenter(s))

    val labelAlong: Float get() = labelGutter / 2
    val numberAcross: Float get() = if (vertical) numberGutter / 2 else acrossTo + numberGutter / 2
}

@Composable
fun FretboardCanvas(
    cells: List<Cell>,
    tuningNames: List<String>,
    voicing: Voicing?,
    vertical: Boolean,
    lefty: Boolean,
    palette: FretPalette,
    showAllNotes: Boolean,
    onTapNote: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val measurer = rememberTextMeasurer()
    Box(modifier) {
        val strings = tuningNames.size
        Canvas(
            Modifier
                .fillMaxSize()
                .pointerInput(cells, vertical, lefty, strings) {
                    detectTapGestures { tap ->
                        val g = NeckGeometry(size.width.toFloat(), size.height.toFloat(), strings, vertical, lefty, density)
                        val r = g.cellSize * 0.5f
                        cells.minByOrNull { (g.center(it.string, it.fret) - tap).getDistanceSquared() }
                            ?.takeIf { (g.center(it.string, it.fret) - tap).getDistance() <= r }
                            ?.let { onTapNote(it.pc) }
                    }
                },
        ) {
            val g = NeckGeometry(size.width, size.height, strings, vertical, lefty, density)
            drawNeck(g, strings, palette, measurer)
            drawStringsAndLabels(g, tuningNames, voicing, palette, measurer)
            drawCells(g, cells, palette, measurer, showAllNotes)
        }
    }
}

private fun DrawScope.drawNeck(g: NeckGeometry, strings: Int, p: FretPalette, m: TextMeasurer) {
    // Fingerboard from the nut to the 12th fret
    val a = g.point(g.fretLine(1), g.acrossFrom)
    val b = g.point(g.fretLine(NUM_FRETS + 1), g.acrossTo)
    drawRect(p.board, Offset(min(a.x, b.x), min(a.y, b.y)), Size(kotlin.math.abs(b.x - a.x), kotlin.math.abs(b.y - a.y)))
    // Inlays sit between the middle strings
    val r = g.cellSize * 0.12f
    val mid = (g.acrossFrom + g.acrossTo) / 2
    for (f in INLAYS) drawCircle(p.inlay, r, g.point(g.fretCenter(f), mid))
    val off = if (strings >= 3) (g.acrossTo - g.acrossFrom) * 0.22f else 0f
    drawCircle(p.inlay, r, g.point(g.fretCenter(DOUBLE_INLAY), mid - off))
    drawCircle(p.inlay, r, g.point(g.fretCenter(DOUBLE_INLAY), mid + off))
    // Frets (the nut is thick)
    for (f in 1..NUM_FRETS + 1) {
        drawLine(
            if (f == 1) p.nut else p.fret,
            g.point(g.fretLine(f), g.acrossFrom), g.point(g.fretLine(f), g.acrossTo),
            strokeWidth = if (f == 1) 5f * density else 1.5f * density,
        )
    }
    // Fret numbers
    for (f in 0..NUM_FRETS) {
        val text = if (f == 0) "0" else f.toString()
        val bold = f in INLAYS || f == DOUBLE_INLAY
        drawCentered(m, text, g.point(g.fretCenter(f), g.numberAcross), p.faint, 11f, bold)
    }
}

private fun DrawScope.drawStringsAndLabels(
    g: NeckGeometry, names: List<String>, voicing: Voicing?, p: FretPalette, m: TextMeasurer,
) {
    val n = names.size
    for (s in 0 until n) {
        val across = g.stringCenter(s)
        // Thicker toward the bass
        val thick = (1f + 2.2f * (n - 1 - s) / maxOf(n - 1, 1).toFloat()) * density
        drawLine(p.string, g.point(g.fretLine(0), across), g.point(g.fretLine(NUM_FRETS + 1), across), thick)
        val muted = voicing != null && voicing.frets[s] == MUTED
        drawCentered(m, if (muted) "×" else names[s], g.point(g.labelAlong, across),
            if (muted) p.root else p.text, 14f, bold = true)
    }
}

private fun DrawScope.drawCells(
    g: NeckGeometry, cells: List<Cell>, p: FretPalette, m: TextMeasurer, showAllNotes: Boolean,
) {
    val r = g.cellSize * 0.42f
    val fontSp = (r / density * 0.95f).coerceIn(8f, 15f)
    for (c in cells) {
        val o = g.center(c.string, c.fret)
        val fill: Color? = when (c.role) {
            Role.VOICING_ROOT -> p.chordRoot
            Role.VOICING -> p.chord
            Role.SCALE_ROOT -> p.root
            Role.SCALE -> p.scale
            Role.CHORD_TONE, Role.OTHER -> null
        }
        val textColor = when {
            c.role == Role.VOICING_ROOT || c.role == Role.VOICING -> p.chordText
            fill != null -> Color.White
            c.prominent -> p.text
            else -> p.faint
        }
        if (fill != null) drawCircle(fill, r, o)
        else if (c.chordRing || c.highlighted) drawCircle(p.background, r, o)
        if (c.chordRing) drawCircle(p.chord, r, o, style = Stroke(2.5f * density))
        if (c.highlighted) drawCircle(p.highlight, r + 3.5f * density, o, style = Stroke(2.5f * density))
        if (c.prominent || showAllNotes) {
            drawCentered(
                m, c.label, o, textColor, if (c.prominent) fontSp else fontSp * 0.8f, bold = c.prominent,
                backdrop = if (c.prominent) null else if (c.fret == 0) p.background else p.board,
            )
        }
    }
}

private fun DrawScope.drawCentered(
    m: TextMeasurer, text: String, at: Offset, color: Color, sizeSp: Float, bold: Boolean = false,
    backdrop: Color? = null,
) {
    val layout = m.measure(
        text,
        TextStyle(color = color, fontSize = sizeSp.sp, fontWeight = if (bold) FontWeight.Bold else FontWeight.Normal),
    )
    val topLeft = Offset(at.x - layout.size.width / 2f, at.y - layout.size.height / 2f)
    if (backdrop != null) {
        // Keeps faint labels readable where a string or fret line runs through them.
        val pad = 2f * density
        drawRoundRect(
            backdrop, Offset(topLeft.x - pad, topLeft.y),
            Size(layout.size.width + 2 * pad, layout.size.height.toFloat()), CornerRadius(3f * density),
        )
    }
    drawText(layout, topLeft = topLeft)
}
