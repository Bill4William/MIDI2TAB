package com.midi2tab.fretboard.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Tab
import androidx.compose.material3.PrimaryTabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.midi2tab.fretboard.model.ChordSheetItem
import com.midi2tab.fretboard.model.PRESETS
import com.midi2tab.fretboard.model.ScaleSheetItem
import com.midi2tab.fretboard.model.SheetItem
import com.midi2tab.fretboard.model.chordSummary
import com.midi2tab.fretboard.model.chordTitle
import com.midi2tab.fretboard.model.computeCells
import com.midi2tab.fretboard.model.scaleSummary
import com.midi2tab.fretboard.model.voicingTab
import com.midi2tab.fretboard.theory.CHORD_TYPES
import com.midi2tab.fretboard.theory.ROOT_CHOICES
import com.midi2tab.fretboard.theory.SCALE_FAMILIES
import com.midi2tab.fretboard.theory.diatonicChords
import com.midi2tab.fretboard.theory.midiToName
import com.midi2tab.fretboard.theory.scaleFamily
import com.midi2tab.fretboard.theory.spellScale

/** Actions that need an Android Context (clipboard, sharing, printing). */
interface PlatformActions {
    fun copyText(label: String, text: String)
    fun shareSheet(items: List<SheetItem>, title: String, lefty: Boolean)
    fun printSheet(items: List<SheetItem>, title: String, lefty: Boolean)
}

private val TABS = listOf("Scale", "Chord", "Tuning", "Sheet")

@Composable
fun ExplorerScreen(vm: ExplorerViewModel, actions: PlatformActions, initialTab: Int = 0) {
    val dark = isSystemInDarkTheme()
    val palette = if (dark) DarkPalette else LightPalette
    val s = vm.state
    val voicing = vm.currentVoicing
    val cells = remember(s, voicing) { computeCells(s, voicing) }
    val snackbar = remember { SnackbarHostState() }
    var tab by rememberSaveable { mutableIntStateOf(initialTab) }

    LaunchedEffect(vm.message) {
        vm.message?.let {
            snackbar.showSnackbar(it)
            vm.message = null
        }
    }

    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Box(Modifier.safeDrawingPadding()) {
            BoxWithConstraints(Modifier.fillMaxSize()) {
                val landscape = maxWidth > maxHeight
                val neck = @Composable { m: Modifier ->
                    FretboardCanvas(
                        cells = cells, tuningNames = s.stringNames, voicing = voicing,
                        vertical = !landscape, lefty = s.lefty, palette = palette,
                        showAllNotes = s.allNotes, onTapNote = vm::toggleHighlight, modifier = m,
                    )
                }
                val panel = @Composable { m: Modifier ->
                    Column(m) {
                        StatusLine(vm)
                        PrimaryTabRow(selectedTabIndex = tab) {
                            TABS.forEachIndexed { i, t ->
                                Tab(selected = tab == i, onClick = { tab = i },
                                    text = { Text(if (i == 3) "$t (${vm.sheet.size})" else t, maxLines = 1) })
                            }
                        }
                        Column(
                            Modifier.fillMaxWidth().weight(1f).verticalScroll(rememberScrollState())
                                .padding(horizontal = 12.dp, vertical = 8.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            when (tab) {
                                0 -> ScaleTab(vm)
                                1 -> ChordTab(vm, actions)
                                2 -> TuningTab(vm)
                                else -> SheetTab(vm, actions)
                            }
                        }
                    }
                }
                if (landscape) {
                    Row(Modifier.fillMaxSize()) {
                        neck(Modifier.weight(0.6f).fillMaxSize().padding(4.dp))
                        panel(Modifier.weight(0.4f).fillMaxSize())
                    }
                } else {
                    Column(Modifier.fillMaxSize()) {
                        neck(Modifier.fillMaxWidth().weight(0.56f).padding(horizontal = 4.dp))
                        panel(Modifier.fillMaxWidth().weight(0.44f))
                    }
                }
            }
            SnackbarHost(snackbar, Modifier.align(Alignment.BottomCenter))
        }
    }
}

@Composable
private fun StatusLine(vm: ExplorerViewModel) {
    val s = vm.state
    val lines = buildList {
        if (s.scaleOn) add(scaleSummary(s))
        if (s.chordOn) add(chordSummary(s))
    }
    if (lines.isEmpty()) return
    Column(
        Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surfaceVariant)
            .padding(horizontal = 12.dp, vertical = 4.dp),
    ) {
        lines.forEach {
            Text(it, fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

// ── Reusable controls ─────────────────────────────────────────────────────────

@Composable
private fun <T> Picker(
    value: String, options: List<T>, label: (T) -> String, onPick: (T) -> Unit,
    modifier: Modifier = Modifier,
) {
    var open by remember { mutableStateOf(false) }
    Box(modifier) {
        OutlinedButton(onClick = { open = true }, contentPadding = PaddingValues(horizontal = 10.dp),
            modifier = Modifier.fillMaxWidth()) {
            Text("$value  ▾", maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            options.forEach { o ->
                DropdownMenuItem(text = { Text(label(o)) }, onClick = { open = false; onPick(o) })
            }
        }
    }
}

@Composable
private fun SwitchRow(text: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Switch(checked = checked, onCheckedChange = onChange)
        Spacer(Modifier.width(8.dp))
        Text(text, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun CheckRow(text: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Checkbox(checked = checked, onCheckedChange = onChange)
        Text(text)
    }
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

@Composable
private fun ColumnScope.ScaleTab(vm: ExplorerViewModel) {
    val s = vm.state
    SwitchRow("Show scale", s.scaleOn) { on -> vm.update { it.copy(scaleOn = on) } }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Picker(ROOT_CHOICES[s.scaleRoot], ROOT_CHOICES.indices.toList(), { ROOT_CHOICES[it] },
            { r -> vm.update { it.copy(scaleRoot = r, scaleOn = true) } }, Modifier.weight(0.35f))
        Picker(s.family, SCALE_FAMILIES, { it.name },
            { f -> vm.update { it.copy(family = f.name, modeIndex = 0, scaleOn = true) } }, Modifier.weight(0.65f))
    }
    val modes = scaleFamily(s.family).modeNames
    Picker(s.modeName, modes.indices.toList(), { modes[it] },
        { m -> vm.update { it.copy(modeIndex = m, scaleOn = true) } }, Modifier.fillMaxWidth())
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
        FilterChip(selected = !s.showDegrees, onClick = { vm.update { it.copy(showDegrees = false) } },
            label = { Text("Notes") })
        FilterChip(selected = s.showDegrees, onClick = { vm.update { it.copy(showDegrees = true) } },
            label = { Text("Degrees") })
        CheckRow("All notes", s.allNotes) { v -> vm.update { it.copy(allNotes = v) } }
    }
    HorizontalDivider()
    DiatonicRow(vm)
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(onClick = vm::addScaleToSheet, enabled = s.scaleOn) { Text("+ Sheet") }
        TextButton(onClick = vm::reset) { Text("Reset") }
        if (s.highlight.isNotEmpty()) {
            TextButton(onClick = { vm.update { it.copy(highlight = emptySet()) } }) { Text("Clear highlights") }
        }
    }
}

@Composable
private fun DiatonicRow(vm: ExplorerViewModel) {
    val s = vm.state
    val chords = diatonicChords(s.scaleRoot, s.scaleIntervals, s.sevenths)
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text("Chords in key", fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.width(8.dp))
        CheckRow("7ths", s.sevenths) { v -> vm.update { it.copy(sevenths = v) } }
    }
    if (chords.isEmpty()) {
        Text("Available for 7-note scales", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        return
    }
    val names = spellScale(s.scaleRoot, s.scaleIntervals)
    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        chords.forEachIndexed { i, dc ->
            val type = dc.type
            FilledTonalButton(
                onClick = { if (type != null) vm.setChord(dc.rootPc, type.name) },
                enabled = type != null,
                contentPadding = PaddingValues(horizontal = 10.dp),
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(dc.numeral, fontSize = 11.sp)
                    Text(names[i] + (type?.symbol ?: "?"), fontWeight = FontWeight.Bold)
                }
            }
        }
    }
    OutlinedButton(onClick = vm::addDiatonicToSheet) { Text("+ All chords in key to sheet") }
}

@Composable
private fun ColumnScope.ChordTab(vm: ExplorerViewModel, actions: PlatformActions) {
    val s = vm.state
    SwitchRow("Show chord", s.chordOn) { on -> vm.update { it.copy(chordOn = on) } }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Picker(ROOT_CHOICES[s.chordRoot], ROOT_CHOICES.indices.toList(), { ROOT_CHOICES[it] },
            { r -> vm.setChord(r, s.chordTypeName) }, Modifier.weight(0.35f))
        Picker(s.chordTypeName, CHORD_TYPES, { if (it.symbol.isEmpty()) it.name else "${it.name}  (${it.symbol})" },
            { t -> vm.setChord(s.chordRoot, t.name) }, Modifier.weight(0.65f))
    }
    val v = vm.currentVoicing
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        FilledTonalButton(onClick = { vm.stepVoicing(-1) }, enabled = vm.voicings.size > 1) { Text("◀") }
        Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
            val title = if (s.chordOn) chordTitle(s) else "—"
            Text(title, fontWeight = FontWeight.Bold, fontSize = 18.sp)
            Text(
                when {
                    !s.chordOn -> "Chord hidden"
                    vm.searching -> "Searching…"
                    v == null -> "No playable voicing"
                    else -> "${v.shape()}   (${vm.voicingIndex + 1}/${vm.voicings.size})"
                },
                fontFamily = FontFamily.Monospace,
            )
        }
        FilledTonalButton(onClick = { vm.stepVoicing(1) }, enabled = vm.voicings.size > 1) { Text("▶") }
    }
    CheckRow("All chord tones", s.allChordTones) { c -> vm.update { it.copy(allChordTones = c) } }
    CheckRow("Root in bass", s.rootInBass) { c -> vm.update(pickBest = true) { it.copy(rootInBass = c) } }
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("Max stretch")
        (3..6).forEach { n ->
            FilterChip(selected = s.maxSpan == n, onClick = { vm.update(pickBest = true) { it.copy(maxSpan = n) } },
                label = { Text("$n") })
        }
    }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(onClick = vm::addChordToSheet, enabled = v != null) { Text("+ Sheet") }
        OutlinedButton(onClick = {
            if (v != null) {
                actions.copyText("Chord tab", voicingTab(s, v))
                vm.message = "Copied ${chordTitle(s)} (${v.shape()}) as tab"
            }
        }, enabled = v != null) { Text("Copy tab") }
    }
}

@Composable
private fun ColumnScope.TuningTab(vm: ExplorerViewModel) {
    val s = vm.state
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Strings", fontWeight = FontWeight.SemiBold)
        FilledTonalButton(onClick = { vm.changeStringCount(-1) }) { Text("−") }
        Text("${s.tuning.size}", fontSize = 18.sp, fontWeight = FontWeight.Bold)
        FilledTonalButton(onClick = { vm.changeStringCount(1) }) { Text("+") }
    }
    Text("Low string first. Tap ▲ / ▼ to retune by a semitone.", fontSize = 12.sp,
        color = MaterialTheme.colorScheme.onSurfaceVariant)
    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        for (i in s.tuning.indices.reversed()) {
            Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.widthIn(min = 52.dp)) {
                Text("${i + 1}", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                TextButton(onClick = { vm.shiftString(i, 1) }, modifier = Modifier.size(48.dp, 36.dp),
                    contentPadding = PaddingValues(0.dp)) { Text("▲") }
                Text(midiToName(s.tuning[i]), fontWeight = FontWeight.Bold, fontSize = 16.sp)
                TextButton(onClick = { vm.shiftString(i, -1) }, modifier = Modifier.size(48.dp, 36.dp),
                    contentPadding = PaddingValues(0.dp)) { Text("▼") }
            }
        }
    }
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("All strings")
        FilledTonalButton(onClick = { vm.shiftAll(1) }) { Text("▲") }
        FilledTonalButton(onClick = { vm.shiftAll(-1) }) { Text("▼") }
    }
    Picker("Presets", PRESETS, { it.name }, vm::applyPreset, Modifier.fillMaxWidth())
    SwitchRow("Left-handed", s.lefty) { on -> vm.update { it.copy(lefty = on) } }
}

@Composable
private fun ColumnScope.SheetTab(vm: ExplorerViewModel, actions: PlatformActions) {
    var title by rememberSaveable { mutableStateOf("Scales & Chords") }
    val items = vm.sheet
    if (items.isEmpty()) {
        Text("Your sheet is empty. Use “+ Sheet” on the Scale or Chord tab, or add every chord in a key, " +
            "then share it as a PDF or print it.")
        return
    }
    OutlinedTextField(value = title, onValueChange = { title = it }, label = { Text("Title") },
        singleLine = true, modifier = Modifier.fillMaxWidth())
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(onClick = { actions.shareSheet(items.toList(), title.ifBlank { "Scales & Chords" }, vm.state.lefty) }) {
            Text("Share PDF")
        }
        Button(onClick = { actions.printSheet(items.toList(), title.ifBlank { "Scales & Chords" }, vm.state.lefty) }) {
            Text("Print")
        }
        TextButton(onClick = vm::clearSheet) { Text("Clear") }
    }
    val scales = items.count { it is ScaleSheetItem }
    Text("$scales scale(s), ${items.size - scales} chord(s)", fontSize = 12.sp,
        color = MaterialTheme.colorScheme.onSurfaceVariant)
    items.forEachIndexed { i, item ->
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(item.title, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(
                    if (item is ChordSheetItem) "Chord  ${item.subtitle}" else "Scale",
                    fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            TextButton(onClick = { vm.moveSheetItem(i, -1) }, enabled = i > 0) { Text("▲") }
            TextButton(onClick = { vm.moveSheetItem(i, 1) }, enabled = i < items.size - 1) { Text("▼") }
            TextButton(onClick = { vm.removeSheetItem(i) }) { Text("✕") }
        }
        HorizontalDivider()
    }
    Spacer(Modifier.height(8.dp))
}
