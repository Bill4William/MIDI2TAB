package com.midi2tab.fretboard.ui

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.midi2tab.fretboard.model.KEY_STATE
import com.midi2tab.fretboard.model.KEY_TUNINGS
import com.midi2tab.fretboard.model.MemoryStore
import com.midi2tab.fretboard.model.PRESETS
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config

/** A fresh ViewModel on the same store stands in for the app being reopened. */
@RunWith(AndroidJUnit4::class)
@Config(sdk = [35])
class ExplorerViewModelTest {
    private val dropC = listOf(62, 57, 53, 48, 43, 36)

    @Test fun savedTuningSurvivesRestart() {
        val store = MemoryStore()
        val vm = ExplorerViewModel(store)
        vm.update { it.copy(tuning = dropC) }
        assertTrue(vm.saveTuning("  Drop C  "))
        assertEquals("Drop C", vm.savedTunings.single().name)
        assertNotNull(store.load(KEY_TUNINGS))

        val reopened = ExplorerViewModel(store)
        assertEquals(listOf("Drop C"), reopened.savedTunings.map { it.name })
        assertEquals(dropC, reopened.savedTunings.single().tuning)
    }

    @Test fun sameNameReplacesAndBlankIsRejected() {
        val vm = ExplorerViewModel(MemoryStore())
        vm.saveTuning("Mine")
        vm.update { it.copy(tuning = dropC) }
        vm.saveTuning("MINE")
        assertEquals(1, vm.savedTunings.size)
        assertEquals(dropC, vm.savedTunings.single().tuning)
        assertFalse(vm.saveTuning("   "))
        assertEquals(1, vm.savedTunings.size)
    }

    @Test fun loadAndDelete() {
        val store = MemoryStore()
        val vm = ExplorerViewModel(store)
        vm.update { it.copy(tuning = dropC) }
        vm.saveTuning("Drop C")
        vm.applyPreset(PRESETS[0])
        vm.applySavedTuning(vm.savedTunings.single())
        assertEquals(dropC, vm.state.tuning)
        vm.deleteTuning(vm.savedTunings.single())
        assertTrue(vm.savedTunings.isEmpty())
        assertTrue(ExplorerViewModel(store).savedTunings.isEmpty())
    }

    @Test fun settingsRestoreOnReopen() {
        val store = MemoryStore()
        val vm = ExplorerViewModel(store)
        vm.update { it.copy(tuning = dropC, scaleRoot = 9, family = "Pentatonic", modeIndex = 4, lefty = true) }
        vm.setChord(4, "Minor 7")
        assertNotNull(store.load(KEY_STATE))

        val s = ExplorerViewModel(store).state
        assertEquals(dropC, s.tuning)
        assertEquals("Minor Pentatonic", s.modeName)
        assertTrue(s.lefty)
        assertTrue(s.chordOn)
        assertEquals(4, s.chordRoot)
        assertEquals("Minor 7", s.chordTypeName)
    }
}
