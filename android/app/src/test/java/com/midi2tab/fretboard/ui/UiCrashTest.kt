package com.midi2tab.fretboard.ui

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.midi2tab.fretboard.model.MemoryStore
import com.midi2tab.fretboard.model.SheetItem
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Drives the real screen through taps, the way a user does, looking for crashes. */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w411dp-h891dp-night-xxhdpi")
class UiCrashTest {
    @get:Rule val compose = createComposeRule()

    private val noActions = object : PlatformActions {
        override fun copyText(label: String, text: String) = Unit
        override fun shareSheet(items: List<SheetItem>, title: String, lefty: Boolean) = Unit
        override fun printSheet(items: List<SheetItem>, title: String, lefty: Boolean) = Unit
    }

    @Test fun addStringWhileChordShown() {
        val vm = ExplorerViewModel(MemoryStore())
        compose.setContent { FretboardTheme(dark = true) { ExplorerScreen(vm, noActions) } }
        compose.onNodeWithText("Chord").performClick()
        compose.onNodeWithText("Show chord").performClick()
        compose.waitForIdle()
        compose.onNodeWithText("Tuning").performClick()
        compose.onNodeWithText("+").performClick()
        compose.waitForIdle()
        compose.onNodeWithText("−").performClick()
        compose.onNodeWithText("−").performClick()
        compose.waitForIdle()
    }

    /** A slow search (many strings, inversions allowed) widens the gap a phone hits. */
    @Test fun addStringWhileSlowChordSearchRuns() {
        val vm = ExplorerViewModel(MemoryStore())
        vm.update {
            it.copy(tuning = listOf(64, 59, 55, 50, 45, 40, 35, 30, 25, 20, 15), chordOn = true,
                chordTypeName = "Dominant 9", rootInBass = false)
        }
        compose.setContent { FretboardTheme(dark = true) { ExplorerScreen(vm, noActions, initialTab = 2) } }
        Thread.sleep(3000) // let the first search finish
        compose.waitForIdle()
        compose.onNodeWithText("+").performClick()
        compose.waitForIdle()
        compose.onNodeWithText("−").performClick()
        compose.waitForIdle()
    }
}
