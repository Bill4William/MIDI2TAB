package com.midi2tab.fretboard.model

import com.midi2tab.fretboard.theory.chordType
import com.midi2tab.fretboard.theory.findVoicings
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ExplorerModelTest {
    private val standard = ExplorerState()

    private fun cell(cells: List<Cell>, string: Int, fret: Int) = cells.first { it.string == string && it.fret == fret }

    @Test fun cMajorScaleCells() {
        val cells = computeCells(standard, null)
        assertEquals(6 * 13, cells.size)
        // Low E string (index 5), 8th fret = C, the root
        assertEquals(Role.SCALE_ROOT, cell(cells, 5, 8).role)
        assertEquals("C", cell(cells, 5, 8).label)
        // Low E, 2nd fret = F#: not in C major
        assertEquals(Role.OTHER, cell(cells, 5, 2).role)
        assertEquals(7, cells.filter { it.string == 0 && it.role != Role.OTHER && it.fret < 12 }.size)
    }

    @Test fun degreesAndFlatsInFMajor() {
        val s = standard.copy(scaleRoot = 5, showDegrees = false)
        val cells = computeCells(s, null)
        assertEquals("Bb", cell(cells, 2, 3).label) // G string 3rd fret
        val deg = computeCells(s.copy(showDegrees = true), null)
        assertEquals("4", cell(deg, 2, 3).label)
    }

    @Test fun voicingOverridesScale() {
        val s = standard.copy(chordOn = true, chordRoot = 9, chordTypeName = "Minor")
        val v = findVoicings(s.tuning, 9, chordType("Minor")).first { it.shape() == "x02210" }
        val cells = computeCells(s, v)
        assertEquals(Role.VOICING_ROOT, cell(cells, 4, 0).role) // open A
        assertEquals(Role.VOICING, cell(cells, 1, 1).role)      // C on the B string
        assertEquals("Am: A C E", chordSummary(s))
        val tab = voicingTab(s, v)
        assertTrue(tab, tab.startsWith("Am\nE|-0--|\nB|-1--|"))
        assertTrue(tab, tab.trimEnd().endsWith("E|-x--|"))
    }

    @Test fun chordToneRingsOnlyWhenAsked() {
        val s = standard.copy(chordOn = true, chordRoot = 2, chordTypeName = "Dominant 7")
        assertTrue(computeCells(s, null).none { it.chordRing })
        val rings = computeCells(s.copy(allChordTones = true), null).filter { it.chordRing }
        assertTrue(rings.isNotEmpty())
        assertTrue(rings.all { it.pc in setOf(2, 6, 9, 0) })
    }

    @Test fun highlightMarksEveryPosition() {
        val cells = computeCells(standard.copy(highlight = setOf(4)), null)
        assertEquals(cells.count { it.pc == 4 }, cells.count { it.highlighted })
    }

    @Test fun sheetItemsAndLayout() {
        val scale = scaleSheetItem(standard.copy(scaleRoot = 9, family = "Pentatonic", modeIndex = 4))
        assertEquals("A Minor Pentatonic", scale.title)
        assertTrue(scale.cells.values.any { it.second })
        val v = findVoicings(standard.tuning, 0, chordType("Major")).first()
        val chord = chordSheetItem(standard, 0, chordType("Major"), v)
        assertEquals("C", chord.title)
        assertEquals("x32010", chord.subtitle)

        // Same page-break behaviour as the desktop exporter's tests
        assertEquals(1, layoutSheet(listOf(scale, scale) + List(8) { chord }).size)
        assertTrue(layoutSheet(List(10) { scale }).size >= 3)
        val row = layoutSheet(List(5) { chord })[0]
        assertEquals(4, row.count { it.top == row[0].top })   // four chords per row
        assertTrue(layoutSheet(emptyList()).size == 1)
    }
}
