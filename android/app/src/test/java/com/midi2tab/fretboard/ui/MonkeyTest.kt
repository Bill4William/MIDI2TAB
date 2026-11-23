package com.midi2tab.fretboard.ui

import android.os.Looper
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.midi2tab.fretboard.model.MemoryStore
import com.midi2tab.fretboard.model.PRESETS
import com.midi2tab.fretboard.model.chordSheetItem
import com.midi2tab.fretboard.model.chordSummary
import com.midi2tab.fretboard.model.computeCells
import com.midi2tab.fretboard.model.layoutSheet
import com.midi2tab.fretboard.model.matchingTuningName
import com.midi2tab.fretboard.model.scaleSheetItem
import com.midi2tab.fretboard.model.scaleSummary
import com.midi2tab.fretboard.model.voicingTab
import com.midi2tab.fretboard.theory.CHORD_TYPES
import com.midi2tab.fretboard.theory.SCALE_FAMILIES
import com.midi2tab.fretboard.theory.diatonicChords
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import kotlin.random.Random

/**
 * Random sequences of user actions, with background voicing results sometimes
 * landing late, checking after every step that everything the screen reads
 * works and stays consistent with the current tuning.
 */
@RunWith(AndroidJUnit4::class)
@Config(sdk = [35])
class MonkeyTest {
    private fun settle() {
        Thread.sleep(5)
        shadowOf(Looper.getMainLooper()).idle()
    }

    private fun checkScreenReads(vm: ExplorerViewModel) {
        val s = vm.state
        val v = vm.currentVoicing
        if (v != null) assertEquals("voicing must match string count", s.tuning.size, v.frets.size)
        assertEquals(s.tuning.size * 13, computeCells(s, v).size)
        if (s.scaleOn) scaleSummary(s)
        if (s.chordOn) chordSummary(s)
        if (v != null) {
            voicingTab(s, v)
            chordSheetItem(s, s.chordRoot, s.chordType, v)
        }
        diatonicChords(s.scaleRoot, s.scaleIntervals, s.sevenths)
        scaleSheetItem(s)
        matchingTuningName(s.tuning, vm.savedTunings)
        layoutSheet(vm.sheet.toList())
        assertTrue(vm.voicingIndex >= 0)
    }

    @Test fun randomUse() {
        val rnd = Random(20261121)
        val vm = ExplorerViewModel(MemoryStore())
        repeat(1500) { step ->
            when (rnd.nextInt(17)) {
                0 -> vm.changeStringCount(if (rnd.nextBoolean()) 1 else -1)
                1 -> vm.shiftString(rnd.nextInt(vm.state.tuning.size), if (rnd.nextBoolean()) 1 else -1)
                2 -> vm.shiftAll(if (rnd.nextBoolean()) 1 else -1)
                3 -> vm.applyPreset(PRESETS.random(rnd))
                4 -> vm.update { it.copy(chordOn = !it.chordOn) }
                5 -> vm.setChord(rnd.nextInt(12), CHORD_TYPES.random(rnd).name)
                6 -> vm.stepVoicing(if (rnd.nextBoolean()) 1 else -1)
                7 -> {
                    val f = SCALE_FAMILIES.random(rnd)
                    vm.update { it.copy(family = f.name, modeIndex = rnd.nextInt(f.modeNames.size), scaleRoot = rnd.nextInt(12)) }
                }
                8 -> vm.update { it.copy(scaleOn = !it.scaleOn, showDegrees = rnd.nextBoolean(), sevenths = rnd.nextBoolean()) }
                9 -> vm.update(pickBest = true) { it.copy(rootInBass = !it.rootInBass, maxSpan = 3 + rnd.nextInt(4)) }
                10 -> vm.toggleHighlight(rnd.nextInt(12))
                11 -> vm.addChordToSheet()
                12 -> vm.addScaleToSheet()
                13 -> if (vm.sheet.isNotEmpty()) vm.moveSheetItem(rnd.nextInt(vm.sheet.size), if (rnd.nextBoolean()) 1 else -1)
                14 -> if (vm.sheet.isNotEmpty()) vm.removeSheetItem(rnd.nextInt(vm.sheet.size))
                15 -> if (rnd.nextBoolean()) vm.saveTuning("T${rnd.nextInt(5)}")
                    else vm.savedTunings.randomOrNull(rnd)?.let { vm.applySavedTuning(it) }
                16 -> vm.update { it.copy(lefty = !it.lefty, allChordTones = rnd.nextBoolean()) }
            }
            // Sometimes let background searches land, sometimes check before they do.
            if (rnd.nextInt(3) == 0) settle()
            try {
                checkScreenReads(vm)
            } catch (e: Throwable) {
                throw AssertionError("step $step, state ${vm.state}", e)
            }
        }
    }
}
