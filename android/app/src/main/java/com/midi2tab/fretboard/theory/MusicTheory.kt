/*
 * Music theory engine — a direct port of src/music_theory.py.
 *
 * Pure Kotlin, no Android dependencies: scales and their modes, chord
 * construction, correctly spelled note names, scale-degree labels, diatonic
 * harmony and chord-voicing search for any string count / tuning.
 *
 * Results must match the Python engine exactly; the unit tests compare against
 * golden data generated from it (tools/gen_theory_golden.py).
 *
 * Conventions:
 *   - Pitch classes are ints 0–11 (C = 0).
 *   - Tunings are lists of MIDI pitches ordered high → low
 *     (index 0 = highest-pitched string).
 */
package com.midi2tab.fretboard.theory

import kotlin.math.abs

// ── Note names & spelling ─────────────────────────────────────────────────────

val SHARP_NAMES = listOf("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
val FLAT_NAMES = listOf("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")

/** Root picker labels — enharmonic pairs shown together, like most theory tools. */
val ROOT_CHOICES = listOf(
    "C", "C#/Db", "D", "D#/Eb", "E", "F",
    "F#/Gb", "G", "G#/Ab", "A", "A#/Bb", "B",
)

private val LETTERS = listOf("C", "D", "E", "F", "G", "A", "B")
private val LETTER_PC = mapOf("C" to 0, "D" to 2, "E" to 4, "F" to 5, "G" to 7, "A" to 9, "B" to 11)
private val ACC_STR = mapOf(-2 to "bb", -1 to "b", 0 to "", 1 to "#", 2 to "##")

/** Python-style modulo: always non-negative for a positive divisor. */
internal fun mod(a: Int, n: Int): Int = ((a % n) + n) % n

/** 'C#', 'Db', 'C#/Db', 'E#', 'Cb' → pitch class. */
fun pcFromName(raw: String): Int {
    val name = raw.split("/")[0].trim()
    require(name.isNotEmpty() && name[0].uppercaseChar().toString() in LETTER_PC) {
        "Unknown note '$name'"
    }
    var pc = LETTER_PC.getValue(name[0].uppercaseChar().toString())
    for (ch in name.substring(1)) {
        pc += when (ch) {
            '#', '♯' -> 1
            'b', '♭' -> -1
            else -> throw IllegalArgumentException("Unknown note '$name'")
        }
    }
    return mod(pc, 12)
}

/** Spell pitch class [pc] using letter LETTERS[letterIdx]; returns (name, accidental). */
private fun spell(letterIdx: Int, pc: Int): Pair<String, Int> {
    val letter = LETTERS[mod(letterIdx, 7)]
    var diff = mod(pc - LETTER_PC.getValue(letter), 12)
    if (diff > 6) diff -= 12
    return (letter + (ACC_STR[diff] ?: "?")) to diff
}

/**
 * Note names for a scale. Seven-note scales get one letter per degree
 * (F major → Bb, not A#), with the root spelled whichever enharmonic way needs
 * fewer accidentals. Other scales fall back to sharps or flats.
 */
fun spellScale(rootPc: Int, intervals: List<Int>, preferFlats: Boolean? = null): List<String> {
    val pcs = intervals.map { mod(rootPc + it, 12) }
    if (intervals.size == 7) {
        var best: Pair<Int, List<String>>? = null
        for (rootLetter in 0 until 7) {
            val (_, rootAcc) = spell(rootLetter, rootPc)
            if (abs(rootAcc) > 1) continue
            if (preferFlats == true && rootAcc > 0) continue
            if (preferFlats == false && rootAcc < 0) continue
            val names = mutableListOf<String>()
            var cost = 0
            pcs.forEachIndexed { deg, pc ->
                val (n, acc) = spell(rootLetter + deg, pc)
                names += n
                cost += abs(acc) * (if (abs(acc) < 2) 1 else 4)
            }
            if (names.any { '?' in it }) continue
            if (best == null || cost < best.first) best = cost to names
        }
        if (best != null) return best.second
    }
    val flats = preferFlats ?: (rootPc in setOf(5, 10, 3, 8, 1)) // F Bb Eb Ab Db
    val table = if (flats) FLAT_NAMES else SHARP_NAMES
    return pcs.map { table[it] }
}

fun midiToName(pitch: Int): String = "${SHARP_NAMES[mod(pitch, 12)]}${Math.floorDiv(pitch, 12) - 1}"

/** Note letter (with accidental) of a MIDI pitch, without the octave. */
fun midiToLetter(pitch: Int): String = SHARP_NAMES[mod(pitch, 12)]

// ── Scales & modes ────────────────────────────────────────────────────────────

data class ScaleFamily(
    val name: String,
    val intervals: List<Int>,
    val modeNames: List<String>, // one per rotation that is offered
)

val SCALE_FAMILIES: List<ScaleFamily> = listOf(
    ScaleFamily("Major (Diatonic)", listOf(0, 2, 4, 5, 7, 9, 11), listOf(
        "Ionian (Major)", "Dorian", "Phrygian", "Lydian",
        "Mixolydian", "Aeolian (Natural Minor)", "Locrian")),
    ScaleFamily("Harmonic Minor", listOf(0, 2, 3, 5, 7, 8, 11), listOf(
        "Harmonic Minor", "Locrian ♮6", "Ionian #5", "Dorian #4",
        "Phrygian Dominant", "Lydian #2", "Ultralocrian")),
    ScaleFamily("Melodic Minor", listOf(0, 2, 3, 5, 7, 9, 11), listOf(
        "Melodic Minor (Jazz)", "Dorian b2", "Lydian Augmented",
        "Lydian Dominant", "Mixolydian b6", "Locrian ♮2", "Altered")),
    ScaleFamily("Harmonic Major", listOf(0, 2, 4, 5, 7, 8, 11), listOf(
        "Harmonic Major", "Dorian b5", "Phrygian b4", "Lydian b3",
        "Mixolydian b2", "Lydian Augmented #2", "Locrian bb7")),
    ScaleFamily("Double Harmonic", listOf(0, 1, 4, 5, 7, 8, 11), listOf(
        "Double Harmonic Major", "Lydian #2 #6", "Ultraphrygian",
        "Hungarian Minor", "Oriental", "Ionian #2 #5", "Locrian bb3 bb7")),
    ScaleFamily("Pentatonic", listOf(0, 2, 4, 7, 9), listOf(
        "Major Pentatonic", "Egyptian (Suspended)", "Man Gong (Blues Minor)",
        "Ritusen (Blues Major)", "Minor Pentatonic")),
    ScaleFamily("Blues", listOf(0, 3, 5, 6, 7, 10), listOf("Minor Blues")),
    ScaleFamily("Major Blues", listOf(0, 2, 3, 4, 7, 9), listOf("Major Blues")),
    ScaleFamily("Bebop", listOf(0, 2, 4, 5, 7, 9, 10, 11), listOf("Bebop Dominant")),
    ScaleFamily("Hirajoshi", listOf(0, 2, 3, 7, 8), listOf("Hirajoshi")),
    ScaleFamily("Whole Tone", listOf(0, 2, 4, 6, 8, 10), listOf("Whole Tone")),
    ScaleFamily("Diminished", listOf(0, 2, 3, 5, 6, 8, 9, 11), listOf(
        "Whole-Half", "Half-Whole (Dominant)")),
    ScaleFamily("Augmented", listOf(0, 3, 4, 7, 8, 11), listOf(
        "Augmented", "Inverse Augmented")),
    ScaleFamily("Chromatic", (0 until 12).toList(), listOf("Chromatic")),
)

fun scaleFamily(name: String): ScaleFamily = SCALE_FAMILIES.first { it.name == name }

/** Intervals (from the mode's own root) of rotation [modeIndex] of [family]. */
fun modeIntervals(family: String, modeIndex: Int = 0): List<Int> {
    val base = scaleFamily(family).intervals
    val k = mod(modeIndex, base.size)
    val start = base[k]
    return (base.drop(k) + base.take(k)).map { mod(it - start, 12) }.sorted()
}

/** Locate a mode by (case-insensitive, partial) name → (family, index). */
fun findMode(name: String): Pair<String, Int>? {
    val want = name.lowercase()
    for (fam in SCALE_FAMILIES) {
        fam.modeNames.forEachIndexed { i, m ->
            val lm = m.lowercase()
            if (lm == want || lm.startsWith("$want ")) return fam.name to i
        }
    }
    return null
}

/** Interval → degree label, used for non-heptatonic scales and chords. */
private val DEGREE_BY_SEMITONE = listOf("1", "b2", "2", "b3", "3", "4", "b5", "5", "b6", "6", "b7", "7")
private val MAJOR_STEPS = listOf(0, 2, 4, 5, 7, 9, 11)

/**
 * Scale-degree labels relative to the major scale.
 * Seven-note scales are labelled positionally (Lydian → #4, not b5).
 */
fun degreeLabels(intervals: List<Int>): List<String> {
    if (intervals.size == 7) {
        return intervals.mapIndexed { deg, iv ->
            var diff = iv - MAJOR_STEPS[deg]
            if (diff > 6) diff -= 12 else if (diff < -6) diff += 12
            (ACC_STR[diff] ?: "?") + (deg + 1)
        }
    }
    return intervals.map { DEGREE_BY_SEMITONE[mod(it, 12)] }
}

// ── Chords ────────────────────────────────────────────────────────────────────

data class ChordType(
    val symbol: String,            // suffix appended to the root, e.g. "m7"
    val name: String,
    val intervals: List<Int>,      // semitones above root (may exceed 12)
    val labels: List<String>,      // degree labels matching [intervals]
    val optional: Set<Int> = emptySet(), // intervals that a voicing may omit
)

private fun ct(symbol: String, name: String, ivs: List<Int>, labels: List<String>, optional: Set<Int> = emptySet()) =
    ChordType(symbol, name, ivs, labels, optional)

val CHORD_TYPES: List<ChordType> = listOf(
    ct("", "Major", listOf(0, 4, 7), listOf("1", "3", "5")),
    ct("m", "Minor", listOf(0, 3, 7), listOf("1", "b3", "5")),
    ct("dim", "Diminished", listOf(0, 3, 6), listOf("1", "b3", "b5")),
    ct("aug", "Augmented", listOf(0, 4, 8), listOf("1", "3", "#5")),
    ct("5", "Power (5)", listOf(0, 7), listOf("1", "5")),
    ct("sus2", "Sus2", listOf(0, 2, 7), listOf("1", "2", "5")),
    ct("sus4", "Sus4", listOf(0, 5, 7), listOf("1", "4", "5")),
    ct("6", "Major 6", listOf(0, 4, 7, 9), listOf("1", "3", "5", "6"), setOf(7)),
    ct("m6", "Minor 6", listOf(0, 3, 7, 9), listOf("1", "b3", "5", "6"), setOf(7)),
    ct("7", "Dominant 7", listOf(0, 4, 7, 10), listOf("1", "3", "5", "b7"), setOf(7)),
    ct("maj7", "Major 7", listOf(0, 4, 7, 11), listOf("1", "3", "5", "7"), setOf(7)),
    ct("m7", "Minor 7", listOf(0, 3, 7, 10), listOf("1", "b3", "5", "b7"), setOf(7)),
    ct("mMaj7", "Minor-Major 7", listOf(0, 3, 7, 11), listOf("1", "b3", "5", "7"), setOf(7)),
    ct("m7b5", "Half-Diminished", listOf(0, 3, 6, 10), listOf("1", "b3", "b5", "b7")),
    ct("dim7", "Diminished 7", listOf(0, 3, 6, 9), listOf("1", "b3", "b5", "bb7")),
    ct("maj7#5", "Augmented Major 7", listOf(0, 4, 8, 11), listOf("1", "3", "#5", "7")),
    ct("aug7", "Augmented 7", listOf(0, 4, 8, 10), listOf("1", "3", "#5", "b7")),
    ct("7sus4", "Dominant 7 sus4", listOf(0, 5, 7, 10), listOf("1", "4", "5", "b7"), setOf(7)),
    ct("add9", "Add 9", listOf(0, 4, 7, 14), listOf("1", "3", "5", "9"), setOf(7)),
    ct("madd9", "Minor add 9", listOf(0, 3, 7, 14), listOf("1", "b3", "5", "9"), setOf(7)),
    ct("9", "Dominant 9", listOf(0, 4, 7, 10, 14), listOf("1", "3", "5", "b7", "9"), setOf(7)),
    ct("maj9", "Major 9", listOf(0, 4, 7, 11, 14), listOf("1", "3", "5", "7", "9"), setOf(7)),
    ct("m9", "Minor 9", listOf(0, 3, 7, 10, 14), listOf("1", "b3", "5", "b7", "9"), setOf(7)),
    ct("7b9", "Dominant 7 b9", listOf(0, 4, 7, 10, 13), listOf("1", "3", "5", "b7", "b9"), setOf(7)),
    ct("7#9", "Dominant 7 #9", listOf(0, 4, 7, 10, 15), listOf("1", "3", "5", "b7", "#9"), setOf(7)),
    ct("11", "Dominant 11", listOf(0, 4, 7, 10, 14, 17),
        listOf("1", "3", "5", "b7", "9", "11"), setOf(4, 7, 14)),
    ct("m11", "Minor 11", listOf(0, 3, 7, 10, 14, 17),
        listOf("1", "b3", "5", "b7", "9", "11"), setOf(7, 14)),
    ct("13", "Dominant 13", listOf(0, 4, 7, 10, 14, 21),
        listOf("1", "3", "5", "b7", "9", "13"), setOf(7, 14)),
)

fun chordType(name: String): ChordType = CHORD_TYPES.first { it.name == name }

/** pitch class → chord-degree label ('1', 'b3', '5', …). */
fun chordDegreeMap(rootPc: Int, chord: ChordType): Map<Int, String> =
    chord.intervals.zip(chord.labels).associate { (iv, lbl) -> mod(rootPc + iv, 12) to lbl }

/** Black-key roots default to the more common spelling (Db, Eb, F#, Ab, Bb). */
private val DEFAULT_ROOT_NAME = listOf("C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")

fun defaultRootName(pc: Int): String = DEFAULT_ROOT_NAME[mod(pc, 12)]

/** pitch class → spelled name, using the degree labels (b3 → a 3rd up). */
fun spellChord(rootPc: Int, chord: ChordType, rootName: String? = null): Map<Int, String> {
    val rn = rootName ?: defaultRootName(rootPc)
    val rootLetter = LETTERS.indexOf(rn[0].uppercaseChar().toString())
    val out = LinkedHashMap<Int, String>()
    chord.intervals.zip(chord.labels).forEach { (iv, lbl) ->
        val num = lbl.filter { it.isDigit() }.toInt()
        val pc = mod(rootPc + iv, 12)
        val (name, acc) = spell(rootLetter + num - 1, pc)
        // Double accidentals are correct on paper but hard to read on a
        // fretboard (E7#9's F## is played and named as G), so simplify them.
        out[pc] = if (abs(acc) <= 1) name else defaultRootName(pc)
    }
    return out
}

/** Exact match of a pitch-class set (with known root) to a chord type. */
fun identifyChord(pcs: Collection<Int>, rootPc: Int): ChordType? {
    val rel = pcs.map { mod(it - rootPc, 12) }.toSet()
    return CHORD_TYPES.firstOrNull { c -> c.intervals.map { mod(it, 12) }.toSet() == rel }
}

private val ROMAN = listOf("I", "II", "III", "IV", "V", "VI", "VII")

data class DiatonicChord(val numeral: String, val rootPc: Int, val type: ChordType?)

/** Harmonise a seven-note scale by stacking thirds. */
fun diatonicChords(rootPc: Int, intervals: List<Int>, sevenths: Boolean = false): List<DiatonicChord> {
    if (intervals.size != 7) return emptyList()
    val size = if (sevenths) 4 else 3
    return (0 until 7).map { d ->
        val pcs = (0 until size).map { k -> mod(rootPc + intervals[(d + 2 * k) % 7], 12) }
        val croot = pcs[0]
        val ctype = identifyChord(pcs, croot)
        val third = mod(pcs[1] - croot, 12)
        val fifth = mod(pcs[2] - croot, 12)
        var numeral = if (third == 4) ROMAN[d] else ROMAN[d].lowercase()
        if (fifth == 6) {
            numeral += if (!sevenths || mod(pcs[3] - croot, 12) == 9) "°" else "ø"
        } else if (fifth == 8) {
            numeral += "+"
        }
        // Prefix accidental when the degree is altered vs. the major scale
        val diff = intervals[d] - MAJOR_STEPS[d]
        if (diff != 0) numeral = (if (diff < 0) "b" else "#").repeat(abs(diff)) + numeral
        DiatonicChord(numeral, croot, ctype)
    }
}

// ── Chord voicing search ──────────────────────────────────────────────────────

const val MUTED = -1

data class Voicing(
    val frets: List<Int>, // per string, high → low; MUTED = not played
    val score: Double,
) {
    val position: Int get() = frets.filter { it > 0 }.minOrNull() ?: 0

    /** Chord-chart string, low → high, e.g. "x32010". */
    fun shape(): String {
        val parts = frets.reversed().map { if (it == MUTED) "x" else it.toString() }
        val sep = if (frets.any { it >= 10 }) "-" else ""
        return parts.joinToString(sep)
    }
}

/**
 * Search playable voicings of [chord] for an arbitrary tuning.
 *
 * Rules: every required chord tone sounds; played strings form one block
 * (muted strings only below the bass, above the top note, or at most one
 * interior gap); fretted notes fit inside [maxSpan] frets; no more than four
 * fingers (a shared lowest fret counts as one barre finger); an open string
 * can't sit under a barre the shape needs. Results are sorted by neck
 * position, then by playability score.
 */
fun findVoicings(
    tuning: List<Int>,
    rootPc: Int,
    chord: ChordType,
    maxFret: Int = 12,
    maxSpan: Int = 4,
    rootInBass: Boolean = true,
    maxResults: Int = 80,
): List<Voicing> {
    val n = tuning.size
    if (n == 0) return emptyList()
    val tones = chord.intervals.map { mod(rootPc + it, 12) }.toSet()
    val required = chord.intervals.filter { it !in chord.optional }.map { mod(rootPc + it, 12) }.toSet()
    // Low → high order makes "bass note" reasoning straightforward.
    val order = (n - 1 downTo 0).toList()
    // Guitars and up: at least four sounding strings; basses/ukes: three.
    val minPlayed = minOf(n, maxOf(required.size, if (n >= 6) 4 else 3))

    val found = LinkedHashMap<List<Int>, Double>()

    for (lo in 0..maxFret) {
        val hi = minOf(maxFret, lo + maxSpan - 1)
        val options: List<List<Int>> = order.map { s ->
            (listOf(0) + (maxOf(lo, 1)..hi).toList())
                .filter { f -> mod(tuning[s] + f, 12) in tones }
                .toSortedSet().toList()
        }
        val chosen = IntArray(n)

        fun evaluate(lowToHigh: IntArray) {
            val played = lowToHigh.indices.filter { lowToHigh[it] != MUTED }
            if (played.size < minPlayed) return
            val first = played.first()
            val last = played.last()
            val gaps = (first..last).count { lowToHigh[it] == MUTED }
            if (gaps > 1) return
            val notes = played.map { mod(tuning[order[it]] + lowToHigh[it], 12) }
            if (!notes.containsAll(required)) return
            if (rootInBass && notes[0] != rootPc) return
            val fretted = played.map { lowToHigh[it] }.filter { it > 0 }
            if (fretted.isNotEmpty()) {
                val fmin = fretted.min()
                val fmax = fretted.max()
                if (fmax - fmin >= maxSpan) return
                // Only keep the voicing in the window it "belongs" to.
                if (fmin != maxOf(lo, 1) && lo != 0) return
                val atMin = fretted.count { it == fmin }
                val fingers = (if (atMin >= 2) 1 else atMin) + fretted.count { it != fmin }
                if (fingers > 4) return
                if (fretted.size > 4) {
                    // Needs a barre at fmin: strings it covers can't ring open.
                    val barred = played.filter { lowToHigh[it] == fmin }
                    if ((barred.first()..barred.last()).any { lowToHigh[it] == 0 }) return
                }
            } else if (lo != 0) {
                return
            }
            val highToLow = lowToHigh.reversed()
            if (highToLow in found) return
            val span = if (fretted.isNotEmpty()) fretted.max() - fretted.min() else 0
            val opens = played.size - fretted.size
            // Open strings help in open position but are awkward up the neck.
            val openWeight = if (fretted.isEmpty() || fretted.max() <= 3) -0.15 else 0.5
            val score = span * 0.6 + gaps * 2.5 -
                played.size * 0.4 -
                notes.toSet().size * 0.5 +
                opens * openWeight
            found[highToLow] = score
        }

        // pending = muted strings since the last played one; they become an
        // interior gap only if another string is played above them.
        fun dfs(k: Int, played: Int, gaps: Int, pending: Int) {
            if (k == n) {
                evaluate(chosen)
                return
            }
            val started = played > 0
            if (played + (n - k) < minPlayed) return
            for (f in options[k]) {
                if (!started && rootInBass && mod(tuning[order[k]] + f, 12) != rootPc) continue
                val newGaps = gaps + if (started) pending else 0
                if (newGaps > 1) continue
                chosen[k] = f
                dfs(k + 1, played + 1, newGaps, 0)
            }
            chosen[k] = MUTED
            dfs(k + 1, played, gaps, if (started) pending + 1 else 0)
        }

        dfs(0, 0, 0, 0)
    }

    val voicings = found.map { (fr, sc) -> Voicing(fr, sc) }
        .sortedWith(compareBy<Voicing> { it.position }.thenBy { it.score })
    // Keep the best few per position so the list stays browsable.
    val perPos = HashMap<Int, Int>()
    val trimmed = ArrayList<Voicing>()
    for (v in voicings) {
        val c = perPos[v.position] ?: 0
        if (c < 4) {
            trimmed += v
            perPos[v.position] = c + 1
        }
    }
    return trimmed.take(maxResults)
}

/** Index of the most practical voicing (low on the neck, easy to play). */
fun bestVoicingIndex(voicings: List<Voicing>): Int {
    if (voicings.isEmpty()) return 0
    return voicings.indices.minBy { voicings[it].score + 0.4 * voicings[it].position }
}
