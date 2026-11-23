package com.midi2tab.fretboard.theory

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Hand-written checks mirroring tests/test_music_theory.py. */
class MusicTheoryTest {
    private val guitar6 = listOf(64, 59, 55, 50, 45, 40) // E4 B3 G3 D3 A2 E2
    private val bass4 = listOf(43, 38, 33, 28)

    private fun mode(name: String): List<Int> {
        val (fam, idx) = findMode(name)!!
        return modeIntervals(fam, idx)
    }

    private fun shapes(tuning: List<Int>, root: Int, chord: String, rootInBass: Boolean = true) =
        findVoicings(tuning, root, chordType(chord), rootInBass = rootInBass).map { it.shape() }

    private fun best(root: Int, chord: String): String {
        val v = findVoicings(guitar6, root, chordType(chord))
        return v[bestVoicingIndex(v)].shape()
    }

    @Test fun churchModes() {
        assertEquals(listOf(0, 2, 3, 5, 7, 9, 10), mode("Dorian"))
        assertEquals(listOf(0, 2, 4, 6, 7, 9, 11), mode("Lydian"))
        assertEquals(listOf(0, 1, 3, 5, 6, 8, 10), mode("Locrian"))
        assertEquals(listOf(0, 1, 4, 5, 7, 8, 10), mode("Phrygian Dominant"))
        assertEquals(listOf(0, 3, 5, 7, 10), mode("Minor Pentatonic"))
    }

    @Test fun spelling() {
        assertEquals(listOf("F", "G", "A", "Bb", "C", "D", "E"), spellScale(5, mode("Ionian (Major)")))
        assertEquals(listOf("Db", "Eb", "F", "Gb", "Ab", "Bb", "C"), spellScale(1, mode("Ionian (Major)")))
        assertEquals(listOf("A", "B", "C", "D", "E", "F", "G#"), spellScale(9, mode("Harmonic Minor")))
        assertEquals(listOf("1", "2", "3", "#4", "5", "6", "7"), degreeLabels(mode("Lydian")))
        assertEquals("G", spellChord(4, chordType("Dominant 7 #9"))[7])
        assertEquals(1, pcFromName("C#/Db"))
        assertEquals(11, pcFromName("Cb"))
    }

    @Test fun diatonicCMajorSevenths() {
        val got = diatonicChords(0, mode("Ionian (Major)"), sevenths = true).map { it.type?.symbol }
        assertEquals(listOf("maj7", "m7", "m7", "maj7", "7", "m7", "m7b5"), got)
        assertTrue(diatonicChords(0, mode("Minor Pentatonic")).isEmpty())
    }

    @Test fun openChordsFoundFirst() {
        assertEquals("x32010", shapes(guitar6, 0, "Major")[0])
        assertEquals("x02210", shapes(guitar6, 9, "Minor")[0])
        assertEquals("022100", shapes(guitar6, 4, "Major")[0])
        assertEquals("xx0232", shapes(guitar6, 2, "Major")[0])
    }

    @Test fun bestVoicingsMatchStandardCharts() {
        assertEquals("133211", best(5, "Major"))
        assertEquals("x24432", best(11, "Minor"))
        assertEquals("020000", best(4, "Minor 7"))
        assertEquals("x02020", best(9, "Dominant 7"))
        assertEquals("320003", best(7, "Major"))
        assertEquals(0, bestVoicingIndex(emptyList()))
    }

    @Test fun barreRuleAndInversions() {
        assertFalse("103211" in shapes(guitar6, 5, "Major"))
        assertTrue("332010" in shapes(guitar6, 0, "Major", rootInBass = false))
    }

    @Test fun everyVoicingIsPlayable() {
        for (tuning in listOf(guitar6, bass4)) {
            for (name in listOf("Major", "Minor 7", "Dominant 9", "Diminished 7")) {
                val chord = chordType(name)
                val tones = chord.intervals.map { mod(2 + it, 12) }.toSet()
                for (v in findVoicings(tuning, 2, chord)) {
                    val played = v.frets.withIndex().filter { it.value != MUTED }
                        .map { mod(tuning[it.index] + it.value, 12) }
                    assertTrue(v.shape(), played.toSet().all { it in tones })
                    val fretted = v.frets.filter { it > 0 }
                    if (fretted.isNotEmpty()) assertTrue(v.shape(), fretted.max() - fretted.min() < 4)
                }
            }
        }
    }

    @Test fun twelveStringsFinishQuickly() {
        val twelve = listOf(64, 59, 55, 50, 45, 40, 35, 30, 25, 20, 15, 10)
        val t0 = System.nanoTime()
        val v = findVoicings(twelve, 0, chordType("Dominant 9"), rootInBass = false)
        val ms = (System.nanoTime() - t0) / 1_000_000
        assertTrue(v.isNotEmpty())
        assertTrue("took $ms ms", ms < 3000)
    }

    @Test fun midiNames() {
        assertEquals("E2", midiToName(40))
        assertEquals("C-1", midiToName(0))
        assertNull(findMode("Nonexistent"))
    }
}
