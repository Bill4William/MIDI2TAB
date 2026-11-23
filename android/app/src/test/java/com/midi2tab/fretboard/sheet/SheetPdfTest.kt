package com.midi2tab.fretboard.sheet

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.midi2tab.fretboard.model.ExplorerState
import com.midi2tab.fretboard.model.PAGE_HEIGHT
import com.midi2tab.fretboard.model.PAGE_WIDTH
import com.midi2tab.fretboard.model.SheetItem
import com.midi2tab.fretboard.model.chordSheetItem
import com.midi2tab.fretboard.model.layoutSheet
import com.midi2tab.fretboard.model.scaleSheetItem
import com.midi2tab.fretboard.theory.bestVoicingIndex
import com.midi2tab.fretboard.theory.chordType
import com.midi2tab.fretboard.theory.diatonicChords
import com.midi2tab.fretboard.theory.findVoicings
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/** Draws a real sheet with the PDF drawing code; page images are kept for visual review. */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35])
class SheetPdfTest {
    @Test fun writesMultiPageSheet() {
        val am = ExplorerState(scaleRoot = 9, family = "Major (Diatonic)", modeIndex = 5)
        val items = mutableListOf<SheetItem>(
            scaleSheetItem(am.copy(family = "Pentatonic", modeIndex = 4, showDegrees = true)),
            scaleSheetItem(am),
        )
        for (dc in diatonicChords(am.scaleRoot, am.scaleIntervals, sevenths = true)) {
            val type = dc.type ?: continue
            val vs = findVoicings(am.tuning, dc.rootPc, type)
            items += chordSheetItem(am, dc.rootPc, type, vs[bestVoicingIndex(vs)])
        }
        val e7s9 = findVoicings(am.tuning, 4, chordType("Dominant 7 #9"))
        items += chordSheetItem(am, 4, chordType("Dominant 7 #9"), e7s9[3])
        val bass = ExplorerState(tuning = listOf(43, 38, 33, 28, 23), scaleRoot = 4, family = "Pentatonic", modeIndex = 4)
        repeat(4) { items += scaleSheetItem(bass) }

        // Robolectric has no native PdfDocument, so draw each page into a
        // bitmap with the same code the PDF uses and keep it for review.
        val pages = layoutSheet(items)
        assertEquals(2, pages.size)
        val dir = File("build/outputs/sheet-preview").apply { mkdirs() }
        pages.forEachIndexed { i, placed ->
            val scale = 2f
            val bmp = Bitmap.createBitmap((PAGE_WIDTH * scale).toInt(), (PAGE_HEIGHT * scale).toInt(), Bitmap.Config.ARGB_8888)
            val canvas = Canvas(bmp).apply { drawColor(Color.WHITE); scale(scale, scale) }
            drawSheetPage(canvas, placed, "Practice Sheet", i + 1, lefty = false)
            // Something other than white was drawn
            assertTrue((0 until bmp.width step 7).any { x -> (0 until bmp.height step 7).any { y -> bmp.getPixel(x, y) != Color.WHITE } })
            File(dir, "page-${i + 1}.png").outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
        }
    }
}
