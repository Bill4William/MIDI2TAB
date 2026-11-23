package com.midi2tab.fretboard.ui

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.github.takahirom.roborazzi.captureRoboImage
import com.midi2tab.fretboard.model.SheetItem
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/**
 * Renders the real screen on the JVM (Robolectric native graphics, no device)
 * so layouts can be reviewed as images. Run: ./gradlew recordRoborazziDebug
 * Images land in app/build/outputs/roborazzi/.
 */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w411dp-h891dp-night-xxhdpi")
class ScreenshotTest {
    private val noActions = object : PlatformActions {
        override fun copyText(label: String, text: String) = Unit
        override fun shareSheet(items: List<SheetItem>, title: String, lefty: Boolean) = Unit
        override fun printSheet(items: List<SheetItem>, title: String, lefty: Boolean) = Unit
    }

    private fun shot(name: String, tab: Int, setup: ExplorerViewModel.() -> Unit = {}) {
        val vm = ExplorerViewModel().apply(setup)
        captureRoboImage("build/outputs/roborazzi/$name.png") {
            FretboardTheme(dark = true) { ExplorerScreen(vm, noActions, initialTab = tab) }
        }
    }

    @Test fun scaleTab() = shot("01_scale", 0)

    @Test fun chordTab() = shot("02_chord", 1) {
        update { it.copy(chordOn = true, chordRoot = 9, chordTypeName = "Minor 7", showDegrees = true) }
    }

    @Test fun tuningTab() = shot("03_tuning_bass", 2) {
        update { it.copy(tuning = listOf(43, 38, 33, 28, 23), scaleRoot = 4, family = "Pentatonic", modeIndex = 4) }
    }

    // Extra-tall screen so the "My tunings" list below the tuning editor is in frame.
    @Config(qualifiers = "w411dp-h1500dp-night-xxhdpi")
    @Test fun savedTunings() = shot("06_saved_tunings", 2) {
        update { it.copy(tuning = listOf(62, 57, 53, 48, 43, 36)) }
        saveTuning("Drop C")
        update { it.copy(tuning = listOf(62, 59, 55, 50, 45, 38)) }
        saveTuning("Double drop D")
        message = null
    }

    @Test fun sheetTab() = shot("04_sheet", 3) {
        addScaleToSheet()
        update { it.copy(chordOn = true, chordRoot = 0, chordTypeName = "Major") }
    }

    @Config(qualifiers = "w891dp-h411dp-night-xxhdpi")
    @Test fun landscape() = shot("05_landscape", 0) {
        update { it.copy(scaleRoot = 2, family = "Harmonic Minor", modeIndex = 4, lefty = true, highlight = setOf(6)) }
    }
}
