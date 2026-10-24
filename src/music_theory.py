"""
Music theory engine for the Fretboard Explorer.

Pure logic, no GUI: scales and their modes, chord construction, correctly
spelled note names, scale-degree labels, diatonic harmony, chord-voicing
search for any string count / tuning, and key detection from MIDI notes.

Conventions:
  * Pitch classes are ints 0–11 (C=0).
  * Tunings are lists of MIDI pitches ordered high → low, matching the rest
    of MIDI2TAB (index 0 = highest-pitched string).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# ── Note names & spelling ─────────────────────────────────────────────────────

SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES  = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

# Root picker labels — enharmonic pairs shown together, like most theory tools.
ROOT_CHOICES = ["C", "C#/Db", "D", "D#/Eb", "E", "F",
                "F#/Gb", "G", "G#/Ab", "A", "A#/Bb", "B"]

_LETTERS = ["C", "D", "E", "F", "G", "A", "B"]
_LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_ACC_STR = {-2: "bb", -1: "b", 0: "", 1: "#", 2: "##"}


def pc_from_name(name: str) -> int:
    """'C#', 'Db', 'C#/Db', 'E#', 'Cb' → pitch class."""
    name = name.split("/")[0].strip()
    if not name or name[0].upper() not in _LETTER_PC:
        raise ValueError(f"Unknown note '{name}'")
    pc = _LETTER_PC[name[0].upper()]
    for ch in name[1:]:
        if ch in "#♯":
            pc += 1
        elif ch in "b♭":
            pc -= 1
        else:
            raise ValueError(f"Unknown note '{name}'")
    return pc % 12


def _spell(letter_idx: int, pc: int) -> Tuple[str, int]:
    """Spell pitch class `pc` using letter `_LETTERS[letter_idx]`."""
    letter = _LETTERS[letter_idx % 7]
    diff = (pc - _LETTER_PC[letter]) % 12
    if diff > 6:
        diff -= 12
    return letter + _ACC_STR.get(diff, "?"), diff


def spell_scale(root_pc: int, intervals: Sequence[int],
                prefer_flats: Optional[bool] = None) -> List[str]:
    """
    Return note names for a scale.

    Seven-note scales get one letter per degree (F major → Bb, not A#), with
    the root spelled whichever enharmonic way needs fewer accidentals.
    Other scales fall back to sharps or flats.
    """
    pcs = [(root_pc + i) % 12 for i in intervals]
    if len(intervals) == 7:
        best: Optional[Tuple[int, List[str]]] = None
        for root_letter in range(7):
            root_name, root_acc = _spell(root_letter, root_pc)
            if abs(root_acc) > 1:
                continue
            if prefer_flats is True and root_acc > 0:
                continue
            if prefer_flats is False and root_acc < 0:
                continue
            names, cost = [], 0
            for deg, pc in enumerate(pcs):
                n, acc = _spell(root_letter + deg, pc)
                names.append(n)
                cost += abs(acc) * (1 if abs(acc) < 2 else 4)
            if "?" in "".join(names):
                continue
            if best is None or cost < best[0]:
                best = (cost, names)
        if best is not None:
            return best[1]
    if prefer_flats is None:
        prefer_flats = root_pc in (5, 10, 3, 8, 1)  # F Bb Eb Ab Db
    table = FLAT_NAMES if prefer_flats else SHARP_NAMES
    return [table[pc] for pc in pcs]


def pc_name(pc: int, prefer_flats: bool = False) -> str:
    return (FLAT_NAMES if prefer_flats else SHARP_NAMES)[pc % 12]


def midi_to_name(pitch: int) -> str:
    return f"{SHARP_NAMES[pitch % 12]}{pitch // 12 - 1}"


# ── Scales & modes ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ScaleFamily:
    name: str
    intervals: Tuple[int, ...]
    mode_names: Tuple[str, ...]   # one per rotation that is offered


SCALE_FAMILIES: Dict[str, ScaleFamily] = {f.name: f for f in [
    ScaleFamily("Major (Diatonic)", (0, 2, 4, 5, 7, 9, 11), (
        "Ionian (Major)", "Dorian", "Phrygian", "Lydian",
        "Mixolydian", "Aeolian (Natural Minor)", "Locrian")),
    ScaleFamily("Harmonic Minor", (0, 2, 3, 5, 7, 8, 11), (
        "Harmonic Minor", "Locrian ♮6", "Ionian #5", "Dorian #4",
        "Phrygian Dominant", "Lydian #2", "Ultralocrian")),
    ScaleFamily("Melodic Minor", (0, 2, 3, 5, 7, 9, 11), (
        "Melodic Minor (Jazz)", "Dorian b2", "Lydian Augmented",
        "Lydian Dominant", "Mixolydian b6", "Locrian ♮2", "Altered")),
    ScaleFamily("Harmonic Major", (0, 2, 4, 5, 7, 8, 11), (
        "Harmonic Major", "Dorian b5", "Phrygian b4", "Lydian b3",
        "Mixolydian b2", "Lydian Augmented #2", "Locrian bb7")),
    ScaleFamily("Double Harmonic", (0, 1, 4, 5, 7, 8, 11), (
        "Double Harmonic Major", "Lydian #2 #6", "Ultraphrygian",
        "Hungarian Minor", "Oriental", "Ionian #2 #5", "Locrian bb3 bb7")),
    ScaleFamily("Pentatonic", (0, 2, 4, 7, 9), (
        "Major Pentatonic", "Egyptian (Suspended)", "Man Gong (Blues Minor)",
        "Ritusen (Blues Major)", "Minor Pentatonic")),
    ScaleFamily("Blues", (0, 3, 5, 6, 7, 10), ("Minor Blues",)),
    ScaleFamily("Major Blues", (0, 2, 3, 4, 7, 9), ("Major Blues",)),
    ScaleFamily("Bebop", (0, 2, 4, 5, 7, 9, 10, 11), ("Bebop Dominant",)),
    ScaleFamily("Hirajoshi", (0, 2, 3, 7, 8), ("Hirajoshi",)),
    ScaleFamily("Whole Tone", (0, 2, 4, 6, 8, 10), ("Whole Tone",)),
    ScaleFamily("Diminished", (0, 2, 3, 5, 6, 8, 9, 11), (
        "Whole-Half", "Half-Whole (Dominant)")),
    ScaleFamily("Augmented", (0, 3, 4, 7, 8, 11), (
        "Augmented", "Inverse Augmented")),
    ScaleFamily("Chromatic", tuple(range(12)), ("Chromatic",)),
]}


def mode_intervals(family: str, mode_index: int = 0) -> List[int]:
    """Intervals (from the mode's own root) of rotation `mode_index`."""
    base = SCALE_FAMILIES[family].intervals
    k = mode_index % len(base)
    start = base[k]
    return sorted((i - start) % 12 for i in base[k:] + base[:k])


def find_mode(name: str) -> Optional[Tuple[str, int]]:
    """Locate a mode by (case-insensitive, partial) name → (family, index)."""
    want = name.lower()
    for fam in SCALE_FAMILIES.values():
        for i, m in enumerate(fam.mode_names):
            if m.lower() == want or m.lower().startswith(want + " "):
                return fam.name, i
    return None


# Interval → degree label, used for non-heptatonic scales and chords.
_DEGREE_BY_SEMITONE = ["1", "b2", "2", "b3", "3", "4",
                       "b5", "5", "b6", "6", "b7", "7"]
_MAJOR_STEPS = [0, 2, 4, 5, 7, 9, 11]


def degree_labels(intervals: Sequence[int]) -> List[str]:
    """
    Scale-degree labels relative to the major scale.
    Seven-note scales are labelled positionally (Lydian → #4, not b5).
    """
    if len(intervals) == 7:
        out = []
        for deg, iv in enumerate(intervals):
            diff = iv - _MAJOR_STEPS[deg]
            if diff > 6:
                diff -= 12
            elif diff < -6:
                diff += 12
            out.append(_ACC_STR.get(diff, "?") + str(deg + 1))
        return out
    return [_DEGREE_BY_SEMITONE[iv % 12] for iv in intervals]


# ── Chords ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ChordType:
    symbol: str                    # suffix appended to the root, e.g. "m7"
    name: str
    intervals: Tuple[int, ...]     # semitones above root (may exceed 12)
    optional: Tuple[int, ...] = () # intervals that a voicing may omit
    labels: Tuple[str, ...] = ()   # degree labels matching `intervals`


def _ct(symbol, name, ivs, labels, optional=()):
    return ChordType(symbol, name, tuple(ivs), tuple(optional), tuple(labels))


CHORD_TYPES: Dict[str, ChordType] = {c.name: c for c in [
    _ct("",      "Major",            (0, 4, 7),          ("1", "3", "5")),
    _ct("m",     "Minor",            (0, 3, 7),          ("1", "b3", "5")),
    _ct("dim",   "Diminished",       (0, 3, 6),          ("1", "b3", "b5")),
    _ct("aug",   "Augmented",        (0, 4, 8),          ("1", "3", "#5")),
    _ct("5",     "Power (5)",        (0, 7),             ("1", "5")),
    _ct("sus2",  "Sus2",             (0, 2, 7),          ("1", "2", "5")),
    _ct("sus4",  "Sus4",             (0, 5, 7),          ("1", "4", "5")),
    _ct("6",     "Major 6",          (0, 4, 7, 9),       ("1", "3", "5", "6"), (7,)),
    _ct("m6",    "Minor 6",          (0, 3, 7, 9),       ("1", "b3", "5", "6"), (7,)),
    _ct("7",     "Dominant 7",       (0, 4, 7, 10),      ("1", "3", "5", "b7"), (7,)),
    _ct("maj7",  "Major 7",          (0, 4, 7, 11),      ("1", "3", "5", "7"), (7,)),
    _ct("m7",    "Minor 7",          (0, 3, 7, 10),      ("1", "b3", "5", "b7"), (7,)),
    _ct("mMaj7", "Minor-Major 7",    (0, 3, 7, 11),      ("1", "b3", "5", "7"), (7,)),
    _ct("m7b5",  "Half-Diminished",  (0, 3, 6, 10),      ("1", "b3", "b5", "b7")),
    _ct("dim7",  "Diminished 7",     (0, 3, 6, 9),       ("1", "b3", "b5", "bb7")),
    _ct("maj7#5", "Augmented Major 7", (0, 4, 8, 11),    ("1", "3", "#5", "7")),
    _ct("aug7",  "Augmented 7",      (0, 4, 8, 10),      ("1", "3", "#5", "b7")),
    _ct("7sus4", "Dominant 7 sus4",  (0, 5, 7, 10),      ("1", "4", "5", "b7"), (7,)),
    _ct("add9",  "Add 9",            (0, 4, 7, 14),      ("1", "3", "5", "9"), (7,)),
    _ct("madd9", "Minor add 9",      (0, 3, 7, 14),      ("1", "b3", "5", "9"), (7,)),
    _ct("9",     "Dominant 9",       (0, 4, 7, 10, 14),  ("1", "3", "5", "b7", "9"), (7,)),
    _ct("maj9",  "Major 9",          (0, 4, 7, 11, 14),  ("1", "3", "5", "7", "9"), (7,)),
    _ct("m9",    "Minor 9",          (0, 3, 7, 10, 14),  ("1", "b3", "5", "b7", "9"), (7,)),
    _ct("7b9",   "Dominant 7 b9",    (0, 4, 7, 10, 13),  ("1", "3", "5", "b7", "b9"), (7,)),
    _ct("7#9",   "Dominant 7 #9",    (0, 4, 7, 10, 15),  ("1", "3", "5", "b7", "#9"), (7,)),
    _ct("11",    "Dominant 11",      (0, 4, 7, 10, 14, 17),
        ("1", "3", "5", "b7", "9", "11"), (4, 7, 14)),
    _ct("m11",   "Minor 11",         (0, 3, 7, 10, 14, 17),
        ("1", "b3", "5", "b7", "9", "11"), (7, 14)),
    _ct("13",    "Dominant 13",      (0, 4, 7, 10, 14, 21),
        ("1", "3", "5", "b7", "9", "13"), (7, 14)),
]}


def chord_pcs(root_pc: int, chord: ChordType) -> List[int]:
    return [(root_pc + i) % 12 for i in chord.intervals]


def chord_degree_map(root_pc: int, chord: ChordType) -> Dict[int, str]:
    """pitch class → chord-degree label ('1', 'b3', '5', …)."""
    return {(root_pc + iv) % 12: lbl
            for iv, lbl in zip(chord.intervals, chord.labels)}


# Black-key roots default to the more common spelling (Db, Eb, F#, Ab, Bb).
_DEFAULT_ROOT_NAME = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def default_root_name(pc: int) -> str:
    return _DEFAULT_ROOT_NAME[pc % 12]


def spell_chord(root_pc: int, chord: ChordType,
                root_name: Optional[str] = None) -> Dict[int, str]:
    """pitch class → spelled name, using the degree labels (b3 → a 3rd up)."""
    root_name = root_name or default_root_name(root_pc)
    root_letter = _LETTERS.index(root_name[0].upper())
    out: Dict[int, str] = {}
    for iv, lbl in zip(chord.intervals, chord.labels):
        num = int("".join(ch for ch in lbl if ch.isdigit()))
        pc = (root_pc + iv) % 12
        name, acc = _spell(root_letter + num - 1, pc)
        # Double accidentals are correct on paper but hard to read on a
        # fretboard (E7#9's F## is played and named as G), so simplify them.
        out[pc] = name if abs(acc) <= 1 else default_root_name(pc)
    return out


def chord_name(root_pc: int, chord: ChordType, prefer_flats: bool = False) -> str:
    return pc_name(root_pc, prefer_flats) + chord.symbol


def identify_chord(pcs: Iterable[int], root_pc: int) -> Optional[ChordType]:
    """Exact match of a pitch-class set (with known root) to a chord type."""
    rel = frozenset((p - root_pc) % 12 for p in pcs)
    for c in CHORD_TYPES.values():
        if frozenset(i % 12 for i in c.intervals) == rel:
            return c
    return None


_ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII"]


def diatonic_chords(root_pc: int, intervals: Sequence[int],
                    sevenths: bool = False
                    ) -> List[Tuple[str, int, Optional[ChordType]]]:
    """
    Harmonise a seven-note scale by stacking thirds.
    Returns (roman numeral, chord root pc, chord type or None) per degree.
    """
    if len(intervals) != 7:
        return []
    out = []
    size = 4 if sevenths else 3
    for d in range(7):
        pcs = [(root_pc + intervals[(d + 2 * k) % 7]) % 12 for k in range(size)]
        croot = pcs[0]
        ctype = identify_chord(pcs, croot)
        third = (pcs[1] - croot) % 12
        fifth = (pcs[2] - croot) % 12
        numeral = _ROMAN[d] if third == 4 else _ROMAN[d].lower()
        if fifth == 6:
            numeral += "°" if not sevenths or (pcs[3] - croot) % 12 == 9 else "ø"
        elif fifth == 8:
            numeral += "+"
        # Prefix accidental when the degree is altered vs. the major scale
        diff = intervals[d] - _MAJOR_STEPS[d]
        if diff:
            numeral = ("b" if diff < 0 else "#") * abs(diff) + numeral
        out.append((numeral, croot, ctype))
    return out


# ── Chord voicing search ──────────────────────────────────────────────────────

MUTED = -1


@dataclass(frozen=True)
class Voicing:
    frets: Tuple[int, ...]   # per string, high → low; MUTED = not played
    score: float

    @property
    def position(self) -> int:
        fretted = [f for f in self.frets if f > 0]
        return min(fretted) if fretted else 0

    def shape(self) -> str:
        """Chord-chart string, low → high, e.g. 'x32010'."""
        parts = ["x" if f == MUTED else str(f) for f in reversed(self.frets)]
        sep = "-" if any(f >= 10 for f in self.frets) else ""
        return sep.join(parts)


def find_voicings(tuning: Sequence[int], root_pc: int, chord: ChordType,
                  max_fret: int = 12, max_span: int = 4,
                  root_in_bass: bool = True, max_results: int = 80
                  ) -> List[Voicing]:
    """
    Search playable voicings of `chord` for an arbitrary tuning.

    Rules: every required chord tone sounds; played strings form one block
    (muted strings only below the bass, above the top note, or at most one
    interior gap); fretted notes fit inside `max_span` frets; no more than
    four fingers (a shared lowest fret counts as one barre finger).
    Results are sorted by neck position, then by playability score.
    """
    n = len(tuning)
    if n == 0:
        return []
    tones = {(root_pc + i) % 12 for i in chord.intervals}
    required = {(root_pc + i) % 12 for i in chord.intervals
                if i not in chord.optional}
    # Low → high order makes "bass note" reasoning straightforward.
    order = list(range(n - 1, -1, -1))
    # Guitars and up: at least four sounding strings; basses/ukes: three.
    min_played = min(n, max(len(required), 4 if n >= 6 else 3))

    found: Dict[Tuple[int, ...], float] = {}

    for lo in range(0, max_fret + 1):
        hi = min(max_fret, lo + max_span - 1)
        options: List[List[int]] = []
        for s in order:
            opts = [f for f in ([0] + list(range(max(lo, 1), hi + 1)))
                    if (tuning[s] + f) % 12 in tones]
            options.append(sorted(set(opts)))

        chosen: List[int] = []

        def dfs(k: int, played: int, gaps: int, pending: int) -> None:
            # pending = muted strings since the last played one; they become
            # an interior gap only if another string is played above them.
            if k == n:
                _evaluate(chosen)
                return
            started = played > 0
            if played + (n - k) < min_played:
                return
            for f in options[k]:
                if not started and root_in_bass and \
                        (tuning[order[k]] + f) % 12 != root_pc:
                    continue
                new_gaps = gaps + (pending if started else 0)
                if new_gaps > 1:
                    continue
                chosen.append(f)
                dfs(k + 1, played + 1, new_gaps, 0)
                chosen.pop()
            chosen.append(MUTED)
            dfs(k + 1, played, gaps, pending + 1 if started else 0)
            chosen.pop()

        def _evaluate(low_to_high: List[int]) -> None:
            played = [i for i, f in enumerate(low_to_high) if f != MUTED]
            if len(played) < min_played:
                return
            first, last = played[0], played[-1]
            gaps = sum(1 for i in range(first, last + 1)
                       if low_to_high[i] == MUTED)
            if gaps > 1:
                return
            notes = [(tuning[order[i]] + low_to_high[i]) % 12 for i in played]
            if not required.issubset(notes):
                return
            if root_in_bass and notes[0] != root_pc:
                return
            fretted = [low_to_high[i] for i in played if low_to_high[i] > 0]
            if fretted:
                fmin, fmax = min(fretted), max(fretted)
                if fmax - fmin >= max_span:
                    return
                # Only keep the voicing in the window it "belongs" to.
                if fmin != max(lo, 1) and lo != 0:
                    return
                at_min = fretted.count(fmin)
                fingers = (1 if at_min >= 2 else at_min) + \
                    sum(1 for f in fretted if f != fmin)
                if fingers > 4:
                    return
                if len(fretted) > 4:
                    # Needs a barre at fmin: strings it covers can't ring open.
                    barred = [i for i in played if low_to_high[i] == fmin]
                    if any(low_to_high[i] == 0
                           for i in range(barred[0], barred[-1] + 1)):
                        return
            elif lo != 0:
                return
            high_to_low = tuple(reversed(low_to_high))
            if high_to_low in found:
                return
            span = (max(fretted) - min(fretted)) if fretted else 0
            opens = len(played) - len(fretted)
            # Open strings help in open position but are awkward up the neck.
            open_weight = -0.15 if (not fretted or max(fretted) <= 3) else 0.5
            score = (span * 0.6 + gaps * 2.5
                     - len(played) * 0.4
                     - len(set(notes)) * 0.5
                     + opens * open_weight)
            found[high_to_low] = score

        dfs(0, 0, 0, 0)

    voicings = [Voicing(fr, sc) for fr, sc in found.items()]
    voicings.sort(key=lambda v: (v.position, v.score))
    # Keep the best few per position so the list stays browsable.
    per_pos: Dict[int, int] = {}
    trimmed = []
    for v in voicings:
        c = per_pos.get(v.position, 0)
        if c < 4:
            trimmed.append(v)
            per_pos[v.position] = c + 1
    return trimmed[:max_results]


def best_voicing_index(voicings: Sequence[Voicing]) -> int:
    """Index of the most practical voicing (low on the neck, easy to play)."""
    if not voicings:
        return 0
    return min(range(len(voicings)),
               key=lambda i: voicings[i].score + 0.4 * voicings[i].position)


# ── Key detection (Krumhansl–Schmuckler) ──────────────────────────────────────

_KS_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_KS_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def _pearson(a: Sequence[float], b: Sequence[float]) -> float:
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    return num / (da * db) if da and db else 0.0


def detect_key(weighted_pitches: Iterable[Tuple[int, float]]
               ) -> Optional[Tuple[int, bool, float]]:
    """
    Estimate the key from (midi pitch, weight) pairs, weight typically being
    note duration. Returns (tonic pc, is_minor, correlation) or None.
    """
    hist = [0.0] * 12
    for p, w in weighted_pitches:
        hist[p % 12] += w
    if not any(hist):
        return None
    best = None
    for tonic in range(12):
        rot = hist[tonic:] + hist[:tonic]
        for minor, prof in ((False, _KS_MAJOR), (True, _KS_MINOR)):
            r = _pearson(rot, prof)
            if best is None or r > best[2]:
                best = (tonic, minor, r)
    return best


def parse_key_signature(key: str) -> Optional[Tuple[int, bool]]:
    """'F#m' → (6, True); 'Bb' → (10, False). Accepts 'min'/'minor' too."""
    key = key.strip()
    if not key:
        return None
    minor = False
    low = key.lower()
    for suffix in ("minor", "min", "m"):
        if low.endswith(suffix) and len(key) > len(suffix):
            key, minor = key[: -len(suffix)].strip(), True
            break
    for suffix in (" major", "maj"):
        if key.lower().endswith(suffix):
            key = key[: -len(suffix)].strip()
    try:
        return pc_from_name(key), minor
    except ValueError:
        return None
