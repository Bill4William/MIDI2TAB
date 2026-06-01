from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from typing import List, Optional

import customtkinter as ctk

from .midi_parser import parse_midi
from .pdf_exporter import export_pdf
from .tab_formatter import (
    PDF_MAX_CHARS,
    TXT_MAX_CHARS,
    format_tab,
    measures_per_line_for_width,
)
from .tab_generator import PlacedNote, assign_notes, note_name, parse_note_name

# ── Appearance — matches AlocasiaTrack exactly ────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# ── Note options for tuning dropdowns ─────────────────────────────────────────
_NOTE_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
NOTE_OPTIONS: List[str] = [f"{n}{o}" for o in range(0, 8) for n in _NOTE_NAMES_SHARP]

# ── Key signature options ─────────────────────────────────────────────────────
KEY_OPTIONS: List[str] = [
    "",
    "C", "G", "D", "A", "E", "B", "F#", "Gb", "Db", "C#", "Ab", "Eb", "Bb", "F",
    "Am", "Em", "Bm", "F#m", "C#m", "G#m", "Ebm", "D#m", "Bbm", "Fm", "Cm", "Gm", "Dm",
]

# ── Built-in presets ──────────────────────────────────────────────────────────
PRESETS: dict[str, List[str]] = {
    "Guitar – Standard 6-string":  ["E5", "B4", "G4", "D4", "A3", "E3"],
    "Guitar – Drop D 6-string":    ["E5", "B4", "G4", "D4", "A3", "D3"],
    "Guitar – Open G 6-string":    ["D5", "B4", "G4", "D4", "G3", "D3"],
    "Guitar – Open E 6-string":    ["E5", "B4", "G#4", "E4", "B3", "E3"],
    "Guitar – DADGAD 6-string":    ["D5", "A4", "G4", "D4", "A3", "D3"],
    "Guitar – 7-string":           ["E5", "B4", "G4", "D4", "A3", "E3", "B2"],
    "Guitar – 8-string":           ["E5", "B4", "G4", "D4", "A3", "E3", "B2", "F#2"],
    "Bass – Standard 4-string":    ["G3", "D3", "A2", "E2"],
    "Bass – Drop D 4-string":      ["G3", "D3", "A2", "D2"],
    "Bass – 5-string":             ["G3", "D3", "A2", "E2", "B1"],
    "Bass – 6-string":             ["C4", "G3", "D3", "A2", "E2", "B1"],
    "Ukulele – Standard (GCEA)":   ["A5", "E5", "C5", "G5"],
    "Custom": [],
}

# ── Resource path (works from source and inside PyInstaller bundle) ───────────

def _resource_path(relative: str) -> str:
    base = getattr(
        sys, "_MEIPASS",
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    return os.path.join(base, relative)

# ── User preset persistence ───────────────────────────────────────────────────

def _user_data_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    app_dir = os.path.join(base, "MIDI2TAB")
    os.makedirs(app_dir, exist_ok=True)
    return app_dir

USER_PRESETS_FILE = os.path.join(_user_data_dir(), "user_presets.json")


def _load_user_presets() -> dict[str, List[str]]:
    if not os.path.exists(USER_PRESETS_FILE):
        return {}
    try:
        with open(USER_PRESETS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, list)}
    except Exception:
        return {}


def _save_user_presets_file(user_presets: dict[str, List[str]]) -> None:
    with open(USER_PRESETS_FILE, "w", encoding="utf-8") as fh:
        json.dump(user_presets, fh, indent=2)


# ── Main application ──────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MIDI2TAB")
        self.geometry("1200x720")
        self.minsize(860, 520)

        # Window icon (Windows only — macOS uses the .app bundle)
        if sys.platform == "win32":
            try:
                self.iconbitmap(_resource_path("assets/icon.ico"))
            except Exception:
                pass

        # ── State ─────────────────────────────────────────────────────────
        self._midi_path: Optional[str] = None
        self._tab_text: Optional[str] = None
        self._placed: Optional[List[PlacedNote]] = None
        self._tuning_pitches: Optional[List[int]] = None
        self._beats_per_measure: int = 4
        self._tuning_vars: List[tk.StringVar] = []
        self._user_presets: dict[str, List[str]] = _load_user_presets()
        self._song_info: Optional[str] = None
        self._instrument_info: Optional[str] = None
        self._song_name_var = tk.StringVar()
        self._artist_var    = tk.StringVar()
        self._bpm_var       = tk.StringVar()
        self._key_var       = tk.StringVar()

        # ── Layout ────────────────────────────────────────────────────────
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_menu()
        self._build_sidebar()
        self._build_content()

        self.after(0, lambda: self._apply_preset("Guitar – Standard 6-string"))

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        bar = tk.Menu(self)
        self.configure(menu=bar)

        file_ = tk.Menu(bar, tearoff=0)
        bar.add_cascade(label="File", menu=file_)
        file_.add_command(label="Open MIDI…\tCtrl+O",    command=self._open_midi)
        file_.add_separator()
        file_.add_command(label="Save as Text…\tCtrl+S", command=self._save_text)
        file_.add_command(label="Save as PDF…\tCtrl+Shift+S", command=self._save_pdf)
        file_.add_separator()
        file_.add_command(label="Print…\tCtrl+P",        command=self._print_tab)
        file_.add_separator()
        file_.add_command(label="Exit",                   command=self.quit)

        help_ = tk.Menu(bar, tearoff=0)
        bar.add_cascade(label="Help", menu=help_)
        help_.add_command(label="Help / Manual",    command=self._open_manual)
        help_.add_command(label="About MIDI2TAB",   command=self._show_about)

        self.bind_all("<Control-o>", lambda _: self._open_midi())
        self.bind_all("<Control-s>", lambda _: self._save_text())
        self.bind_all("<Control-S>", lambda _: self._save_pdf())
        self.bind_all("<Control-p>", lambda _: self._print_tab())

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=290, corner_radius=0,
                               fg_color=("gray92", "gray14"))
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(3, weight=1)   # scrollable area expands
        sidebar.grid_columnconfigure(0, weight=1)

        # App title
        ctk.CTkLabel(
            sidebar, text="MIDI2TAB",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=("gray20", "white"),
        ).grid(row=0, column=0, padx=20, pady=(22, 2), sticky="w")

        ctk.CTkLabel(
            sidebar, text="MIDI to Tablature",
            font=ctk.CTkFont(size=11),
            text_color=("gray55", "gray55"),
        ).grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")

        ctk.CTkFrame(sidebar, height=1,
                     fg_color=("gray80", "gray30")).grid(
            row=2, column=0, sticky="ew", padx=12, pady=(0, 4))

        # Scrollable settings
        scroll = ctk.CTkScrollableFrame(sidebar, fg_color="transparent",
                                        corner_radius=0)
        scroll.grid(row=3, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        self._build_settings(scroll)

        # Bottom section
        ctk.CTkFrame(sidebar, height=1,
                     fg_color=("gray80", "gray30")).grid(
            row=4, column=0, sticky="ew", padx=12, pady=(4, 4))

        ctk.CTkButton(
            sidebar, text="Generate Tab",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=42, command=self._generate,
        ).grid(row=5, column=0, padx=12, pady=(0, 4), sticky="ew")

        ctk.CTkButton(
            sidebar, text="? Help / Manual", anchor="w",
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            hover_color=("gray80", "gray28"),
            text_color=("gray40", "gray60"),
            corner_radius=8,
            command=self._open_manual,
        ).grid(row=6, column=0, padx=10, pady=(0, 2), sticky="ew")

        ctk.CTkLabel(
            sidebar, text="v1.0.0",
            font=ctk.CTkFont(size=10),
            text_color=("gray60", "gray50"),
        ).grid(row=7, column=0, padx=20, pady=(0, 14), sticky="w")

    def _build_settings(self, f: ctk.CTkScrollableFrame) -> None:

        def _section(text: str) -> None:
            ctk.CTkLabel(
                f, text=text,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=("gray30", "gray70"),
                anchor="w",
            ).pack(fill="x", padx=14, pady=(12, 1))
            ctk.CTkFrame(f, height=1,
                         fg_color=("gray80", "gray30")).pack(
                fill="x", padx=12, pady=(0, 6))

        # ── MIDI File ──────────────────────────────────────────────────────
        _section("MIDI File")
        file_row = ctk.CTkFrame(f, fg_color="transparent")
        file_row.pack(fill="x", padx=12, pady=(0, 4))
        self._file_lbl = ctk.CTkLabel(
            file_row,
            text="No file selected",
            text_color=("gray55", "gray55"),
            anchor="w",
            wraplength=200,
            font=ctk.CTkFont(size=11),
        )
        self._file_lbl.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            file_row, text="…", width=34, height=28,
            font=ctk.CTkFont(size=13),
            command=self._open_midi,
        ).pack(side="right")

        # ── Song Info ──────────────────────────────────────────────────────
        _section("Song Info")
        song_frame = ctk.CTkFrame(f, fg_color="transparent")
        song_frame.pack(fill="x", padx=12, pady=(0, 4))

        def _info_row(parent, label, var, width=160, combo=False, values=None):
            fr = ctk.CTkFrame(parent, fg_color="transparent")
            fr.pack(fill="x", pady=1)
            ctk.CTkLabel(fr, text=label, width=56, anchor="w",
                         font=ctk.CTkFont(size=11)).pack(side="left")
            if combo:
                ctk.CTkComboBox(fr, variable=var, values=values or [],
                                width=width, state="normal",
                                font=ctk.CTkFont(size=11)).pack(side="left")
            else:
                ctk.CTkEntry(fr, textvariable=var, width=width, height=26,
                             font=ctk.CTkFont(size=11)).pack(side="left")

        _info_row(song_frame, "Song:",   self._song_name_var)
        _info_row(song_frame, "Artist:", self._artist_var)
        _info_row(song_frame, "BPM:",    self._bpm_var, width=80)
        _info_row(song_frame, "Key:",    self._key_var, width=130,
                  combo=True, values=KEY_OPTIONS)

        # ── Preset ────────────────────────────────────────────────────────
        _section("Preset")
        self._preset_var = tk.StringVar(value="Guitar – Standard 6-string")
        self._preset_cb = ctk.CTkComboBox(
            f,
            variable=self._preset_var,
            values=self._preset_list(),
            state="readonly",
            width=260,
            font=ctk.CTkFont(size=11),
            command=lambda v: self._apply_preset(v),
        )
        self._preset_cb.pack(fill="x", padx=12, pady=(0, 3))

        btn_row = ctk.CTkFrame(f, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(0, 4))
        ctk.CTkButton(
            btn_row, text="Save Preset…", height=28,
            font=ctk.CTkFont(size=11),
            command=self._save_preset,
        ).pack(side="left", fill="x", expand=True, padx=(0, 3))
        ctk.CTkButton(
            btn_row, text="Delete", height=28,
            font=ctk.CTkFont(size=11),
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray30"),
            command=self._delete_preset,
        ).pack(side="left")

        # ── Strings ───────────────────────────────────────────────────────
        _section("Strings")
        self._num_strings = tk.IntVar(value=6)
        self._make_spinner(f, "Number of strings:", self._num_strings,
                           1, 12, callback=self._on_strings_changed)

        # ── Tuning ────────────────────────────────────────────────────────
        _section("Tuning  (high → low)")
        self._tuning_container = ctk.CTkFrame(f, fg_color="transparent")
        self._tuning_container.pack(fill="x", padx=12, pady=(0, 4))

        # ── Options ───────────────────────────────────────────────────────
        _section("Options")
        opts = ctk.CTkFrame(f, fg_color="transparent")
        opts.pack(fill="x", padx=12, pady=(0, 4))

        self._beats_var = tk.IntVar(value=4)
        self._mpl_var   = tk.IntVar(value=4)
        self._channel_var = tk.StringVar(value="All")

        self._make_spinner(opts, "Beats per measure:", self._beats_var, 2, 12, pack=True)
        self._make_spinner(opts, "Measures per line:", self._mpl_var,   1, 8,  pack=True)

        ch_row = ctk.CTkFrame(opts, fg_color="transparent")
        ch_row.pack(fill="x", pady=1)
        ctk.CTkLabel(ch_row, text="MIDI channel:", anchor="w",
                     font=ctk.CTkFont(size=12)).pack(side="left", fill="x", expand=True)
        ctk.CTkComboBox(
            ch_row, variable=self._channel_var,
            values=["All"] + [str(i) for i in range(16)],
            state="readonly", width=80,
            font=ctk.CTkFont(size=11),
        ).pack(side="right")

        # Bottom padding
        ctk.CTkLabel(f, text="").pack()

    def _make_spinner(self, parent, label: str, var: tk.IntVar,
                      min_val: int, max_val: int,
                      callback=None, pack: bool = False) -> ctk.CTkFrame:
        """Label  [−]  [value entry]  [+]  row."""
        fr = ctk.CTkFrame(parent, fg_color="transparent")
        if pack:
            fr.pack(fill="x", pady=1)
        else:
            fr.pack(fill="x", padx=0, pady=1)

        ctk.CTkLabel(fr, text=label, anchor="w",
                     font=ctk.CTkFont(size=12)).pack(side="left", fill="x", expand=True)

        def _step(delta: int):
            v = var.get() + delta
            if min_val <= v <= max_val:
                var.set(v)
                if callback:
                    callback()

        ctk.CTkButton(fr, text="−", width=26, height=24,
                      font=ctk.CTkFont(size=14),
                      command=lambda: _step(-1)).pack(side="left", padx=(4, 1))
        ctk.CTkEntry(fr, textvariable=var, width=40, height=24,
                     justify="center",
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=1)
        ctk.CTkButton(fr, text="+", width=26, height=24,
                      font=ctk.CTkFont(size=14),
                      command=lambda: _step(1)).pack(side="left", padx=(1, 0))
        return fr

    # ── Content area ──────────────────────────────────────────────────────────

    def _build_content(self) -> None:
        content = ctk.CTkFrame(self, corner_radius=0,
                               fg_color=("gray95", "gray13"))
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)

        # Toolbar
        tb = ctk.CTkFrame(content, fg_color="transparent")
        tb.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        for text, cmd in [("Save Text", self._save_text),
                          ("Save PDF",  self._save_pdf),
                          ("Print",     self._print_tab)]:
            ctk.CTkButton(tb, text=text, width=90, height=30,
                          font=ctk.CTkFont(size=12),
                          command=cmd).pack(side="left", padx=(0, 6))

        # Tab display with horizontal scrollbar
        text_frame = ctk.CTkFrame(content, fg_color="transparent")
        text_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=0)
        text_frame.grid_columnconfigure(0, weight=1)
        text_frame.grid_rowconfigure(0, weight=1)

        self._text = ctk.CTkTextbox(
            text_frame,
            font=ctk.CTkFont(family="Courier New", size=10),
            wrap="none",
            state="disabled",
            fg_color=("#f5f5f5", "#1e1e1e"),
            text_color=("#1a1a1a", "#d4d4d4"),
        )
        self._text.grid(row=0, column=0, sticky="nsew")

        hbar = ctk.CTkScrollbar(text_frame, orientation="horizontal",
                                 command=self._text._textbox.xview)
        hbar.grid(row=1, column=0, sticky="ew")
        self._text._textbox.configure(xscrollcommand=hbar.set)

        # Status bar
        self._status = tk.StringVar(value="Ready.  Open a MIDI file to begin.")
        ctk.CTkLabel(
            content, textvariable=self._status,
            anchor="w", font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray55"),
        ).grid(row=2, column=0, sticky="ew", padx=14, pady=(2, 8))

    # ── Preset helpers ────────────────────────────────────────────────────────

    def _preset_list(self) -> List[str]:
        built_in = [k for k in PRESETS if k != "Custom"]
        user = list(self._user_presets.keys())
        return built_in + user + ["Custom"]

    def _all_presets(self) -> dict[str, List[str]]:
        return {**PRESETS, **self._user_presets}

    def _refresh_preset_combobox(self) -> None:
        self._preset_cb.configure(values=self._preset_list())

    def _save_preset(self) -> None:
        name = simpledialog.askstring("Save Preset", "Enter a name for this preset:",
                                      parent=self)
        if not name:
            return
        name = name.strip()
        if not name:
            messagebox.showwarning("Invalid Name", "Preset name cannot be blank.")
            return
        if name in PRESETS:
            messagebox.showwarning("Reserved Name",
                f"'{name}' is a built-in preset and cannot be overwritten.")
            return
        notes = [v.get() for v in self._tuning_vars]
        for i, n in enumerate(notes):
            try:
                parse_note_name(n)
            except ValueError:
                messagebox.showerror("Invalid Tuning",
                    f"String {i + 1} has an invalid note '{n}'. Fix the tuning first.")
                return
        self._user_presets[name] = notes
        _save_user_presets_file(self._user_presets)
        self._refresh_preset_combobox()
        self._preset_var.set(name)
        self._status.set(f"Preset '{name}' saved.")

    def _delete_preset(self) -> None:
        name = self._preset_var.get()
        if name in PRESETS:
            messagebox.showwarning("Cannot Delete",
                f"'{name}' is a built-in preset and cannot be deleted.")
            return
        if name not in self._user_presets:
            messagebox.showwarning("Not Found",
                f"'{name}' is not a saved user preset.")
            return
        if not messagebox.askyesno("Delete Preset", f"Delete preset '{name}'?"):
            return
        del self._user_presets[name]
        _save_user_presets_file(self._user_presets)
        self._refresh_preset_combobox()
        self._preset_var.set("Custom")
        self._status.set(f"Preset '{name}' deleted.")

    # ── Tuning rows ───────────────────────────────────────────────────────────

    def _rebuild_tuning_rows(self, notes: Optional[List[str]] = None) -> None:
        for w in self._tuning_container.winfo_children():
            w.destroy()

        n = self._num_strings.get()
        existing = [v.get() for v in self._tuning_vars]
        self._tuning_vars = []

        for i in range(n):
            default = (notes[i] if notes and i < len(notes)
                       else existing[i] if i < len(existing)
                       else "E3")
            row = ctk.CTkFrame(self._tuning_container, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=f"String {i + 1}:", width=74, anchor="w",
                         font=ctk.CTkFont(size=11)).pack(side="left")
            var = tk.StringVar(value=default)
            ctk.CTkComboBox(
                row, variable=var,
                values=NOTE_OPTIONS,
                state="readonly", width=105,
                font=ctk.CTkFont(size=11),
            ).pack(side="left")
            self._tuning_vars.append(var)

    def _apply_preset(self, preset_name: str) -> None:
        notes = self._all_presets().get(preset_name, [])
        if notes:
            self._num_strings.set(len(notes))
            self._rebuild_tuning_rows(notes)
        else:
            self._rebuild_tuning_rows()

    def _on_strings_changed(self) -> None:
        self._preset_var.set("Custom")
        self._rebuild_tuning_rows()

    # ── Song metadata helpers ─────────────────────────────────────────────────

    def _autofill_from_midi(self, path: str) -> None:
        self._bpm_var.set("")
        self._key_var.set("")
        try:
            _, _, tempo_us, _, key_sig = parse_midi(path)
            self._bpm_var.set(str(round(60_000_000 / tempo_us)))
            if key_sig:
                self._key_var.set(key_sig)
        except Exception:
            pass

    def _build_song_info_line(self) -> str:
        parts = []
        if n := self._song_name_var.get().strip(): parts.append(n)
        if a := self._artist_var.get().strip():    parts.append(a)
        if b := self._bpm_var.get().strip():       parts.append(f"{b}bpm")
        if k := self._key_var.get().strip():       parts.append(f"Key of {k}")
        return ", ".join(parts)

    def _build_instrument_line(self) -> str:
        preset_name = self._preset_var.get()
        num_str     = self._num_strings.get()
        instrument, tuning_name = self._parse_preset_name(preset_name)
        notes_str = "".join(self._note_letter_only(v.get())
                            for v in reversed(self._tuning_vars))
        parts = [f"{num_str} String {instrument}"]
        if tuning_name:
            parts.append(tuning_name)
        parts.append(notes_str)
        return " | ".join(parts)

    @staticmethod
    def _note_letter_only(note_str: str) -> str:
        return note_str.rstrip("0123456789")

    @staticmethod
    def _parse_preset_name(preset_name: str) -> tuple:
        sep = " – "
        if sep not in preset_name:
            return preset_name, ""
        instrument, rest = preset_name.split(sep, 1)
        rest = re.sub(r"\s+\d+-string$", "", rest)
        rest = re.sub(r"^\d+-string$",   "", rest)
        rest = re.sub(r"\s+\(.*?\)$",   "", rest)
        return instrument, rest.strip()

    # ── Tuning validation ─────────────────────────────────────────────────────

    def _get_tuning(self) -> Optional[List[int]]:
        tuning: List[int] = []
        for i, var in enumerate(self._tuning_vars):
            try:
                tuning.append(parse_note_name(var.get()))
            except ValueError as exc:
                messagebox.showerror("Invalid Tuning",
                    f"String {i + 1}: '{var.get()}' is not a valid note.\n\n{exc}")
                return None
        return tuning

    # ── Core actions ──────────────────────────────────────────────────────────

    def _open_midi(self) -> None:
        path = filedialog.askopenfilename(
            title="Open MIDI File",
            filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")],
        )
        if path:
            self._midi_path = path
            self._file_lbl.configure(text=os.path.basename(path),
                                     text_color=("gray20", "gray90"))
            self._status.set(f"Loaded: {os.path.basename(path)}")
            self._autofill_from_midi(path)

    def _generate(self) -> None:
        if not self._midi_path:
            messagebox.showwarning("No File", "Open a MIDI file first.")
            return
        tuning = self._get_tuning()
        if tuning is None:
            return

        channel_str = self._channel_var.get()
        channel_filter = None if channel_str == "All" else int(channel_str)

        try:
            self._status.set("Parsing MIDI…")
            self.update()
            notes, tpb, _tempo, _ts, _ks = parse_midi(self._midi_path, channel_filter)

            if not notes:
                messagebox.showwarning("No Notes",
                    "No notes found in this file or channel.")
                self._status.set("No notes found.")
                return

            self._status.set("Placing notes on fretboard…")
            self.update()
            beats = self._beats_var.get()
            placed = assign_notes(notes, tuning, tpb, beats)

            if not placed:
                messagebox.showwarning("Out of Range",
                    "None of the notes could be placed on this instrument.\n"
                    "Check that the tuning covers the MIDI pitch range.")
                self._status.set("No notes could be placed.")
                return

            self._placed           = placed
            self._tuning_pitches   = tuning
            self._beats_per_measure = beats
            self._song_info        = self._build_song_info_line()
            self._instrument_info  = self._build_instrument_line()

            tab = format_tab(
                placed, len(tuning), tuning,
                beats_per_measure=beats,
                measures_per_line=self._mpl_var.get(),
                song_info=self._song_info,
                instrument_info=self._instrument_info,
            )
            self._tab_text = tab
            self._show_tab(tab)

            skipped = len(notes) - len(placed)
            msg = f"Generated {len(placed)} note(s)."
            if skipped:
                msg += f"  ({skipped} out of range, skipped)"
            self._status.set(msg)

        except Exception as exc:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to generate tab:\n{exc}")
            self._status.set("Error — see console for details.")

    def _show_tab(self, text: str) -> None:
        self._text.configure(state="normal")
        self._text.delete("0.0", "end")
        self._text.insert("0.0", text)
        self._text.configure(state="disabled")

    def _reformat_for_width(self, max_chars: int) -> str:
        if self._placed is None or self._tuning_pitches is None:
            return self._tab_text or ""
        labels = [note_name(p) for p in self._tuning_pitches]
        label_width = max(len(lbl) for lbl in labels) + 1
        mpl = measures_per_line_for_width(
            max_chars,
            beats_per_measure=self._beats_per_measure,
            label_width=label_width,
        )
        return format_tab(
            self._placed,
            len(self._tuning_pitches),
            self._tuning_pitches,
            beats_per_measure=self._beats_per_measure,
            measures_per_line=mpl,
            song_info=self._song_info,
            instrument_info=self._instrument_info,
        )

    def _require_tab(self) -> bool:
        if not self._tab_text:
            messagebox.showwarning("No Tab", "Generate a tab first.")
            return False
        return True

    def _save_text(self) -> None:
        if not self._require_tab():
            return
        path = filedialog.asksaveasfilename(
            title="Save Tab as Text",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="tab.txt",
        )
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self._reformat_for_width(TXT_MAX_CHARS))
            self._status.set(f"Saved: {os.path.basename(path)}")

    def _save_pdf(self) -> None:
        if not self._require_tab():
            return
        path = filedialog.asksaveasfilename(
            title="Save Tab as PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile="tab.pdf",
        )
        if path:
            title = self._song_name_var.get().strip() or (
                os.path.splitext(os.path.basename(self._midi_path))[0]
                if self._midi_path else "Tablature"
            )
            export_pdf(self._reformat_for_width(PDF_MAX_CHARS), path, title=title)
            self._status.set(f"Saved PDF: {os.path.basename(path)}")

    def _print_tab(self) -> None:
        if not self._require_tab():
            return
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        title = self._song_name_var.get().strip() or (
            os.path.splitext(os.path.basename(self._midi_path))[0]
            if self._midi_path else "Tablature"
        )
        export_pdf(self._reformat_for_width(PDF_MAX_CHARS), tmp_path, title=title)
        try:
            os.startfile(tmp_path, "print")
            self._status.set("Sent to printer.")
        except Exception:
            try:
                os.startfile(tmp_path)
                self._status.set("Opened PDF — use File › Print in your PDF viewer.")
            except Exception as exc:
                messagebox.showerror("Print Error", str(exc))

    def _open_manual(self) -> None:
        path = _resource_path("docs/manual.html")
        webbrowser.open(f"file:///{path.replace(os.sep, '/')}")

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About MIDI2TAB",
            "MIDI2TAB  v1.0.0\n\n"
            "Converts MIDI files to guitar and bass tablature.\n\n"
            "• Custom string counts and tunings\n"
            "• Save and load your own instrument presets\n"
            "• ASCII display + PDF export\n"
            "• Print directly from the app\n\n"
            "Supported formats: .mid, .midi",
        )
