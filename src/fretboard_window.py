"""
Fretboard Explorer — interactive scale, mode and chord visualiser.

Opens as a separate window from the main MIDI2TAB app and talks to it only
through the callbacks passed to the constructor, so it can share the main
tuning, the song key and the generated tab without depending on App itself.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

from .music_theory import (
    CHORD_TYPES,
    MUTED,
    ROOT_CHOICES,
    SCALE_FAMILIES,
    Voicing,
    chord_degree_map,
    default_root_name,
    degree_labels,
    detect_key,
    diatonic_chords,
    find_mode,
    find_voicings,
    midi_to_name,
    mode_intervals,
    parse_key_signature,
    spell_chord,
    spell_scale,
)
from .tab_generator import parse_note_name

NUM_FRETS = 12
INLAYS = (3, 5, 7, 9)
DOUBLE_INLAY = 12
MIN_STRINGS, MAX_STRINGS = 1, 12
# Same range as the main window's tuning dropdowns (C0–B7).
MIN_PITCH, MAX_PITCH = 12, 107

# Dark / light palettes for the canvas (CTk widgets theme themselves).
_PALETTE = {
    "dark": dict(
        bg="#1e1e1e", board="#3b2d22", fret="#a7a9ac", nut="#e9e3d2",
        string="#cfc6b2", inlay="#7a6550", text="#d4d4d4", faint="#77706a",
        scale="#2fa572", root="#ff6b1a", chord="#f2c94c", chord_root="#ff9f1a",
        chord_text="#1a1a1a", highlight="#4dabf7", tab="#b197fc",
    ),
    "light": dict(
        bg="#f5f5f5", board="#d9b98f", fret="#7d7f82", nut="#fffaf0",
        string="#6f655a", inlay="#c19a6b", text="#1a1a1a", faint="#8a7a66",
        scale="#2a9566", root="#e8590c", chord="#f2c94c", chord_root="#ff9f1a",
        chord_text="#1a1a1a", highlight="#1c7ed6", tab="#7048e8",
    ),
}

TuningGetter = Callable[[], List[str]]
TuningSetter = Callable[[List[str]], None]


class FretboardWindow(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        get_tuning: TuningGetter,
        set_tuning: TuningSetter,
        get_presets: Callable[[], Dict[str, List[str]]],
        get_song_key: Callable[[], str],
        get_midi_notes: Callable[[], Optional[List[Tuple[int, float]]]],
        get_tab: Callable[[], Optional[Tuple[List[int], list]]],
    ) -> None:
        super().__init__(master)
        self.title("MIDI2TAB — Fretboard Explorer")
        self.geometry("1280x800")
        self.minsize(980, 620)

        self._get_main_tuning = get_tuning
        self._set_main_tuning = set_tuning
        self._get_presets = get_presets
        self._get_song_key = get_song_key
        self._get_midi_notes = get_midi_notes
        self._get_tab = get_tab

        # ── State ─────────────────────────────────────────────────────────
        self._tuning: List[int] = self._load_main_tuning() or \
            [64, 59, 55, 50, 45, 40]
        self._highlight: set[int] = set()
        self._voicings: List[Voicing] = []
        self._voicing_idx = 0
        self._voicing_cache: Dict[tuple, List[Voicing]] = {}
        self._tab_counts: Dict[Tuple[int, int], int] = {}
        self._hidden_tab_notes = 0

        self._scale_on   = tk.BooleanVar(value=True)
        self._root_var   = tk.StringVar(value="C")
        self._family_var = tk.StringVar(value="Major (Diatonic)")
        self._mode_var   = tk.StringVar(value="Ionian (Major)")
        self._labels_var = tk.StringVar(value="Notes")
        self._all_notes  = tk.BooleanVar(value=True)

        self._chord_on     = tk.BooleanVar(value=False)
        self._chord_root   = tk.StringVar(value="C")
        self._chord_type   = tk.StringVar(value="Major")
        self._all_tones    = tk.BooleanVar(value=False)
        self._root_in_bass = tk.BooleanVar(value=True)
        self._span_var     = tk.StringVar(value="4")
        self._sevenths     = tk.BooleanVar(value=False)

        self._tab_overlay = tk.BooleanVar(value=False)
        self._lefty       = tk.BooleanVar(value=False)
        self._status      = tk.StringVar()

        # ── Layout ────────────────────────────────────────────────────────
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.configure(fg_color=("gray95", "gray13"))

        self._build_tuning_card()
        self._build_theory_cards()
        self._build_diatonic_bar()
        self._build_canvas()

        ctk.CTkLabel(self, textvariable=self._status, anchor="w",
                     justify="left", font=ctk.CTkFont(size=12),
                     text_color=("gray35", "gray65")).grid(
            row=4, column=0, sticky="ew", padx=16, pady=(2, 10))

        self.bind("<Escape>", lambda _: self._clear_highlight())
        self.bind("<Left>",  lambda _: self._step_voicing(-1))
        self.bind("<Right>", lambda _: self._step_voicing(1))

        self._rebuild_string_boxes()
        self._refresh_all()

        # Keep the window in front of the main app when first opened.
        self.after(150, self._bring_to_front)

    # ── Public hooks for the main app ─────────────────────────────────────────

    def on_tab_generated(self) -> None:
        self._update_tab_overlay()
        self._redraw()

    # ── Helpers: main-app bridge ──────────────────────────────────────────────

    def _bring_to_front(self) -> None:
        self.lift()
        self.focus_force()

    def _load_main_tuning(self) -> Optional[List[int]]:
        try:
            return [parse_note_name(n) for n in self._get_main_tuning()]
        except (ValueError, TypeError):
            return None

    def _pull_tuning(self) -> None:
        t = self._load_main_tuning()
        if not t:
            messagebox.showerror("Invalid Tuning",
                                 "The main window's tuning is not valid.", parent=self)
            return
        self._tuning = t
        self._tuning_changed()
        self._status.set("Loaded tuning from MIDI2TAB.")

    def _push_tuning(self) -> None:
        self._set_main_tuning([midi_to_name(p) for p in self._tuning])
        self._status.set("Sent this tuning to the MIDI2TAB tuning panel.")

    # ── Tuning card ───────────────────────────────────────────────────────────

    def _card(self, parent, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, corner_radius=10,
                            fg_color=("gray88", "gray17"))
        ctk.CTkLabel(card, text=title, anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=("gray20", "gray85")).pack(
            fill="x", padx=12, pady=(8, 2))
        return card

    def _build_tuning_card(self) -> None:
        card = self._card(self, "Strings & Tuning")
        card.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 8))

        # String count
        count = ctk.CTkFrame(row, fg_color="transparent")
        count.pack(side="left", padx=(0, 14))
        ctk.CTkLabel(count, text="Strings", font=ctk.CTkFont(size=11)).pack()
        cnt_row = ctk.CTkFrame(count, fg_color="transparent")
        cnt_row.pack()
        ctk.CTkButton(cnt_row, text="−", width=28, height=28,
                      command=lambda: self._change_string_count(-1)).pack(side="left")
        self._count_lbl = ctk.CTkLabel(cnt_row, text="6", width=30,
                                       font=ctk.CTkFont(size=15, weight="bold"))
        self._count_lbl.pack(side="left")
        ctk.CTkButton(cnt_row, text="+", width=28, height=28,
                      command=lambda: self._change_string_count(1)).pack(side="left")

        # Per-string boxes (rebuilt when the count changes)
        self._strings_frame = ctk.CTkFrame(row, fg_color="transparent")
        self._strings_frame.pack(side="left", padx=4)

        # All strings
        allf = ctk.CTkFrame(row, fg_color="transparent")
        allf.pack(side="left", padx=(10, 14))
        ctk.CTkLabel(allf, text="All strings", font=ctk.CTkFont(size=11)).pack()
        ctk.CTkButton(allf, text="▲", width=40, height=24,
                      command=lambda: self._shift_all(1)).pack(pady=1)
        ctk.CTkButton(allf, text="▼", width=40, height=24,
                      command=lambda: self._shift_all(-1)).pack(pady=1)

        # Presets + sync with main window
        side = ctk.CTkFrame(row, fg_color="transparent")
        side.pack(side="right")
        self._preset_var = tk.StringVar(value="Presets…")
        ctk.CTkComboBox(side, variable=self._preset_var, width=230,
                        values=list(self._get_presets().keys()),
                        state="readonly", font=ctk.CTkFont(size=11),
                        command=self._apply_preset).pack(pady=(0, 4))
        sync = ctk.CTkFrame(side, fg_color="transparent")
        sync.pack()
        ctk.CTkButton(sync, text="⇩ From MIDI2TAB", width=112, height=26,
                      font=ctk.CTkFont(size=11),
                      command=self._pull_tuning).pack(side="left", padx=(0, 4))
        ctk.CTkButton(sync, text="⇧ To MIDI2TAB", width=112, height=26,
                      font=ctk.CTkFont(size=11),
                      command=self._push_tuning).pack(side="left")

    def _rebuild_string_boxes(self) -> None:
        for w in self._strings_frame.winfo_children():
            w.destroy()
        n = len(self._tuning)
        self._count_lbl.configure(text=str(n))
        # Low string on the left, like a chord chart (string numbers n … 1).
        for col, s in enumerate(range(n - 1, -1, -1)):
            box = ctk.CTkFrame(self._strings_frame, fg_color="transparent")
            box.grid(row=0, column=col, padx=2)
            ctk.CTkLabel(box, text=str(s + 1), font=ctk.CTkFont(size=11),
                         text_color=("gray40", "gray60")).pack()
            ctk.CTkButton(box, text="▲", width=42, height=20,
                          font=ctk.CTkFont(size=10),
                          command=lambda s=s: self._shift_string(s, 1)).pack()
            ctk.CTkLabel(box, text=midi_to_name(self._tuning[s]), width=42,
                         height=26, corner_radius=6,
                         fg_color=("white", "gray22"),
                         font=ctk.CTkFont(size=13, weight="bold")).pack(pady=1)
            ctk.CTkButton(box, text="▼", width=42, height=20,
                          font=ctk.CTkFont(size=10),
                          command=lambda s=s: self._shift_string(s, -1)).pack()

    def _change_string_count(self, delta: int) -> None:
        n = len(self._tuning) + delta
        if not (MIN_STRINGS <= n <= MAX_STRINGS):
            return
        if delta > 0:
            # Add a lower string a fourth below (a fifth below a 4th string
            # would also be common, but fourths match guitar & bass practice).
            self._tuning.append(max(MIN_PITCH, self._tuning[-1] - 5))
        else:
            self._tuning.pop()
        self._tuning_changed()

    def _shift_string(self, s: int, delta: int) -> None:
        p = self._tuning[s] + delta
        if MIN_PITCH <= p <= MAX_PITCH:
            self._tuning[s] = p
            self._tuning_changed()

    def _shift_all(self, delta: int) -> None:
        if all(MIN_PITCH <= p + delta <= MAX_PITCH for p in self._tuning):
            self._tuning = [p + delta for p in self._tuning]
            self._tuning_changed()

    def _apply_preset(self, name: str) -> None:
        notes = self._get_presets().get(name)
        if not notes:
            return
        try:
            self._tuning = [parse_note_name(n) for n in notes]
        except ValueError:
            return
        self._tuning_changed()
        self._status.set(f"Tuning preset: {name}")

    def _tuning_changed(self) -> None:
        self._voicing_cache.clear()
        self._rebuild_string_boxes()
        self._refresh_all()

    # ── Scale & chord cards ───────────────────────────────────────────────────

    def _build_theory_cards(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", padx=12, pady=0)
        row.grid_columnconfigure((0, 1), weight=1, uniform="cards")

        # Scale / mode
        sc = self._card(row, "Scale & Mode")
        sc.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        r1 = ctk.CTkFrame(sc, fg_color="transparent")
        r1.pack(fill="x", padx=10, pady=2)
        ctk.CTkSwitch(r1, text="Show", variable=self._scale_on, width=60,
                      command=self._refresh_all).pack(side="left", padx=(0, 8))
        ctk.CTkComboBox(r1, variable=self._root_var, values=ROOT_CHOICES,
                        width=90, state="readonly",
                        command=lambda _: self._refresh_all()).pack(side="left", padx=2)
        ctk.CTkComboBox(r1, variable=self._family_var,
                        values=list(SCALE_FAMILIES.keys()), width=170,
                        state="readonly",
                        command=self._on_family).pack(side="left", padx=2)
        self._mode_cb = ctk.CTkComboBox(r1, variable=self._mode_var, width=200,
                                        values=list(SCALE_FAMILIES[
                                            self._family_var.get()].mode_names),
                                        state="readonly",
                                        command=lambda _: self._refresh_all())
        self._mode_cb.pack(side="left", padx=2)

        r2 = ctk.CTkFrame(sc, fg_color="transparent")
        r2.pack(fill="x", padx=10, pady=(4, 10))
        ctk.CTkSegmentedButton(r2, values=["Notes", "Degrees"],
                               variable=self._labels_var,
                               command=lambda _: self._redraw()).pack(side="left")
        ctk.CTkCheckBox(r2, text="All notes", variable=self._all_notes,
                        width=20, command=self._redraw).pack(side="left", padx=10)
        ctk.CTkButton(r2, text="Song key", width=80, height=26,
                      font=ctk.CTkFont(size=11),
                      command=self._use_song_key).pack(side="left", padx=2)
        ctk.CTkButton(r2, text="Detect from MIDI", width=110, height=26,
                      font=ctk.CTkFont(size=11),
                      command=self._detect_key).pack(side="left", padx=2)
        ctk.CTkButton(r2, text="⟲", width=30, height=26,
                      fg_color=("gray75", "gray25"),
                      hover_color=("gray65", "gray30"),
                      command=self._reset).pack(side="left", padx=2)

        # Chord
        ch = self._card(row, "Chord")
        ch.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        c1 = ctk.CTkFrame(ch, fg_color="transparent")
        c1.pack(fill="x", padx=10, pady=2)
        ctk.CTkSwitch(c1, text="Show", variable=self._chord_on, width=60,
                      command=self._refresh_all).pack(side="left", padx=(0, 8))
        ctk.CTkComboBox(c1, variable=self._chord_root, values=ROOT_CHOICES,
                        width=90, state="readonly",
                        command=lambda _: self._chord_changed()).pack(side="left", padx=2)
        ctk.CTkComboBox(c1, variable=self._chord_type,
                        values=list(CHORD_TYPES.keys()), width=170,
                        state="readonly",
                        command=lambda _: self._chord_changed()).pack(side="left", padx=2)
        ctk.CTkButton(c1, text="◀", width=30, height=26,
                      command=lambda: self._step_voicing(-1)).pack(side="left", padx=(8, 2))
        self._voicing_lbl = ctk.CTkLabel(c1, text="", width=150,
                                         font=ctk.CTkFont(family="Courier New",
                                                          size=12, weight="bold"))
        self._voicing_lbl.pack(side="left")
        ctk.CTkButton(c1, text="▶", width=30, height=26,
                      command=lambda: self._step_voicing(1)).pack(side="left", padx=2)

        c2 = ctk.CTkFrame(ch, fg_color="transparent")
        c2.pack(fill="x", padx=10, pady=(4, 10))
        ctk.CTkCheckBox(c2, text="All chord tones", variable=self._all_tones,
                        width=20, command=self._redraw).pack(side="left")
        ctk.CTkCheckBox(c2, text="Root in bass", variable=self._root_in_bass,
                        width=20, command=self._chord_changed).pack(side="left", padx=10)
        ctk.CTkLabel(c2, text="Max stretch:",
                     font=ctk.CTkFont(size=11)).pack(side="left")
        ctk.CTkComboBox(c2, variable=self._span_var, values=["3", "4", "5", "6"],
                        width=60, state="readonly",
                        command=lambda _: self._chord_changed()).pack(side="left", padx=4)
        ctk.CTkButton(c2, text="Copy tab", width=80, height=26,
                      font=ctk.CTkFont(size=11),
                      command=self._copy_voicing).pack(side="left", padx=6)

    def _build_diatonic_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 0))
        ctk.CTkLabel(bar, text="Chords in key:",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        ctk.CTkCheckBox(bar, text="7ths", variable=self._sevenths, width=20,
                        command=self._refresh_diatonic).pack(side="left", padx=8)
        self._diatonic_frame = ctk.CTkFrame(bar, fg_color="transparent")
        self._diatonic_frame.pack(side="left", fill="x", expand=True)

        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.pack(side="right")
        self._tab_cb = ctk.CTkCheckBox(right, text="Show generated tab",
                                       variable=self._tab_overlay, width=20,
                                       command=self._on_tab_toggle)
        self._tab_cb.pack(side="left", padx=8)
        ctk.CTkCheckBox(right, text="Left-handed", variable=self._lefty,
                        width=20, command=self._redraw).pack(side="left")

    def _build_canvas(self) -> None:
        frame = ctk.CTkFrame(self, corner_radius=10,
                             fg_color=("gray88", "gray17"))
        frame.grid(row=3, column=0, sticky="nsew", padx=12, pady=8)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        self._canvas = tk.Canvas(frame, highlightthickness=0, bd=0)
        self._canvas.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self._canvas.bind("<Configure>", lambda _: self._redraw())
        self._canvas.bind("<Button-1>", self._on_click)
        self._hit: List[Tuple[float, float, float, int]] = []

    # ── Theory state ──────────────────────────────────────────────────────────

    @staticmethod
    def _root_pc(choice: str) -> int:
        return ROOT_CHOICES.index(choice) if choice in ROOT_CHOICES else 0

    def _scale(self) -> Tuple[int, List[int]]:
        fam = SCALE_FAMILIES[self._family_var.get()]
        names = list(fam.mode_names)
        idx = names.index(self._mode_var.get()) if self._mode_var.get() in names else 0
        return self._root_pc(self._root_var.get()), \
            mode_intervals(fam.name, idx)

    def _on_family(self, family: str) -> None:
        names = list(SCALE_FAMILIES[family].mode_names)
        self._mode_cb.configure(values=names)
        self._mode_var.set(names[0])
        self._refresh_all()

    def _set_scale(self, root_pc: int, family: str, mode_idx: int) -> None:
        self._root_var.set(ROOT_CHOICES[root_pc])
        self._family_var.set(family)
        names = list(SCALE_FAMILIES[family].mode_names)
        self._mode_cb.configure(values=names)
        self._mode_var.set(names[mode_idx])
        self._scale_on.set(True)
        self._refresh_all()

    def _set_key(self, tonic: int, minor: bool) -> None:
        fam, idx = find_mode("Aeolian (Natural Minor)" if minor else
                             "Ionian (Major)") or ("Major (Diatonic)", 0)
        self._set_scale(tonic, fam, idx)

    def _use_song_key(self) -> None:
        key = self._get_song_key()
        parsed = parse_key_signature(key or "")
        if not parsed:
            messagebox.showinfo("No Key",
                "No key is set in the main window's Song Info.\n"
                "Load a MIDI file with a key signature, type a key, "
                "or use 'Detect from MIDI'.", parent=self)
            return
        self._set_key(*parsed)
        self._status.set(f"Scale set from song key: {key}")

    def _detect_key(self) -> None:
        notes = self._get_midi_notes()
        if not notes:
            messagebox.showinfo("No MIDI",
                "Open a MIDI file in the main window first.", parent=self)
            return
        result = detect_key(notes)
        if not result:
            return
        tonic, minor, r = result
        self._set_key(tonic, minor)
        name = default_root_name(tonic) + (" minor" if minor else " major")
        self._status.set(f"Detected key: {name}  (confidence r = {r:.2f})")

    def _reset(self) -> None:
        self._highlight.clear()
        self._chord_on.set(False)
        self._set_scale(0, "Major (Diatonic)", 0)

    def _chord(self):
        return self._root_pc(self._chord_root.get()), \
            CHORD_TYPES[self._chord_type.get()]

    def _chord_changed(self) -> None:
        self._chord_on.set(True)
        self._voicing_idx = 0
        self._refresh_all()

    def _compute_voicings(self) -> None:
        if not self._chord_on.get():
            self._voicings = []
            return
        root, ctype = self._chord()
        key = (tuple(self._tuning), root, ctype.name,
               int(self._span_var.get()), self._root_in_bass.get())
        if key not in self._voicing_cache:
            self.configure(cursor="watch")
            self.update_idletasks()
            self._voicing_cache[key] = find_voicings(
                self._tuning, root, ctype, max_fret=NUM_FRETS,
                max_span=int(self._span_var.get()),
                root_in_bass=self._root_in_bass.get())
            self.configure(cursor="")
        self._voicings = self._voicing_cache[key]
        if self._voicing_idx >= len(self._voicings):
            self._voicing_idx = 0

    def _current_voicing(self) -> Optional[Voicing]:
        if self._chord_on.get() and self._voicings:
            return self._voicings[self._voicing_idx]
        return None

    def _step_voicing(self, delta: int) -> None:
        if not self._voicings:
            return
        self._voicing_idx = (self._voicing_idx + delta) % len(self._voicings)
        self._update_voicing_label()
        self._redraw()

    def _update_voicing_label(self) -> None:
        v = self._current_voicing()
        if v is None:
            text = "no voicing" if self._chord_on.get() else ""
        else:
            text = f"{self._voicing_idx + 1}/{len(self._voicings)}  {v.shape()}"
        self._voicing_lbl.configure(text=text)

    def _chord_title(self) -> str:
        root, ctype = self._chord()
        return self._chord_root_name(root) + ctype.symbol

    def _chord_root_name(self, root: int) -> str:
        # Reuse the scale's spelling when the chord root belongs to it.
        if self._scale_on.get():
            sroot, ivs = self._scale()
            names = spell_scale(sroot, ivs)
            pcs = [(sroot + i) % 12 for i in ivs]
            if root in pcs:
                return names[pcs.index(root)]
        return default_root_name(root)

    def _copy_voicing(self) -> None:
        v = self._current_voicing()
        if v is None:
            return
        names = [midi_to_name(p).rstrip("0123456789-") for p in self._tuning]
        width = max(len(n) for n in names)
        lines = [self._chord_title()]
        for name, f in zip(names, v.frets):
            cell = "x" if f == MUTED else str(f)
            lines.append(f"{name:<{width}}|-{cell:-<3}|")
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines) + "\n")
        self._status.set(f"Copied {self._chord_title()} ({v.shape()}) to clipboard.")

    def _refresh_diatonic(self) -> None:
        for w in self._diatonic_frame.winfo_children():
            w.destroy()
        if not self._scale_on.get():
            return
        root, ivs = self._scale()
        chords = diatonic_chords(root, ivs, self._sevenths.get())
        if not chords:
            ctk.CTkLabel(self._diatonic_frame, text="(7-note scales only)",
                         text_color=("gray50", "gray55"),
                         font=ctk.CTkFont(size=11)).pack(side="left", padx=4)
            return
        names = spell_scale(root, ivs)
        for (numeral, croot, ctype), rname in zip(chords, names):
            label = f"{numeral}  {rname}{ctype.symbol if ctype else '?'}"
            ctk.CTkButton(
                self._diatonic_frame, text=label, width=70, height=26,
                font=ctk.CTkFont(size=11),
                fg_color=("gray78", "gray24"), hover_color=("gray68", "gray30"),
                text_color=("gray10", "gray90"),
                state="normal" if ctype else "disabled",
                command=lambda c=croot, t=ctype: self._pick_chord(c, t),
            ).pack(side="left", padx=2)

    def _pick_chord(self, root_pc: int, ctype) -> None:
        self._chord_root.set(ROOT_CHOICES[root_pc])
        self._chord_type.set(ctype.name)
        self._chord_changed()

    # ── Tab overlay ───────────────────────────────────────────────────────────

    def _on_tab_toggle(self) -> None:
        self._update_tab_overlay()
        self._redraw()

    def _update_tab_overlay(self) -> None:
        self._tab_counts = {}
        self._hidden_tab_notes = 0
        if not self._tab_overlay.get():
            return
        data = self._get_tab()
        if not data:
            self._tab_overlay.set(False)
            self._status.set("Generate a tab in the main window first.")
            return
        tab_tuning, placed = data
        same = len(tab_tuning) == len(self._tuning) and all(
            (a - b) % 12 == 0 for a, b in zip(tab_tuning, self._tuning))
        if not same:
            self._tab_overlay.set(False)
            self._status.set("The generated tab used a different tuning — "
                             "click '⇩ From MIDI2TAB' to match it.")
            return
        for pn in placed:
            if pn.fret <= NUM_FRETS:
                key = (pn.string_idx, pn.fret)
                self._tab_counts[key] = self._tab_counts.get(key, 0) + 1
            else:
                self._hidden_tab_notes += 1

    # ── Refresh / status ──────────────────────────────────────────────────────

    def _refresh_all(self) -> None:
        self._compute_voicings()
        self._update_voicing_label()
        self._refresh_diatonic()
        if self._tab_overlay.get():
            self._update_tab_overlay()
        self._redraw()

    def _update_status(self) -> None:
        parts = []
        if self._scale_on.get():
            root, ivs = self._scale()
            names = spell_scale(root, ivs)
            parts.append(f"{names[0]} {self._mode_var.get()}:  "
                         + "  ".join(names)
                         + "     (" + " ".join(degree_labels(ivs)) + ")")
        if self._chord_on.get():
            root, ctype = self._chord()
            sp = spell_chord(root, ctype, self._chord_root_name(root))
            tones = " ".join(sp[(root + i) % 12] for i in ctype.intervals)
            parts.append(f"{self._chord_title()}:  {tones}")
        if self._tab_counts:
            msg = f"Tab overlay: {sum(self._tab_counts.values())} notes"
            if self._hidden_tab_notes:
                msg += f" ({self._hidden_tab_notes} above fret {NUM_FRETS} not shown)"
            parts.append(msg)
        if self._highlight:
            parts.append("Highlighted: " + " ".join(
                default_root_name(p) for p in sorted(self._highlight))
                + "  (Esc clears)")
        if parts:
            self._status.set("     |     ".join(parts))

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _colors(self) -> dict:
        mode = "dark" if ctk.get_appearance_mode().lower() == "dark" else "light"
        return _PALETTE[mode]

    def _redraw(self) -> None:
        c = self._canvas
        c.delete("all")
        self._hit = []
        pal = self._colors()
        c.configure(bg=pal["bg"])
        W, H = c.winfo_width(), c.winfo_height()
        if W < 50 or H < 50:
            return

        n = len(self._tuning)
        left, right, top, bottom = 46, 16, 26, 26
        cols = NUM_FRETS + 1                     # open column + 12 frets
        cw = (W - left - right) / cols
        rh = min(54.0, (H - top - bottom) / max(n, 1))
        board_h = rh * n
        y0 = top + max(0.0, (H - top - bottom - board_h) / 2)
        lefty = self._lefty.get()

        def mx(x: float) -> float:
            """Mirror horizontally for left-handed view."""
            return W - x if lefty else x

        def x_of(col: float) -> float:
            """Left edge of column `col` (0 = open strings)."""
            return mx(left + col * cw)

        def cx(col: int) -> float:
            return (x_of(col) + x_of(col + 1)) / 2

        def cy(s: int) -> float:
            return y0 + rh * (s + 0.5)

        # Fingerboard
        bx1, bx2 = sorted((x_of(1), x_of(cols)))
        c.create_rectangle(bx1, y0, bx2, y0 + board_h, fill=pal["board"], width=0)
        for f in INLAYS + (DOUBLE_INLAY,):
            r = min(cw, rh) * 0.13
            ys = [y0 + board_h / 2] if f != DOUBLE_INLAY else \
                [y0 + board_h * 0.3, y0 + board_h * 0.7]
            if n < 3:
                ys = [y0 + board_h / 2]
            for y in ys:
                c.create_oval(cx(f) - r, y - r, cx(f) + r, y + r,
                              fill=pal["inlay"], width=0)
        # Frets and nut
        for f in range(1, cols + 1):
            x = x_of(f)
            c.create_line(x, y0, x, y0 + board_h,
                          fill=pal["nut"] if f == 1 else pal["fret"],
                          width=6 if f == 1 else 2)
        # Fret numbers
        num_font = ("Helvetica", 10)
        for f in range(1, cols):
            c.create_text(cx(f), y0 - 12, text=str(f), fill=pal["faint"],
                          font=num_font + (("bold",) if f in INLAYS + (12,) else ()))
        c.create_text(cx(0), y0 - 12, text="open", fill=pal["faint"], font=num_font)
        # Strings (thicker toward the bass)
        for s in range(n):
            thick = 1 + 2.5 * s / max(n - 1, 1)
            c.create_line(x_of(0) if not lefty else x_of(cols), cy(s),
                          x_of(cols) if not lefty else x_of(0), cy(s),
                          fill=pal["string"], width=thick)
            c.create_text(mx(left / 2 - 4), cy(s),
                          text=midi_to_name(self._tuning[s]).rstrip("0123456789-"),
                          fill=pal["text"], font=("Helvetica", 13, "bold"))

        # ── Theory layers ─────────────────────────────────────────────────
        scale_on, chord_on = self._scale_on.get(), self._chord_on.get()
        scale_pcs: Dict[int, Tuple[str, str]] = {}
        root_pc = None
        if scale_on:
            root_pc, ivs = self._scale()
            for iv, name, deg in zip(ivs, spell_scale(root_pc, ivs),
                                     degree_labels(ivs)):
                scale_pcs[(root_pc + iv) % 12] = (name, deg)

        chord_root, chord_pcs = None, {}
        voicing = self._current_voicing()
        if chord_on:
            chord_root, ctype = self._chord()
            spelled = spell_chord(chord_root, ctype, self._chord_root_name(chord_root))
            degs = chord_degree_map(chord_root, ctype)
            chord_pcs = {pc: (spelled[pc], degs[pc]) for pc in degs}

        show_degrees = self._labels_var.get() == "Degrees"
        r = min(cw, rh) * 0.40
        font = ("Helvetica", max(8, int(r * 0.62)), "bold")
        small = ("Helvetica", max(7, int(r * 0.55)))

        for s in range(n):
            for f in range(cols):
                pc = (self._tuning[s] + f) % 12
                x, y = cx(f), cy(s)
                self._hit.append((x, y, r, pc))
                in_voicing = voicing is not None and voicing.frets[s] == f
                in_chord = pc in chord_pcs
                in_scale = pc in scale_pcs

                fill = outline = None
                text_color = pal["text"]
                if in_voicing:
                    name, deg = chord_pcs[pc]
                    fill = pal["chord_root"] if pc == chord_root else pal["chord"]
                    text_color = pal["chord_text"]
                elif in_chord and self._all_tones.get():
                    name, deg = chord_pcs[pc]
                    outline = pal["chord"]
                    if in_scale:
                        fill = pal["root"] if pc == root_pc else pal["scale"]
                        text_color = "white"
                elif in_scale:
                    name, deg = scale_pcs[pc]
                    fill = pal["root"] if pc == root_pc else pal["scale"]
                    text_color = "white"
                else:
                    name = chord_pcs.get(pc, scale_pcs.get(pc, (None,)))[0] \
                        or default_root_name(pc)
                    deg = ""

                highlighted = pc in self._highlight
                drawn = fill is not None or outline is not None
                if fill is not None:
                    c.create_oval(x - r, y - r, x + r, y + r, fill=fill,
                                  outline=outline or "", width=3 if outline else 0)
                elif outline is not None:
                    c.create_oval(x - r, y - r, x + r, y + r, fill=pal["bg"],
                                  outline=outline, width=3)
                elif highlighted:
                    c.create_oval(x - r, y - r, x + r, y + r, fill=pal["bg"], width=0)
                if highlighted:
                    rr = r + 4
                    c.create_oval(x - rr, y - rr, x + rr, y + rr,
                                  outline=pal["highlight"], width=3)
                count = self._tab_counts.get((s, f))
                if count:
                    br = max(5.0, r * 0.38)
                    bx, by = x + r * 0.78, y - r * 0.78
                    c.create_oval(bx - br, by - br, bx + br, by + br,
                                  fill=pal["tab"], width=0)
                    c.create_text(bx, by, text=str(min(count, 99)),
                                  fill="white", font=("Helvetica", max(7, int(br))))
                    if not drawn and not highlighted:
                        c.create_oval(x - r, y - r, x + r, y + r,
                                      outline=pal["tab"], width=2)
                        drawn = True

                if drawn or highlighted or self._all_notes.get():
                    label = (deg or name) if show_degrees and deg else name
                    color = text_color if (drawn and (fill or outline)) or highlighted \
                        else pal["faint"]
                    if outline and not fill:
                        color = pal["text"]
                    c.create_text(x, y, text=label, fill=color,
                                  font=font if (drawn or highlighted) else small)

            # Muted-string marker for the current voicing
            if voicing is not None and voicing.frets[s] == MUTED:
                c.create_text(mx(left - 7), cy(s), text="×", fill=pal["root"],
                              font=("Helvetica", max(10, int(r * 0.7)), "bold"))

        self._update_status()

    # ── Interaction ───────────────────────────────────────────────────────────

    def _on_click(self, event) -> None:
        for x, y, r, pc in self._hit:
            if (event.x - x) ** 2 + (event.y - y) ** 2 <= (r + 2) ** 2:
                self._highlight ^= {pc}
                self._redraw()
                return

    def _clear_highlight(self) -> None:
        self._highlight.clear()
        self._redraw()
