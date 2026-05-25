from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .midi_parser import MidiNote

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

_NOTE_MAP = {
    "C": 0, "C#": 1, "Db": 1,
    "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "Fb": 4, "E#": 5,
    "F": 5, "F#": 6, "Gb": 6,
    "G": 7, "G#": 8, "Ab": 8,
    "A": 9, "A#": 10, "Bb": 10,
    "B": 11, "Cb": 11, "B#": 12,
}

MAX_FRET = 24


def note_name(midi_pitch: int) -> str:
    octave = (midi_pitch // 12) - 1
    return f"{_NOTE_NAMES[midi_pitch % 12]}{octave}"


def parse_note_name(name: str) -> int:
    """Convert a note name like 'E2', 'A#3', 'Bb4' to a MIDI pitch number."""
    name = name.strip()
    if not name:
        raise ValueError("Empty note name")

    # Split letter/accidental from octave number
    i = 0
    while i < len(name) and (name[i].isalpha() or name[i] == "#"):
        i += 1

    note_part = name[:i]
    octave_str = name[i:]

    if note_part not in _NOTE_MAP:
        raise ValueError(f"Unknown note '{note_part}' in '{name}'")

    try:
        octave = int(octave_str)
    except ValueError:
        raise ValueError(f"Bad octave '{octave_str}' in '{name}'")

    semitone = _NOTE_MAP[note_part]
    pitch = (octave + 1) * 12 + semitone
    if not (0 <= pitch <= 127):
        raise ValueError(f"Note '{name}' is outside MIDI range (0–127)")
    return pitch


@dataclass
class PlacedNote:
    string_idx: int   # 0 = highest-pitched string
    fret: int
    grid_pos: int     # 16th-note grid slot
    duration_grid: int


def find_candidates(pitch: int, tuning: List[int]) -> List[Tuple[int, int]]:
    """Return (string_idx, fret) pairs that can produce this pitch."""
    return [
        (i, pitch - open_pitch)
        for i, open_pitch in enumerate(tuning)
        if 0 <= pitch - open_pitch <= MAX_FRET
    ]


def assign_notes(
    notes: List[MidiNote],
    tuning: List[int],
    ticks_per_beat: int,
    beats_per_measure: int = 4,
    grid_divisions: int = 16,
) -> List[PlacedNote]:
    """
    Map MIDI notes to (string, fret) positions using a greedy hand-position
    heuristic: prefer candidates closest to the current hand position, with a
    small bias toward lower frets to avoid unnecessary position shifts.
    Notes that are unplayable on the instrument are silently skipped.
    """
    ticks_per_grid = ticks_per_beat * 4.0 / grid_divisions

    # Group simultaneous notes so we can avoid duplicate string usage per slot
    groups: dict[int, List[MidiNote]] = defaultdict(list)
    for note in notes:
        grid_pos = round(note.start_tick / ticks_per_grid)
        groups[grid_pos].append(note)

    placed: List[PlacedNote] = []
    hand_position: float = 0.0  # fret the index finger is near

    for grid_pos in sorted(groups.keys()):
        used_strings: set[int] = set()

        # Sort notes in this chord by pitch so lower-string (bass) notes
        # anchor the hand position first.
        chord = sorted(groups[grid_pos], key=lambda n: n.pitch)

        for note in chord:
            candidates = find_candidates(note.pitch, tuning)
            if not candidates:
                continue

            # Filter strings already occupied in this grid slot
            available = [(s, f) for s, f in candidates if s not in used_strings]
            if not available:
                available = candidates  # fallback if all strings occupied

            # Score: distance from current hand position + small low-fret bonus
            def score(sf: Tuple[int, int]) -> float:
                _, f = sf
                return abs(f - hand_position) + f * 0.05

            best_string, best_fret = min(available, key=score)
            used_strings.add(best_string)

            duration_grid = max(1, round(note.duration_ticks / ticks_per_grid))
            placed.append(
                PlacedNote(
                    string_idx=best_string,
                    fret=best_fret,
                    grid_pos=grid_pos,
                    duration_grid=duration_grid,
                )
            )

            if best_fret > 0:
                hand_position = hand_position * 0.7 + best_fret * 0.3

    return placed
