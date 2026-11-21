package com.midi2tab.fretboard.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.midi2tab.fretboard.model.ExplorerState
import com.midi2tab.fretboard.model.KEY_STATE
import com.midi2tab.fretboard.model.KEY_TUNINGS
import com.midi2tab.fretboard.model.MemoryStore
import com.midi2tab.fretboard.model.SavedTuning
import com.midi2tab.fretboard.model.SettingsStore
import com.midi2tab.fretboard.model.cleanTuningName
import com.midi2tab.fretboard.model.decodeState
import com.midi2tab.fretboard.model.decodeTunings
import com.midi2tab.fretboard.model.encodeState
import com.midi2tab.fretboard.model.encodeTunings
import com.midi2tab.fretboard.model.tuningLabel
import com.midi2tab.fretboard.model.MAX_PITCH
import com.midi2tab.fretboard.model.MAX_STRINGS
import com.midi2tab.fretboard.model.MIN_PITCH
import com.midi2tab.fretboard.model.MIN_STRINGS
import com.midi2tab.fretboard.model.NUM_FRETS
import com.midi2tab.fretboard.model.Preset
import com.midi2tab.fretboard.model.SheetItem
import com.midi2tab.fretboard.model.chordSheetItem
import com.midi2tab.fretboard.model.chordTitle
import com.midi2tab.fretboard.model.scaleSheetItem
import com.midi2tab.fretboard.theory.ChordType
import com.midi2tab.fretboard.theory.Voicing
import com.midi2tab.fretboard.theory.bestVoicingIndex
import com.midi2tab.fretboard.theory.diatonicChords
import com.midi2tab.fretboard.theory.findVoicings
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.concurrent.ConcurrentHashMap

class ExplorerViewModel(private val store: SettingsStore = MemoryStore()) : ViewModel() {
    var state by mutableStateOf(decodeState(store.load(KEY_STATE)))
        private set
    var savedTunings by mutableStateOf(decodeTunings(store.load(KEY_TUNINGS)))
        private set
    // Search results and the tuning/chord they were found for. A search runs in
    // the background, so between a change and its result the stored list
    // belongs to the old tuning (possibly a different string count); it must
    // never be drawn against the new one.
    private var foundVoicings by mutableStateOf<List<Voicing>>(emptyList())
    private var foundFor by mutableStateOf<VoicingKey?>(null)

    /** Voicings for the current tuning and chord; empty while a search is still running. */
    val voicings: List<Voicing>
        get() = if (state.chordOn && foundFor == key(state)) foundVoicings else emptyList()
    var voicingIndex by mutableIntStateOf(0)
        private set
    var searching by mutableStateOf(false)
        private set
    var message by mutableStateOf<String?>(null)

    val sheet = mutableStateListOf<SheetItem>()

    val currentVoicing: Voicing?
        get() = voicings.getOrNull(voicingIndex)

    // Read and filled from background searches, so it must be thread-safe.
    private val cache = ConcurrentHashMap<VoicingKey, List<Voicing>>()
    private var searchJob: Job? = null

    init {
        // A chord left on at the last launch needs its voicings found again.
        if (state.chordOn) refreshVoicings(pickBest = true)
    }

    private data class VoicingKey(
        val tuning: List<Int>, val root: Int, val type: String, val span: Int, val rootInBass: Boolean,
    )

    private fun key(s: ExplorerState, root: Int = s.chordRoot, type: String = s.chordTypeName) =
        VoicingKey(s.tuning, root, type, s.maxSpan, s.rootInBass)

    private fun search(k: VoicingKey, type: ChordType): List<Voicing> =
        cache.getOrPut(k) { findVoicings(k.tuning, k.root, type, NUM_FRETS, k.span, k.rootInBass) }

    /** Apply a change; re-run the voicing search when the chord inputs changed. */
    fun update(pickBest: Boolean = false, change: (ExplorerState) -> ExplorerState) {
        val old = state
        val new = change(old)
        state = new
        if (new != old) store.save(KEY_STATE, encodeState(new))
        val chordInputsChanged = key(old) != key(new) || old.chordOn != new.chordOn
        if (chordInputsChanged || pickBest) refreshVoicings(pickBest || key(old) != key(new))
    }

    private fun refreshVoicings(pickBest: Boolean) {
        val s = state
        searchJob?.cancel()
        if (!s.chordOn) return
        val k = key(s)
        searchJob = viewModelScope.launch {
            searching = true
            val result = withContext(Dispatchers.Default) { search(k, s.chordType) }
            foundVoicings = result
            foundFor = k
            if (pickBest || voicingIndex !in result.indices) voicingIndex = bestVoicingIndex(result)
            searching = false
        }
    }

    fun stepVoicing(delta: Int) {
        val vs = voicings
        if (vs.isEmpty()) return
        voicingIndex = Math.floorMod(voicingIndex + delta, vs.size)
    }

    // ── Tuning ────────────────────────────────────────────────────────────────

    fun changeStringCount(delta: Int) = update { s ->
        val n = s.tuning.size + delta
        when {
            n < MIN_STRINGS || n > MAX_STRINGS -> s
            // New strings go a fourth below the lowest, as on guitar and bass.
            delta > 0 -> s.copy(tuning = s.tuning + maxOf(MIN_PITCH, s.tuning.last() - 5))
            else -> s.copy(tuning = s.tuning.dropLast(1))
        }
    }

    fun shiftString(index: Int, delta: Int) = update { s ->
        val p = s.tuning[index] + delta
        if (p in MIN_PITCH..MAX_PITCH) s.copy(tuning = s.tuning.toMutableList().also { it[index] = p }) else s
    }

    fun shiftAll(delta: Int) = update { s ->
        if (s.tuning.all { it + delta in MIN_PITCH..MAX_PITCH }) s.copy(tuning = s.tuning.map { it + delta }) else s
    }

    fun applyPreset(p: Preset) = update { it.copy(tuning = p.tuning) }

    fun applySavedTuning(t: SavedTuning) = update { it.copy(tuning = t.tuning) }

    /** Saves the current tuning under [rawName], replacing one with the same name. */
    fun saveTuning(rawName: String): Boolean {
        val name = cleanTuningName(rawName)
        if (name.isEmpty()) {
            message = "Give the tuning a name"
            return false
        }
        val replaced = savedTunings.any { it.name.equals(name, ignoreCase = true) }
        savedTunings = savedTunings.filterNot { it.name.equals(name, ignoreCase = true) } +
            SavedTuning(name, state.tuning)
        store.save(KEY_TUNINGS, encodeTunings(savedTunings))
        message = (if (replaced) "Updated" else "Saved") + " tuning “$name” (${tuningLabel(state.tuning)})"
        return true
    }

    fun deleteTuning(t: SavedTuning) {
        savedTunings = savedTunings - t
        store.save(KEY_TUNINGS, encodeTunings(savedTunings))
        message = "Deleted tuning “${t.name}”"
    }

    // ── Scale / chord ─────────────────────────────────────────────────────────

    fun setChord(root: Int, typeName: String) =
        update(pickBest = true) { it.copy(chordOn = true, chordRoot = root, chordTypeName = typeName) }

    fun toggleHighlight(pc: Int) = update { s ->
        s.copy(highlight = if (pc in s.highlight) s.highlight - pc else s.highlight + pc)
    }

    fun reset() {
        update(pickBest = true) { ExplorerState(tuning = it.tuning, lefty = it.lefty) }
    }

    // ── Print sheet ───────────────────────────────────────────────────────────

    fun addScaleToSheet() {
        val item = scaleSheetItem(state)
        sheet += item
        message = "Added ${item.title} to the sheet (${sheet.size})"
    }

    fun addChordToSheet() {
        val v = currentVoicing
        if (v == null) {
            message = "Turn on a chord with a playable voicing first"
            return
        }
        val item = chordSheetItem(state, state.chordRoot, state.chordType, v)
        sheet += item
        message = "Added ${item.title} (${v.shape()}) to the sheet (${sheet.size})"
    }

    fun addDiatonicToSheet() {
        val s = state
        viewModelScope.launch {
            val added = ArrayList<SheetItem>()
            val missing = ArrayList<String>()
            withContext(Dispatchers.Default) {
                for (dc in diatonicChords(s.scaleRoot, s.scaleIntervals, s.sevenths)) {
                    val type = dc.type ?: continue
                    val vs = search(key(s, dc.rootPc, type.name), type)
                    if (vs.isEmpty()) missing += chordTitle(s, dc.rootPc, type)
                    else added += chordSheetItem(s, dc.rootPc, type, vs[bestVoicingIndex(vs)])
                }
            }
            sheet += added
            message = "Added ${added.size} chords in key to the sheet (${sheet.size})" +
                if (missing.isEmpty()) "" else " — no playable voicing for ${missing.joinToString()}"
        }
    }

    fun moveSheetItem(index: Int, delta: Int) {
        val j = index + delta
        if (index !in sheet.indices || j !in sheet.indices) return
        val item = sheet.removeAt(index)
        sheet.add(j, item)
    }

    fun removeSheetItem(index: Int) {
        if (index in sheet.indices) sheet.removeAt(index)
    }

    fun clearSheet() = sheet.clear()
}
