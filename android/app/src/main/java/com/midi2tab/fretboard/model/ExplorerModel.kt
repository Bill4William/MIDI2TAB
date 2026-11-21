/*
 * What the fretboard shows, independent of how it is drawn.
 *
 * ExplorerState holds every user choice; the functions here turn it into
 * per-position cell info, the status line, and printable sheet items. Keeping
 * this free of Android/Compose lets it be unit-tested on the JVM and mirrors
 * the desktop Fretboard Explorer (src/fretboard_window.py).
 */
package com.midi2tab.fretboard.model

import com.midi2tab.fretboard.theory.CHORD_TYPES
import com.midi2tab.fretboard.theory.ChordType
import com.midi2tab.fretboard.theory.MUTED
import com.midi2tab.fretboard.theory.ROOT_CHOICES
import com.midi2tab.fretboard.theory.SCALE_FAMILIES
import com.midi2tab.fretboard.theory.Voicing
import com.midi2tab.fretboard.theory.chordDegreeMap
import com.midi2tab.fretboard.theory.chordType
import com.midi2tab.fretboard.theory.defaultRootName
import com.midi2tab.fretboard.theory.degreeLabels
import com.midi2tab.fretboard.theory.midiToLetter
import com.midi2tab.fretboard.theory.mod
import com.midi2tab.fretboard.theory.modeIntervals
import com.midi2tab.fretboard.theory.scaleFamily
import com.midi2tab.fretboard.theory.spellChord
import com.midi2tab.fretboard.theory.spellScale

const val NUM_FRETS = 12
const val MIN_STRINGS = 1
const val MAX_STRINGS = 12
const val MIN_PITCH = 12   // C0
const val MAX_PITCH = 107  // B7

data class Preset(val name: String, val tuning: List<Int>) // high → low, sounding pitch

val PRESETS = listOf(
    Preset("Guitar – Standard", listOf(64, 59, 55, 50, 45, 40)),
    Preset("Guitar – Drop D", listOf(64, 59, 55, 50, 45, 38)),
    Preset("Guitar – Open G", listOf(62, 59, 55, 50, 43, 38)),
    Preset("Guitar – Open E", listOf(64, 59, 56, 52, 47, 40)),
    Preset("Guitar – DADGAD", listOf(62, 57, 55, 50, 45, 38)),
    Preset("Guitar – 7-string", listOf(64, 59, 55, 50, 45, 40, 35)),
    Preset("Guitar – 8-string", listOf(64, 59, 55, 50, 45, 40, 35, 30)),
    Preset("Bass – 4-string", listOf(43, 38, 33, 28)),
    Preset("Bass – Drop D", listOf(43, 38, 33, 26)),
    Preset("Bass – 5-string", listOf(43, 38, 33, 28, 23)),
    Preset("Bass – 6-string", listOf(48, 43, 38, 33, 28, 23)),
    Preset("Ukulele – GCEA", listOf(69, 64, 60, 67)),
)

data class ExplorerState(
    val tuning: List<Int> = PRESETS[0].tuning,
    val scaleOn: Boolean = true,
    val scaleRoot: Int = 0,
    val family: String = SCALE_FAMILIES[0].name,
    val modeIndex: Int = 0,
    val showDegrees: Boolean = false,
    val allNotes: Boolean = true,
    val sevenths: Boolean = false,
    val chordOn: Boolean = false,
    val chordRoot: Int = 0,
    val chordTypeName: String = CHORD_TYPES[0].name,
    val allChordTones: Boolean = false,
    val rootInBass: Boolean = true,
    val maxSpan: Int = 4,
    val highlight: Set<Int> = emptySet(),
    val lefty: Boolean = false,
) {
    val scaleIntervals: List<Int> get() = modeIntervals(family, modeIndex)
    val modeName: String get() = scaleFamily(family).modeNames[modeIndex]
    val chordType: ChordType get() = chordType(chordTypeName)
    val stringNames: List<String> get() = tuning.map { midiToLetter(it) }
}

enum class Role { VOICING_ROOT, VOICING, SCALE_ROOT, SCALE, CHORD_TONE, OTHER }

data class Cell(
    val string: Int,          // 0 = highest string
    val fret: Int,            // 0 = open
    val pc: Int,
    val label: String,
    val role: Role,
    val chordRing: Boolean,   // ringed as a chord tone ("All chord tones")
    val highlighted: Boolean,
) {
    /** Drawn as a filled/ringed dot rather than faint text. */
    val prominent: Boolean get() = role != Role.OTHER || chordRing || highlighted
}

/** Spelling of a chord's root: reuse the scale's spelling when it belongs to it. */
fun chordRootName(s: ExplorerState, root: Int = s.chordRoot): String {
    if (s.scaleOn) {
        val ivs = s.scaleIntervals
        val pcs = ivs.map { mod(s.scaleRoot + it, 12) }
        val idx = pcs.indexOf(root)
        if (idx >= 0) return spellScale(s.scaleRoot, ivs)[idx]
    }
    return defaultRootName(root)
}

fun chordTitle(s: ExplorerState, root: Int = s.chordRoot, type: ChordType = s.chordType): String =
    chordRootName(s, root) + type.symbol

/** Every visible position on the neck (open string + frets 1–12). */
fun computeCells(s: ExplorerState, voicing: Voicing?): List<Cell> {
    val scale = HashMap<Int, Pair<String, String>>()
    if (s.scaleOn) {
        val ivs = s.scaleIntervals
        val names = spellScale(s.scaleRoot, ivs)
        val degs = degreeLabels(ivs)
        ivs.forEachIndexed { i, iv -> scale[mod(s.scaleRoot + iv, 12)] = names[i] to degs[i] }
    }
    val chord = HashMap<Int, Pair<String, String>>()
    if (s.chordOn) {
        val spelled = spellChord(s.chordRoot, s.chordType, chordRootName(s))
        chordDegreeMap(s.chordRoot, s.chordType).forEach { (pc, deg) -> chord[pc] = spelled.getValue(pc) to deg }
    }
    val v = if (s.chordOn) voicing else null
    val out = ArrayList<Cell>(s.tuning.size * (NUM_FRETS + 1))
    for (str in s.tuning.indices) {
        for (fret in 0..NUM_FRETS) {
            val pc = mod(s.tuning[str] + fret, 12)
            val inVoicing = v != null && v.frets[str] == fret
            val inChord = pc in chord
            val inScale = pc in scale
            val ring = !inVoicing && inChord && s.allChordTones
            val (role, names) = when {
                inVoicing -> (if (pc == s.chordRoot) Role.VOICING_ROOT else Role.VOICING) to chord.getValue(pc)
                ring && inScale -> (if (pc == s.scaleRoot) Role.SCALE_ROOT else Role.SCALE) to chord.getValue(pc)
                ring -> Role.CHORD_TONE to chord.getValue(pc)
                inScale -> (if (pc == s.scaleRoot) Role.SCALE_ROOT else Role.SCALE) to scale.getValue(pc)
                else -> Role.OTHER to ((chord[pc] ?: scale[pc])?.first ?: defaultRootName(pc)).let { it to "" }
            }
            val label = if (s.showDegrees && names.second.isNotEmpty()) names.second else names.first
            out += Cell(str, fret, pc, label, role, ring, pc in s.highlight)
        }
    }
    return out
}

fun scaleSummary(s: ExplorerState): String {
    val ivs = s.scaleIntervals
    val names = spellScale(s.scaleRoot, ivs)
    return "${names[0]} ${s.modeName}: ${names.joinToString(" ")}   (${degreeLabels(ivs).joinToString(" ")})"
}

fun chordSummary(s: ExplorerState): String {
    val sp = spellChord(s.chordRoot, s.chordType, chordRootName(s))
    return "${chordTitle(s)}: " + s.chordType.intervals.joinToString(" ") { sp.getValue(mod(s.chordRoot + it, 12)) }
}

/** Plain-text tab snippet of a voicing, high string first. */
fun voicingTab(s: ExplorerState, v: Voicing, title: String = chordTitle(s)): String {
    val names = s.stringNames
    val width = names.maxOf { it.length }
    return buildString {
        appendLine(title)
        names.zip(v.frets).forEach { (n, f) ->
            val cell = if (f == MUTED) "x" else f.toString()
            appendLine(n.padEnd(width) + "|-" + cell.padEnd(3, '-') + "|")
        }
    }
}

// ── Printable sheet items ─────────────────────────────────────────────────────

sealed interface SheetItem {
    val title: String
    val subtitle: String
    val stringNames: List<String> // high → low
}

data class ScaleSheetItem(
    override val title: String,
    override val subtitle: String,
    override val stringNames: List<String>,
    val cells: Map<Pair<Int, Int>, Pair<String, Boolean>>, // (string, fret) → (label, isRoot)
) : SheetItem

data class ChordSheetItem(
    override val title: String,
    override val subtitle: String,
    override val stringNames: List<String>,
    val frets: List<Int>,       // high → low, MUTED = not played
    val labels: List<String>,
    val roots: List<Boolean>,
) : SheetItem

fun scaleSheetItem(s: ExplorerState): ScaleSheetItem {
    val ivs = s.scaleIntervals
    val names = spellScale(s.scaleRoot, ivs)
    val degs = degreeLabels(ivs)
    val byPc = ivs.indices.associate { mod(s.scaleRoot + ivs[it], 12) to (names[it] to degs[it]) }
    val cells = LinkedHashMap<Pair<Int, Int>, Pair<String, Boolean>>()
    s.tuning.forEachIndexed { str, open ->
        for (f in 0..NUM_FRETS) {
            val pc = mod(open + f, 12)
            val nd = byPc[pc] ?: continue
            cells[str to f] = (if (s.showDegrees) nd.second else nd.first) to (pc == s.scaleRoot)
        }
    }
    return ScaleSheetItem(
        title = "${names[0]} ${s.modeName}",
        subtitle = names.joinToString("  ") + "     (" + degs.joinToString(" ") + ")" +
            "     Tuning: " + s.stringNames.reversed().joinToString(" "),
        stringNames = s.stringNames,
        cells = cells,
    )
}

fun chordSheetItem(s: ExplorerState, root: Int, type: ChordType, v: Voicing): ChordSheetItem {
    val spelled = spellChord(root, type, chordRootName(s, root))
    val degs = chordDegreeMap(root, type)
    val labels = ArrayList<String>()
    val roots = ArrayList<Boolean>()
    v.frets.forEachIndexed { str, f ->
        val pc = mod(s.tuning[str] + f, 12)
        labels += if (f == MUTED) "" else if (s.showDegrees) degs[pc] ?: "" else spelled[pc] ?: ""
        roots += f != MUTED && pc == root
    }
    return ChordSheetItem(chordTitle(s, root, type), v.shape(), s.stringNames, v.frets, labels, roots)
}

fun rootChoiceIndex(pc: Int): Int = mod(pc, ROOT_CHOICES.size)
