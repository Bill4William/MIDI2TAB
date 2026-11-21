package com.midi2tab.fretboard.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PersistenceTest {
    private val dropC = listOf(62, 57, 53, 48, 43, 36) // D A F C G C

    @Test fun tuningsRoundTrip() {
        val list = listOf(SavedTuning("Drop C", dropC), SavedTuning("Bass BEAD", listOf(38, 33, 28, 23)))
        assertEquals(list, decodeTunings(encodeTunings(list)))
    }

    @Test fun namesAreCleaned() {
        assertEquals("Open D", cleanTuningName("  Open\tD \n"))
        assertEquals(MAX_NAME_LENGTH, cleanTuningName("x".repeat(100)).length)
        val decoded = decodeTunings(encodeTunings(listOf(SavedTuning("A\tB", dropC))))
        assertEquals("A B", decoded.single().name)
    }

    @Test fun corruptTuningLinesAreSkipped() {
        val text = listOf(
            "Good\t64,59,55,50,45,40",
            "No tab here",
            "\t64,59",                 // empty name
            "Bad pitch\t64,abc",
            "Too low\t1,2,3",          // below C0
            "Too many\t" + List(13) { 40 }.joinToString(","),
        ).joinToString("\n")
        assertEquals(listOf("Good"), decodeTunings(text).map { it.name })
        assertTrue(decodeTunings(null).isEmpty())
        assertTrue(decodeTunings("").isEmpty())
    }

    @Test fun stateRoundTrip() {
        val s = ExplorerState(
            tuning = dropC, scaleRoot = 2, family = "Harmonic Minor", modeIndex = 4, showDegrees = true,
            allNotes = false, sevenths = true, chordOn = true, chordRoot = 7, chordTypeName = "Dominant 7 #9",
            allChordTones = true, rootInBass = false, maxSpan = 5, lefty = true, highlight = setOf(3),
        )
        // Highlights are transient and not restored
        assertEquals(s.copy(highlight = emptySet()), decodeState(encodeState(s)))
    }

    @Test fun invalidStateFieldsFallBackToDefaults() {
        val d = ExplorerState()
        val text = """
            tuning=64,abc
            scaleRoot=15
            family=Not A Scale
            modeIndex=3
            chordType=Nope
            maxSpan=99
            lefty=yes
            chordOn=true
            junk line
        """.trimIndent()
        val s = decodeState(text)
        assertEquals(d.tuning, s.tuning)
        assertEquals(d.scaleRoot, s.scaleRoot)
        assertEquals(d.family, s.family)
        assertEquals(d.modeIndex, s.modeIndex)     // unknown family → default mode too
        assertEquals(d.chordTypeName, s.chordTypeName)
        assertEquals(d.maxSpan, s.maxSpan)
        assertEquals(d.lefty, s.lefty)             // "yes" isn't a boolean
        assertEquals(true, s.chordOn)              // valid fields still restore
        assertEquals(d, decodeState(null))
        // A mode index beyond the restored family's modes is rejected
        assertEquals(0, decodeState("family=Blues\nmodeIndex=4").modeIndex)
    }

    @Test fun labelsAndMatching() {
        assertEquals("E A D G B E", tuningLabel(PRESETS[0].tuning))
        assertEquals("Guitar – Drop D", matchingTuningName(listOf(64, 59, 55, 50, 45, 38), emptyList()))
        assertEquals("Drop C", matchingTuningName(dropC, listOf(SavedTuning("Drop C", dropC))))
        assertNull(matchingTuningName(dropC, emptyList()))
    }
}
