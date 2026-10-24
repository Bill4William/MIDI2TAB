# MIDI2TAB

Convert MIDI files to guitar and bass tablature — with a clean desktop GUI, PDF export, and a Windows installer.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

- **Open any `.mid` / `.midi` file** and generate ASCII tablature instantly
- **Custom tunings** — per-string note dropdowns covering C0–B7
- **Configurable string count** — 1 to 12 strings
- **Built-in presets** for common instruments:
  - Guitar: Standard, Drop D, Open G, Open E, DADGAD, 7-string, 8-string
  - Bass: Standard 4-string, Drop D, 5-string, 6-string
  - Ukulele: Standard (GCEA)
- **Save your own presets** — stored locally in `user_presets.json`
- **Song metadata header** — auto-populates BPM and key signature from the MIDI file; you fill in song name and artist
- **Instrument info line** — shows string count, tuning name, and notes low-to-high (e.g. `6 String Guitar | Standard | EADGBE`)
- **Silent measure compression** — empty measures are collapsed to `Silent for N Measures` instead of blank dashes
- **Page-safe output** — tab is automatically reformatted to fit 8.5×11" with 0.5" margins (no cutoff)
- **Export options** — Save as TXT, Save as PDF, or Print directly from the app
- **Fretboard Explorer** (Tools → Fretboard Explorer, `Ctrl+F`) — interactive neck from open to the 12th fret for any string count (1–12) and tuning:
  - Scales and modes: all modes of Major, Harmonic Minor, Melodic Minor, Harmonic Major, Double Harmonic and Pentatonic, plus Blues, Bebop, Whole Tone, Diminished, Augmented and more — spelled correctly for the key
  - Note names or scale degrees, click-to-highlight any note across the neck, left-handed view
  - Chords in key (triads or 7ths), one click to show each
  - Chord voicing finder for any tuning (28 chord types), stepping through shapes up the neck, with optional inversions and max stretch
  - **Print sheets** — collect any mix of scales and chords (or every chord in a key in one click), reorder them, and save/print them together as one PDF with neck diagrams and chord boxes
  - Shares tuning with the main window, sets the scale from the song key or detects the key from the MIDI file, and overlays the generated tab's fret positions

---

## Download

| Platform | Installer |
|----------|-----------|
| Windows  | [MIDI2TAB_Setup_v1.0.0.exe](../../releases/latest) |
| macOS    | [MIDI2TAB_v1.0.0.dmg](../../releases/latest) *(built via GitHub Actions)* |

---

## Running from Source

**Requirements:** Python 3.9+

```bash
# Clone the repo
git clone https://github.com/Bill4William/MIDI2TAB.git
cd MIDI2TAB

# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

---

## Building

### Windows installer

1. Install [Inno Setup 6](https://jrsoftware.org/isinfo.php)
2. Run the build script:
   ```
   build\build.bat
   ```
3. Output: `installer_output\MIDI2TAB_Setup_v1.0.0.exe`

### macOS disk image

No Mac required — every push to `main` automatically builds a `.dmg` via GitHub Actions.

To download it:
1. Go to the [Actions tab](../../actions)
2. Click the latest **Build macOS Installer** run
3. Download the **MIDI2TAB-macOS** artifact

To build locally on a Mac:
```bash
pip3 install -r requirements.txt Pillow pyinstaller
bash build/build_mac.sh
```
Output: `installer_output/MIDI2TAB_v1.0.0.dmg`

---

## Running Tests

```bash
python -m pytest tests/ -v
```

82 tests covering note conversion, fret placement, tab formatting, MIDI parsing, PDF export, the Fretboard Explorer theory engine (modes, spelling, diatonic chords, chord voicings, key detection), and scale/chord sheet export.

---

## Project Structure

```
MIDI2TAB/
├── main.py                  # Entry point
├── requirements.txt
├── src/
│   ├── gui.py               # Main application window (tkinter)
│   ├── fretboard_window.py  # Fretboard Explorer window
│   ├── music_theory.py      # Scales, modes, chords, voicing search, key detection
│   ├── sheet_exporter.py    # Printable scale & chord sheets (reportlab)
│   ├── midi_parser.py       # MIDI file parsing (mido)
│   ├── tab_generator.py     # Note-to-fret placement algorithm
│   ├── tab_formatter.py     # ASCII tab rendering
│   └── pdf_exporter.py      # PDF generation (reportlab)
├── assets/
│   └── create_icon.py       # Generates icon.ico / icon.icns
├── build/
│   ├── MIDI2TAB.spec        # PyInstaller spec (Windows + macOS)
│   ├── build.bat            # Windows build script
│   ├── build_mac.sh         # macOS build script
│   └── installer.iss        # Inno Setup script (Windows installer)
├── tests/
│   ├── test_core.py         # Unit tests
│   ├── test_music_theory.py # Fretboard Explorer theory tests
│   └── test_sheet_exporter.py # Scale/chord sheet PDF tests
└── .github/
    └── workflows/
        └── build-mac.yml    # GitHub Actions macOS build
```
