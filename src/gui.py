from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk
from typing import List, Optional

from .midi_parser import parse_midi
from .pdf_exporter import export_pdf
from .tab_formatter import (
    PDF_MAX_CHARS,
    TXT_MAX_CHARS,
    format_tab,
    measures_per_line_for_width,
)
from .tab_generator import PlacedNote, assign_notes, note_name, parse_note_name

# ── Note options for tuning dropdowns ────────────────────────────────────────

_NOTE_NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# C0 through B7 — covers all practical instrument ranges
NOTE_OPTIONS: List[str] = [
    f"{n}{o}" for o in range(0, 8) for n in _NOTE_NAMES_SHARP
]

# ── Key signature options ─────────────────────────────────────────────────────

KEY_OPTIONS: List[str] = [
    "",
    # Major keys
    "C", "G", "D", "A", "E", "B", "F#", "Gb", "Db", "C#", "Ab", "Eb", "Bb", "F",
    # Minor keys
    "Am", "Em", "Bm", "F#m", "C#m", "G#m", "Ebm", "D#m", "Bbm", "Fm", "Cm", "Gm", "Dm",
]

# ── Built-in presets (all open-string notes shifted up one octave) ────────────

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

# ── Resource path helper (works from source and PyInstaller exe) ──────────────

def _resource_path(relative: str) -> str:
    """Return the absolute path to a bundled resource file.

    When running from source, resolves relative to the project root.
    When running as a PyInstaller exe, resolves inside sys._MEIPASS
    (the _internal/ folder that PyInstaller unpacks at runtime).
    """
    base = getattr(
        sys, "_MEIPASS",
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    return os.path.join(base, relative)


# ── User preset persistence ───────────────────────────────────────────────────

def _user_data_dir() -> str:
    """Return a stable, writable app-data folder regardless of how the app is launched.

    Uses the OS-standard location so the path is identical whether the app is
    run from source (python main.py) or as a compiled PyInstaller executable.

      Windows : %APPDATA%\\MIDI2TAB\\
      macOS   : ~/Library/Application Support/MIDI2TAB/
      Linux   : ~/.config/MIDI2TAB/
    """
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

class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MIDI2TAB")
        self.geometry("1150x700")
        self.minsize(820, 500)

        # Set window icon (title bar + taskbar)
        # iconbitmap() is Windows-only; macOS Dock icon comes from the .app bundle
        if sys.platform == "win32":
            try:
                self.iconbitmap(_resource_path("assets/icon.ico"))
            except Exception:
                pass  # don't crash if the icon file is missing

        self._midi_path: Optional[str] = None
        self._tab_text: Optional[str] = None          # screen display (user's mpl)
        self._placed: Optional[List[PlacedNote]] = None   # raw placed notes for reformatting
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

        self._build_menu()
        self._build_ui()

        self.after(0, lambda: self._apply_preset("Guitar – Standard 6-string"))

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        bar = tk.Menu(self)
        self.config(menu=bar)

        file_ = tk.Menu(bar, tearoff=0)
        bar.add_cascade(label="File", menu=file_)
        file_.add_command(label="Open MIDI…\tCtrl+O", command=self._open_midi)
        file_.add_separator()
        file_.add_command(label="Save as Text…\tCtrl+S", command=self._save_text)
        file_.add_command(label="Save as PDF…\tCtrl+Shift+S", command=self._save_pdf)
        file_.add_separator()
        file_.add_command(label="Print…\tCtrl+P", command=self._print_tab)
        file_.add_separator()
        file_.add_command(label="Exit", command=self.quit)

        help_ = tk.Menu(bar, tearoff=0)
        bar.add_cascade(label="Help", menu=help_)
        help_.add_command(label="About MIDI2TAB", command=self._show_about)

        self.bind_all("<Control-o>", lambda _: self._open_midi())
        self.bind_all("<Control-s>", lambda _: self._save_text())
        self.bind_all("<Control-S>", lambda _: self._save_pdf())
        self.bind_all("<Control-p>", lambda _: self._print_tab())

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        left = ttk.Frame(paned, width=280)
        left.pack_propagate(False)
        paned.add(left, weight=0)
        self._build_settings(left)

        right = ttk.Frame(paned)
        paned.add(right, weight=1)
        self._build_display(right)

        self._status = tk.StringVar(value="Ready.  Open a MIDI file to begin.")
        ttk.Label(self, textvariable=self._status, relief=tk.SUNKEN, anchor=tk.W).pack(
            fill=tk.X, side=tk.BOTTOM, padx=2, pady=2
        )

    # ── Settings panel ────────────────────────────────────────────────────────

    def _build_settings(self, parent: ttk.Frame) -> None:
        canvas = tk.Canvas(parent, borderwidth=0, highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        self._inner = ttk.Frame(canvas)
        self._inner.bind(
            "<Configure>",
            lambda _: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self._inner, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def _scroll(ev: tk.Event) -> None:
            canvas.yview_scroll(-1 * (ev.delta // 120), "units")

        canvas.bind("<Enter>", lambda _: canvas.bind_all("<MouseWheel>", _scroll))
        canvas.bind("<Leave>", lambda _: canvas.unbind_all("<MouseWheel>"))

        f = self._inner
        P = {"padx": 8, "pady": 3}

        # ── MIDI File ──
        self._section(f, "MIDI File")
        row = ttk.Frame(f)
        row.pack(fill=tk.X, **P)
        self._file_lbl = ttk.Label(
            row, text="No file selected", foreground="gray",
            wraplength=185, justify=tk.LEFT,
        )
        self._file_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="…", width=3, command=self._open_midi).pack(side=tk.RIGHT)

        ttk.Separator(f, orient="horizontal").pack(fill=tk.X, pady=6)

        # ── Song Info ──
        self._section(f, "Song Info")

        def _info_row(label: str, var: tk.StringVar, widget_fn) -> None:
            r = ttk.Frame(f)
            r.pack(fill=tk.X, **P)
            ttk.Label(r, text=label, width=8, anchor=tk.W).pack(side=tk.LEFT)
            widget_fn(r, var)

        def _entry(parent, var):
            ttk.Entry(parent, textvariable=var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        def _bpm_entry(parent, var):
            ttk.Entry(parent, textvariable=var, width=7).pack(side=tk.LEFT)

        def _key_cb(parent, var):
            ttk.Combobox(
                parent, textvariable=var,
                values=KEY_OPTIONS, state="normal", width=10,
            ).pack(side=tk.LEFT)

        _info_row("Song:", self._song_name_var, _entry)
        _info_row("Artist:", self._artist_var, _entry)
        _info_row("BPM:", self._bpm_var, _bpm_entry)
        _info_row("Key:", self._key_var, _key_cb)

        ttk.Separator(f, orient="horizontal").pack(fill=tk.X, pady=6)

        # ── Preset ──
        self._section(f, "Preset")
        self._preset_var = tk.StringVar(value="Guitar – Standard 6-string")
        self._preset_cb = ttk.Combobox(
            f, textvariable=self._preset_var,
            values=self._preset_list(), state="readonly", width=28,
        )
        self._preset_cb.pack(fill=tk.X, **P)
        self._preset_cb.bind(
            "<<ComboboxSelected>>",
            lambda _: self._apply_preset(self._preset_var.get()),
        )

        btn_row = ttk.Frame(f)
        btn_row.pack(fill=tk.X, padx=8, pady=(0, 3))
        ttk.Button(btn_row, text="Save Preset…", command=self._save_preset).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2)
        )
        self._del_btn = ttk.Button(
            btn_row, text="Delete", command=self._delete_preset,
        )
        self._del_btn.pack(side=tk.LEFT)

        ttk.Separator(f, orient="horizontal").pack(fill=tk.X, pady=6)

        # ── Strings ──
        self._section(f, "Strings")
        sf = ttk.Frame(f)
        sf.pack(fill=tk.X, **P)
        ttk.Label(sf, text="Number of strings:").pack(side=tk.LEFT)
        self._num_strings = tk.IntVar(value=6)
        spin = ttk.Spinbox(
            sf, textvariable=self._num_strings, from_=1, to=12, width=4,
            command=self._on_strings_changed,
        )
        spin.pack(side=tk.RIGHT)
        spin.bind("<Return>", lambda _: self._on_strings_changed())
        spin.bind("<FocusOut>", lambda _: self._on_strings_changed())

        ttk.Separator(f, orient="horizontal").pack(fill=tk.X, pady=6)

        # ── Tuning ──
        self._section(f, "Tuning  (high → low string)")
        self._tuning_frame = ttk.Frame(f)
        self._tuning_frame.pack(fill=tk.X, **P)

        ttk.Separator(f, orient="horizontal").pack(fill=tk.X, pady=6)

        # ── Options ──
        self._section(f, "Options")

        def _opt_row(label: str) -> ttk.Frame:
            r = ttk.Frame(f)
            r.pack(fill=tk.X, **P)
            ttk.Label(r, text=label).pack(side=tk.LEFT)
            return r

        self._beats_var = tk.IntVar(value=4)
        r = _opt_row("Beats per measure:")
        ttk.Spinbox(r, textvariable=self._beats_var, from_=2, to=12, width=4).pack(side=tk.RIGHT)

        self._mpl_var = tk.IntVar(value=4)
        r = _opt_row("Measures per line:")
        ttk.Spinbox(r, textvariable=self._mpl_var, from_=1, to=8, width=4).pack(side=tk.RIGHT)

        self._channel_var = tk.StringVar(value="All")
        r = _opt_row("MIDI channel:")
        ttk.Combobox(
            r, textvariable=self._channel_var,
            values=["All"] + [str(i) for i in range(16)],
            state="readonly", width=5,
        ).pack(side=tk.RIGHT)

        ttk.Separator(f, orient="horizontal").pack(fill=tk.X, pady=6)

        ttk.Button(f, text="Generate Tab", command=self._generate).pack(
            fill=tk.X, padx=8, pady=8, ipady=5
        )

    def _section(self, parent: ttk.Frame, text: str) -> None:
        ttk.Label(parent, text=text, font=("TkDefaultFont", 9, "bold")).pack(
            anchor=tk.W, padx=8, pady=(2, 0)
        )

    # ── Tab display panel ─────────────────────────────────────────────────────

    def _build_display(self, parent: ttk.Frame) -> None:
        tb = ttk.Frame(parent)
        tb.pack(fill=tk.X, pady=(0, 2))
        ttk.Button(tb, text="Save Text", command=self._save_text).pack(side=tk.LEFT, padx=2)
        ttk.Button(tb, text="Save PDF",  command=self._save_pdf ).pack(side=tk.LEFT, padx=2)
        ttk.Button(tb, text="Print",     command=self._print_tab).pack(side=tk.LEFT, padx=2)

        self._text = scrolledtext.ScrolledText(
            parent,
            font=("Courier New", 10),
            wrap=tk.NONE,
            state=tk.DISABLED,
            background="#1e1e1e",
            foreground="#d4d4d4",
            insertbackground="white",
        )
        self._text.pack(fill=tk.BOTH, expand=True)

        hbar = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=self._text.xview)
        hbar.pack(fill=tk.X)
        self._text.configure(xscrollcommand=hbar.set)

    # ── Preset helpers ────────────────────────────────────────────────────────

    def _preset_list(self) -> List[str]:
        """All preset names: built-ins first, then user presets, then Custom."""
        built_in = [k for k in PRESETS if k != "Custom"]
        user = list(self._user_presets.keys())
        return built_in + user + ["Custom"]

    def _all_presets(self) -> dict[str, List[str]]:
        return {**PRESETS, **self._user_presets}

    def _refresh_preset_combobox(self) -> None:
        self._preset_cb.configure(values=self._preset_list())

    def _save_preset(self) -> None:
        name = simpledialog.askstring(
            "Save Preset",
            "Enter a name for this preset:",
            parent=self,
        )
        if not name:
            return
        name = name.strip()
        if not name:
            messagebox.showwarning("Invalid Name", "Preset name cannot be blank.")
            return
        if name in PRESETS:
            messagebox.showwarning(
                "Reserved Name",
                f"'{name}' is a built-in preset and cannot be overwritten.",
            )
            return
        notes = [v.get() for v in self._tuning_vars]
        # Validate all notes before saving
        for i, n in enumerate(notes):
            try:
                parse_note_name(n)
            except ValueError:
                messagebox.showerror(
                    "Invalid Tuning",
                    f"String {i + 1} has an invalid note '{n}'. Fix the tuning first.",
                )
                return
        self._user_presets[name] = notes
        _save_user_presets_file(self._user_presets)
        self._refresh_preset_combobox()
        self._preset_var.set(name)
        self._status.set(f"Preset '{name}' saved.")

    def _delete_preset(self) -> None:
        name = self._preset_var.get()
        if name in PRESETS:
            messagebox.showwarning(
                "Cannot Delete",
                f"'{name}' is a built-in preset and cannot be deleted.",
            )
            return
        if name not in self._user_presets:
            messagebox.showwarning("Not Found", f"'{name}' is not a saved user preset.")
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
        for w in self._tuning_frame.winfo_children():
            w.destroy()

        n = self._num_strings.get()
        existing = [v.get() for v in self._tuning_vars]
        self._tuning_vars = []

        for i in range(n):
            if notes is not None:
                default = notes[i] if i < len(notes) else "E3"
            else:
                default = existing[i] if i < len(existing) else "E3"

            row = ttk.Frame(self._tuning_frame)
            row.pack(fill=tk.X, pady=1)
            ttk.Label(row, text=f"String {i + 1}:", width=10).pack(side=tk.LEFT)
            var = tk.StringVar(value=default)
            cb = ttk.Combobox(
                row, textvariable=var,
                values=NOTE_OPTIONS, state="readonly", width=7,
            )
            cb.pack(side=tk.LEFT)
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
            bpm = round(60_000_000 / tempo_us)
            self._bpm_var.set(str(bpm))
            if key_sig:
                self._key_var.set(key_sig)
        except Exception:
            pass

    def _build_song_info_line(self) -> str:
        parts = []
        name   = self._song_name_var.get().strip()
        artist = self._artist_var.get().strip()
        bpm    = self._bpm_var.get().strip()
        key    = self._key_var.get().strip()
        if name:
            parts.append(name)
        if artist:
            parts.append(artist)
        if bpm:
            parts.append(f"{bpm}bpm")
        if key:
            parts.append(f"Key of {key}")
        return ", ".join(parts)

    def _build_instrument_line(self) -> str:
        preset_name = self._preset_var.get()
        num_str     = self._num_strings.get()
        instrument, tuning_name = self._parse_preset_name(preset_name)
        notes_low_to_high = [
            self._note_letter_only(v.get())
            for v in reversed(self._tuning_vars)
        ]
        notes_str = "".join(notes_low_to_high)
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
        sep = " – "  # " – " (en dash)
        if sep not in preset_name:
            return preset_name, ""
        instrument, rest = preset_name.split(sep, 1)
        rest = re.sub(r"\s+\d+-string$", "", rest)   # "Standard 6-string" → "Standard"
        rest = re.sub(r"^\d+-string$",   "", rest)   # bare "7-string" → ""
        rest = re.sub(r"\s+\(.*?\)$",   "", rest)   # "Standard (GCEA)" → "Standard"
        return instrument, rest.strip()

    # ── Tuning validation ─────────────────────────────────────────────────────

    def _get_tuning(self) -> Optional[List[int]]:
        tuning: List[int] = []
        for i, var in enumerate(self._tuning_vars):
            try:
                tuning.append(parse_note_name(var.get()))
            except ValueError as exc:
                messagebox.showerror(
                    "Invalid Tuning",
                    f"String {i + 1}: '{var.get()}' is not a valid note.\n\n{exc}",
                )
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
            self._file_lbl.config(text=os.path.basename(path), foreground="black")
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
                messagebox.showwarning("No Notes", "No notes found in this file or channel.")
                self._status.set("No notes found.")
                return

            self._status.set("Placing notes on fretboard…")
            self.update()
            beats = self._beats_var.get()
            placed = assign_notes(notes, tuning, tpb, beats)

            if not placed:
                messagebox.showwarning(
                    "Out of Range",
                    "None of the notes could be placed on this instrument.\n"
                    "Check that the tuning covers the MIDI pitch range.",
                )
                self._status.set("No notes could be placed.")
                return

            # Store raw results so saves can reformat to the correct page width
            self._placed = placed
            self._tuning_pitches = tuning
            self._beats_per_measure = beats
            self._song_info = self._build_song_info_line()
            self._instrument_info = self._build_instrument_line()

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

        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to generate tab:\n{exc}")
            self._status.set("Error — see console for details.")

    def _show_tab(self, text: str) -> None:
        self._text.config(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", text)
        self._text.config(state=tk.DISABLED)

    def _reformat_for_width(self, max_chars: int) -> str:
        """Return tab text reformatted so every line fits within max_chars columns."""
        if self._placed is None or self._tuning_pitches is None:
            return self._tab_text or ""
        labels = [note_name(p) for p in self._tuning_pitches]
        label_width = max(len(lbl) for lbl in labels) + 1  # +1 for the "|"
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
            text = self._reformat_for_width(TXT_MAX_CHARS)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
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
            title = (
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

        title = (
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

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About MIDI2TAB",
            "MIDI2TAB\n\n"
            "Converts MIDI files to guitar and bass tablature.\n\n"
            "• Custom string counts and tunings\n"
            "• Save and load your own instrument presets\n"
            "• ASCII display + PDF export\n"
            "• Print directly from the app\n\n"
            "Supported formats: .mid, .midi",
        )
