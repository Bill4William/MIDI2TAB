/*
 * Saving custom tunings and the last-used settings between app launches.
 *
 * Storage is a plain key → string store (SharedPreferences on Android, a map
 * in tests). Encoding is deliberately simple text, and decoding skips anything
 * malformed or out of range instead of failing, so a corrupt or outdated value
 * can never stop the app from starting.
 */
package com.midi2tab.fretboard.model

import com.midi2tab.fretboard.theory.CHORD_TYPES
import com.midi2tab.fretboard.theory.SCALE_FAMILIES
import com.midi2tab.fretboard.theory.midiToLetter

interface SettingsStore {
    fun load(key: String): String?
    fun save(key: String, value: String)
}

class MemoryStore(private val map: MutableMap<String, String> = mutableMapOf()) : SettingsStore {
    override fun load(key: String) = map[key]
    override fun save(key: String, value: String) {
        map[key] = value
    }
}

const val KEY_STATE = "state.v1"
const val KEY_TUNINGS = "tunings.v1"
const val MAX_NAME_LENGTH = 40

data class SavedTuning(val name: String, val tuning: List<Int>) // high → low

/** "E A D G B E" — low string first, the way players name tunings. */
fun tuningLabel(tuning: List<Int>): String = tuning.reversed().joinToString(" ") { midiToLetter(it) }

/** Trims a user-typed name and strips characters the storage format uses. */
fun cleanTuningName(raw: String): String =
    raw.replace(Regex("[\\t\\r\\n]"), " ").trim().take(MAX_NAME_LENGTH)

private fun validTuning(t: List<Int>) = t.size in MIN_STRINGS..MAX_STRINGS && t.all { it in MIN_PITCH..MAX_PITCH }

/** One tuning per line: name, a tab, then pitches high → low. */
fun encodeTunings(list: List<SavedTuning>): String =
    list.joinToString("\n") { "${cleanTuningName(it.name)}\t${it.tuning.joinToString(",")}" }

fun decodeTunings(text: String?): List<SavedTuning> {
    if (text.isNullOrBlank()) return emptyList()
    return text.lineSequence().mapNotNull { line ->
        val parts = line.split('\t')
        if (parts.size != 2) return@mapNotNull null
        val name = cleanTuningName(parts[0])
        val tuning = parts[1].split(',').map { it.trim().toIntOrNull() ?: return@mapNotNull null }
        if (name.isEmpty() || !validTuning(tuning)) null else SavedTuning(name, tuning)
    }.toList()
}

/** The settings worth restoring (not transient ones like highlighted notes). */
fun encodeState(s: ExplorerState): String = listOf(
    "tuning" to s.tuning.joinToString(","),
    "scaleOn" to s.scaleOn,
    "scaleRoot" to s.scaleRoot,
    "family" to s.family,
    "modeIndex" to s.modeIndex,
    "showDegrees" to s.showDegrees,
    "allNotes" to s.allNotes,
    "sevenths" to s.sevenths,
    "chordOn" to s.chordOn,
    "chordRoot" to s.chordRoot,
    "chordType" to s.chordTypeName,
    "allChordTones" to s.allChordTones,
    "rootInBass" to s.rootInBass,
    "maxSpan" to s.maxSpan,
    "lefty" to s.lefty,
).joinToString("\n") { (k, v) -> "$k=$v" }

/** Restores what it can; each missing or invalid field keeps its default. */
fun decodeState(text: String?, default: ExplorerState = ExplorerState()): ExplorerState {
    if (text.isNullOrBlank()) return default
    val m = text.lineSequence().mapNotNull { line ->
        val i = line.indexOf('=')
        if (i <= 0) null else line.substring(0, i) to line.substring(i + 1)
    }.toMap()

    fun bool(k: String, d: Boolean) = m[k]?.toBooleanStrictOrNull() ?: d
    fun int(k: String, d: Int, range: IntRange) = m[k]?.toIntOrNull()?.takeIf { it in range } ?: d

    val tuning = m["tuning"]?.split(',')?.map { it.toIntOrNull() ?: -1 }?.takeIf(::validTuning) ?: default.tuning
    val family = SCALE_FAMILIES.firstOrNull { it.name == m["family"] }
    return default.copy(
        tuning = tuning,
        scaleOn = bool("scaleOn", default.scaleOn),
        scaleRoot = int("scaleRoot", default.scaleRoot, 0..11),
        family = family?.name ?: default.family,
        modeIndex = if (family == null) default.modeIndex else int("modeIndex", 0, family.modeNames.indices),
        showDegrees = bool("showDegrees", default.showDegrees),
        allNotes = bool("allNotes", default.allNotes),
        sevenths = bool("sevenths", default.sevenths),
        chordOn = bool("chordOn", default.chordOn),
        chordRoot = int("chordRoot", default.chordRoot, 0..11),
        chordTypeName = CHORD_TYPES.firstOrNull { it.name == m["chordType"] }?.name ?: default.chordTypeName,
        allChordTones = bool("allChordTones", default.allChordTones),
        rootInBass = bool("rootInBass", default.rootInBass),
        maxSpan = int("maxSpan", default.maxSpan, 3..6),
        lefty = bool("lefty", default.lefty),
    )
}

/** Name of the built-in preset or saved tuning that matches [tuning], if any. */
fun matchingTuningName(tuning: List<Int>, saved: List<SavedTuning>): String? =
    PRESETS.firstOrNull { it.tuning == tuning }?.name ?: saved.firstOrNull { it.tuning == tuning }?.name
