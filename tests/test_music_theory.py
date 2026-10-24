"""
Tests for the Fretboard Explorer theory engine (src/music_theory.py).
Covers: scale/mode intervals, note spelling, degree labels, chord spelling,
        diatonic harmony, voicing search on several tunings, key detection.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.music_theory import (
    CHORD_TYPES,
    MUTED,
    best_voicing_index,
    SCALE_FAMILIES,
    degree_labels,
    detect_key,
    diatonic_chords,
    find_mode,
    find_voicings,
    mode_intervals,
    parse_key_signature,
    pc_from_name,
    spell_chord,
    spell_scale,
)

GUITAR_6 = [64, 59, 55, 50, 45, 40]   # E4 B3 G3 D3 A2 E2
BASS_4   = [43, 38, 33, 28]            # G2 D2 A1 E1
MAJOR = "Major (Diatonic)"


def _mode(name):
    fam, idx = find_mode(name)
    return mode_intervals(fam, idx)


class TestModes(unittest.TestCase):
    def test_church_modes(self):
        expected = {
            "Ionian (Major)":          [0, 2, 4, 5, 7, 9, 11],
            "Dorian":                  [0, 2, 3, 5, 7, 9, 10],
            "Phrygian":                [0, 1, 3, 5, 7, 8, 10],
            "Lydian":                  [0, 2, 4, 6, 7, 9, 11],
            "Mixolydian":              [0, 2, 4, 5, 7, 9, 10],
            "Aeolian (Natural Minor)": [0, 2, 3, 5, 7, 8, 10],
            "Locrian":                 [0, 1, 3, 5, 6, 8, 10],
        }
        for name, ivs in expected.items():
            self.assertEqual(_mode(name), ivs, name)

    def test_named_modes_of_other_families(self):
        self.assertEqual(_mode("Phrygian Dominant"), [0, 1, 4, 5, 7, 8, 10])
        self.assertEqual(_mode("Lydian Dominant"),   [0, 2, 4, 6, 7, 9, 10])
        self.assertEqual(_mode("Altered"),           [0, 1, 3, 4, 6, 8, 10])
        self.assertEqual(_mode("Hungarian Minor"),   [0, 2, 3, 6, 7, 8, 11])
        self.assertEqual(_mode("Minor Pentatonic"),  [0, 3, 5, 7, 10])
        self.assertEqual(_mode("Half-Whole (Dominant)"),
                         [0, 1, 3, 4, 6, 7, 9, 10])

    def test_every_mode_is_valid(self):
        for fam in SCALE_FAMILIES.values():
            for i in range(len(fam.mode_names)):
                ivs = mode_intervals(fam.name, i)
                self.assertEqual(ivs[0], 0)
                self.assertEqual(len(ivs), len(fam.intervals))
                self.assertEqual(len(set(ivs)), len(ivs))


class TestSpelling(unittest.TestCase):
    def test_major_keys_use_one_letter_per_degree(self):
        self.assertEqual(spell_scale(5, _mode("Ionian (Major)")),
                         ["F", "G", "A", "Bb", "C", "D", "E"])
        self.assertEqual(spell_scale(6, _mode("Ionian (Major)")),
                         ["F#", "G#", "A#", "B", "C#", "D#", "E#"])
        # Black-key root picks the simpler enharmonic (Db, not C#)
        self.assertEqual(spell_scale(1, _mode("Ionian (Major)")),
                         ["Db", "Eb", "F", "Gb", "Ab", "Bb", "C"])

    def test_harmonic_minor_raised_seventh(self):
        self.assertEqual(spell_scale(9, _mode("Harmonic Minor")),
                         ["A", "B", "C", "D", "E", "F", "G#"])

    def test_degree_labels(self):
        self.assertEqual(degree_labels(_mode("Lydian")),
                         ["1", "2", "3", "#4", "5", "6", "7"])
        self.assertEqual(degree_labels(_mode("Dorian")),
                         ["1", "2", "b3", "4", "5", "6", "b7"])
        self.assertEqual(degree_labels(_mode("Minor Pentatonic")),
                         ["1", "b3", "4", "5", "b7"])

    def test_chord_spelling(self):
        self.assertEqual(spell_chord(10, CHORD_TYPES["Minor 7"]),
                         {10: "Bb", 1: "Db", 5: "F", 8: "Ab"})
        self.assertEqual(spell_chord(2, CHORD_TYPES["Major"]),
                         {2: "D", 6: "F#", 9: "A"})
        # Double accidentals are simplified for readability
        self.assertEqual(spell_chord(4, CHORD_TYPES["Dominant 7 #9"])[7], "G")
        self.assertEqual(spell_chord(0, CHORD_TYPES["Diminished 7"])[9], "A")

    def test_pc_from_name(self):
        self.assertEqual(pc_from_name("C#/Db"), 1)
        self.assertEqual(pc_from_name("Bb"), 10)
        self.assertEqual(pc_from_name("Cb"), 11)
        with self.assertRaises(ValueError):
            pc_from_name("H")

    def test_parse_key_signature(self):
        self.assertEqual(parse_key_signature("F#m"), (6, True))
        self.assertEqual(parse_key_signature("Bb"), (10, False))
        self.assertEqual(parse_key_signature("Ebm"), (3, True))
        self.assertIsNone(parse_key_signature(""))


class TestDiatonic(unittest.TestCase):
    def test_c_major_triads(self):
        got = [(r, pc, c.symbol) for r, pc, c in
               diatonic_chords(0, _mode("Ionian (Major)"))]
        self.assertEqual(got, [
            ("I", 0, ""), ("ii", 2, "m"), ("iii", 4, "m"), ("IV", 5, ""),
            ("V", 7, ""), ("vi", 9, "m"), ("vii°", 11, "dim")])

    def test_c_major_sevenths(self):
        got = [c.symbol for _, _, c in
               diatonic_chords(0, _mode("Ionian (Major)"), sevenths=True)]
        self.assertEqual(got, ["maj7", "m7", "m7", "maj7", "7", "m7", "m7b5"])

    def test_harmonic_minor_sevenths(self):
        got = [(r, c.symbol) for r, _, c in
               diatonic_chords(9, _mode("Harmonic Minor"), sevenths=True)]
        self.assertEqual(got, [
            ("i", "mMaj7"), ("iiø", "m7b5"), ("bIII+", "maj7#5"),
            ("iv", "m7"), ("V", "7"), ("bVI", "maj7"), ("vii°", "dim7")])

    def test_non_heptatonic_returns_nothing(self):
        self.assertEqual(diatonic_chords(0, _mode("Minor Pentatonic")), [])


class TestVoicings(unittest.TestCase):
    def _shapes(self, tuning, root, chord, **kw):
        return [v.shape() for v in
                find_voicings(tuning, root, CHORD_TYPES[chord], **kw)]

    def test_open_chords_are_found_first(self):
        self.assertEqual(self._shapes(GUITAR_6, 0, "Major")[0], "x32010")  # C
        self.assertEqual(self._shapes(GUITAR_6, 9, "Minor")[0], "x02210")  # Am
        self.assertEqual(self._shapes(GUITAR_6, 4, "Major")[0], "022100")  # E
        self.assertEqual(self._shapes(GUITAR_6, 2, "Major")[0], "xx0232")  # D
        self.assertEqual(self._shapes(GUITAR_6, 7, "Major")[0], "320003")  # G

    def test_barre_shapes_present(self):
        self.assertIn("133211", self._shapes(GUITAR_6, 5, "Major"))       # F
        self.assertIn("x24432", self._shapes(GUITAR_6, 11, "Minor"))      # Bm

    def test_every_voicing_is_valid(self):
        for tuning in (GUITAR_6, BASS_4, [62, 57, 55, 50, 45, 38]):  # DADGAD
            for name in ("Major", "Minor 7", "Dominant 9", "Diminished 7"):
                chord = CHORD_TYPES[name]
                tones = {(2 + i) % 12 for i in chord.intervals}
                required = {(2 + i) % 12 for i in chord.intervals
                            if i not in chord.optional}
                for v in find_voicings(tuning, 2, chord, max_span=4):
                    played = [(tuning[s] + f) % 12
                              for s, f in enumerate(v.frets) if f != MUTED]
                    self.assertTrue(set(played) <= tones, v.shape())
                    self.assertTrue(required <= set(played), v.shape())
                    fretted = [f for f in v.frets if f > 0]
                    if fretted:
                        self.assertLess(max(fretted) - min(fretted), 4)
                        self.assertLessEqual(max(fretted), 12)
                    # Lowest sounding string is the root
                    bass = next(f for f in reversed(v.frets) if f != MUTED)
                    lowest = max(s for s, f in enumerate(v.frets) if f != MUTED)
                    self.assertEqual((tuning[lowest] + bass) % 12, 2)

    def test_open_string_under_required_barre_is_rejected(self):
        # 103211 would need a fret-1 barre, which mutes the open A
        self.assertNotIn("103211", self._shapes(GUITAR_6, 5, "Major"))

    def test_best_voicing_matches_standard_charts(self):
        cases = {(5, "Major"): "133211", (11, "Minor"): "x24432",
                 (4, "Minor 7"): "020000", (9, "Dominant 7"): "x02020",
                 (0, "Major"): "x32010", (7, "Major"): "320003"}
        for (root, name), shape in cases.items():
            v = find_voicings(GUITAR_6, root, CHORD_TYPES[name])
            self.assertEqual(v[best_voicing_index(v)].shape(), shape, name)
        self.assertEqual(best_voicing_index([]), 0)

    def test_inversions_when_root_not_required_in_bass(self):
        shapes = self._shapes(GUITAR_6, 0, "Major", root_in_bass=False)
        self.assertIn("332010", shapes)   # C/G

    def test_large_string_counts_finish(self):
        twelve = [64, 59, 55, 50, 45, 40, 35, 30, 25, 20, 15, 10]
        self.assertTrue(find_voicings(twelve, 0, CHORD_TYPES["Dominant 7"]))


class TestKeyDetection(unittest.TestCase):
    def test_c_major_scale(self):
        notes = [(p, 1.0) for p in (60, 62, 64, 65, 67, 69, 71, 72)]
        notes += [(60, 4.0), (67, 2.0)]
        tonic, minor, _ = detect_key(notes)
        self.assertEqual((tonic, minor), (0, False))

    def test_a_minor_melody(self):
        melody = [69, 72, 76, 74, 72, 71, 69, 67, 69, 64, 65, 67, 69]
        tonic, minor, _ = detect_key([(p, 1.0) for p in melody] + [(57, 4.0)])
        self.assertEqual((tonic, minor), (9, True))

    def test_empty(self):
        self.assertIsNone(detect_key([]))


if __name__ == "__main__":
    unittest.main()
