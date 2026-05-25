"""
Core logic tests for MIDI2TAB.
Covers: note conversion, fret candidate finding, note assignment,
        tab formatting, MIDI parsing, PDF export, preset validation,
        and a full end-to-end pipeline.
"""

import os
import sys
import tempfile
import unittest

import mido

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.gui import NOTE_OPTIONS, PRESETS
from src.midi_parser import MidiNote, parse_midi
from src.pdf_exporter import export_pdf
from src.tab_formatter import format_tab
from src.tab_generator import (
    PlacedNote,
    assign_notes,
    find_candidates,
    note_name,
    parse_note_name,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

# Standard guitar tuning (high → low), pre-octave-shift values used in tests
# so fret math stays intuitive (e.g. E4=64 open on string 0).
GUITAR_6 = [64, 59, 55, 50, 45, 40]   # E4 B3 G3 D3 A2 E2
BASS_4   = [43, 38, 33, 28]            # G2 D2 A1 E1
TICKS    = 480                          # ticks per beat (quarter note)


def _make_midi(note_events, ticks_per_beat=480, channel=0):
    """
    Build a minimal MIDI file from (pitch, start_tick, duration_ticks) tuples.
    Returns the path to a temporary .mid file.
    """
    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    msgs = []
    for pitch, start, dur in note_events:
        msgs.append((start, "on",  pitch))
        msgs.append((start + dur, "off", pitch))
    msgs.sort(key=lambda x: x[0])

    last = 0
    for tick, kind, pitch in msgs:
        delta = tick - last
        if kind == "on":
            track.append(mido.Message("note_on",  note=pitch, velocity=64,
                                      time=delta, channel=channel))
        else:
            track.append(mido.Message("note_off", note=pitch, velocity=0,
                                      time=delta, channel=channel))
        last = tick

    track.append(mido.MetaMessage("end_of_track", time=0))

    fd, path = tempfile.mkstemp(suffix=".mid")
    os.close(fd)
    mid.save(path)
    return path


# ── 1. Note conversion ────────────────────────────────────────────────────────

class TestNoteConversion(unittest.TestCase):

    # parse_note_name – round-trip MIDI pitch values
    def test_standard_guitar_open_strings(self):
        self.assertEqual(parse_note_name("E2"), 40)
        self.assertEqual(parse_note_name("A2"), 45)
        self.assertEqual(parse_note_name("D3"), 50)
        self.assertEqual(parse_note_name("G3"), 55)
        self.assertEqual(parse_note_name("B3"), 59)
        self.assertEqual(parse_note_name("E4"), 64)

    def test_middle_c(self):
        self.assertEqual(parse_note_name("C4"), 60)

    def test_sharps_and_flats_equivalent(self):
        self.assertEqual(parse_note_name("A#3"), parse_note_name("Bb3"))
        self.assertEqual(parse_note_name("C#4"), parse_note_name("Db4"))
        self.assertEqual(parse_note_name("F#2"), parse_note_name("Gb2"))

    def test_low_bass_notes(self):
        self.assertEqual(parse_note_name("E1"), 28)
        self.assertEqual(parse_note_name("B0"), 23)

    def test_whitespace_stripped(self):
        self.assertEqual(parse_note_name("  E4  "), 64)

    def test_invalid_note_letter_raises(self):
        with self.assertRaises(ValueError):
            parse_note_name("X4")

    def test_empty_string_raises(self):
        with self.assertRaises(ValueError):
            parse_note_name("")

    def test_missing_octave_raises(self):
        with self.assertRaises(ValueError):
            parse_note_name("E")

    # note_name – inverse of parse_note_name
    def test_note_name_round_trip(self):
        for pitch in [28, 40, 45, 50, 55, 59, 60, 64, 71, 76]:
            self.assertEqual(parse_note_name(note_name(pitch)), pitch)

    def test_note_name_specific(self):
        self.assertEqual(note_name(40), "E2")
        self.assertEqual(note_name(60), "C4")
        self.assertEqual(note_name(64), "E4")

    # Octave-shifted presets: confirm default guitar low E is now E3 (52)
    def test_preset_guitar_standard_shifted(self):
        low_e = PRESETS["Guitar – Standard 6-string"][-1]
        self.assertEqual(parse_note_name(low_e), 52,
                         msg=f"Expected E3=52, got {low_e}={parse_note_name(low_e)}")

    def test_preset_bass_5string_low_b_shifted(self):
        low_b = PRESETS["Bass – 5-string"][-1]
        self.assertEqual(parse_note_name(low_b), 35,
                         msg=f"Expected B1=35, got {low_b}={parse_note_name(low_b)}")


# ── 2. Fret candidates ────────────────────────────────────────────────────────

class TestFindCandidates(unittest.TestCase):

    def test_open_string_produces_fret_zero(self):
        # E4 (64) on standard guitar → fret 0 on string 0
        candidates = find_candidates(64, GUITAR_6)
        self.assertIn((0, 0), candidates)

    def test_note_playable_on_multiple_strings(self):
        # E4 (64) = fret 0 on string 0, or fret 5 on string 1 (B3+5=64), etc.
        candidates = find_candidates(64, GUITAR_6)
        strings = [s for s, _ in candidates]
        self.assertGreater(len(strings), 1)

    def test_out_of_range_pitch_returns_empty(self):
        # C0 (12) is below any standard guitar string
        self.assertEqual(find_candidates(12, GUITAR_6), [])

    def test_all_frets_within_max(self):
        for pitch in range(40, 88):
            for _, fret in find_candidates(pitch, GUITAR_6):
                self.assertLessEqual(fret, 24)
                self.assertGreaterEqual(fret, 0)

    def test_bass_open_strings(self):
        # G2=43 on bass string 0 → fret 0
        self.assertIn((0, 0), find_candidates(43, BASS_4))
        # E1=28 on bass string 3 → fret 0
        self.assertIn((3, 0), find_candidates(28, BASS_4))


# ── 3. Note assignment ────────────────────────────────────────────────────────

class TestAssignNotes(unittest.TestCase):

    def _note(self, pitch, start_tick, duration=240):
        return MidiNote(pitch=pitch, start_tick=start_tick,
                        duration_ticks=duration, channel=0, velocity=64)

    def test_single_note_placed(self):
        notes = [self._note(64, 0)]   # E4
        placed = assign_notes(notes, GUITAR_6, TICKS)
        self.assertEqual(len(placed), 1)
        self.assertEqual(placed[0].fret, 0)
        self.assertEqual(placed[0].string_idx, 0)

    def test_out_of_range_note_skipped(self):
        notes = [self._note(12, 0)]   # C0 – unplayable on standard guitar
        placed = assign_notes(notes, GUITAR_6, TICKS)
        self.assertEqual(len(placed), 0)

    def test_sequential_notes_placed_in_order(self):
        # E A D G B e major scale on guitar (open strings = fret 0)
        pitches = [40, 45, 50, 55, 59, 64]
        notes = [self._note(p, i * 480) for i, p in enumerate(pitches)]
        placed = assign_notes(notes, GUITAR_6, TICKS)
        self.assertEqual(len(placed), 6)

    def test_grid_position_quantised(self):
        # Note starting at exactly one beat (480 ticks) → grid pos 4 (4 × 16ths)
        notes = [self._note(64, 480)]
        placed = assign_notes(notes, GUITAR_6, TICKS)
        self.assertEqual(placed[0].grid_pos, 4)

    def test_chord_uses_different_strings(self):
        # Two notes sounding simultaneously – must land on different strings
        notes = [
            self._note(64, 0),   # E4
            self._note(59, 0),   # B3
        ]
        placed = assign_notes(notes, GUITAR_6, TICKS)
        self.assertEqual(len(placed), 2)
        strings_used = {p.string_idx for p in placed}
        self.assertEqual(len(strings_used), 2)

    def test_fret_numbers_non_negative(self):
        pitches = range(40, 83)
        notes = [self._note(p, i * 240) for i, p in enumerate(pitches)]
        placed = assign_notes(notes, GUITAR_6, TICKS)
        for p in placed:
            self.assertGreaterEqual(p.fret, 0)


# ── 4. Tab formatter ──────────────────────────────────────────────────────────

class TestTabFormatter(unittest.TestCase):

    def _simple_tab(self, placed, tuning=None, **kwargs):
        t = tuning or GUITAR_6
        return format_tab(placed, len(t), t, **kwargs)

    def test_empty_returns_placeholder(self):
        result = format_tab([], 6, GUITAR_6)
        self.assertIn("no notes", result.lower())

    def test_output_has_correct_line_count(self):
        placed = [PlacedNote(string_idx=0, fret=0, grid_pos=0, duration_grid=4)]
        tab = self._simple_tab(placed, beats_per_measure=4, measures_per_line=1)
        lines = [l for l in tab.splitlines() if l.strip()]
        self.assertEqual(len(lines), 6)

    def test_all_lines_same_length(self):
        placed = [PlacedNote(string_idx=5, fret=7, grid_pos=0, duration_grid=4)]
        tab = self._simple_tab(placed, beats_per_measure=4, measures_per_line=1)
        lines = [l for l in tab.splitlines() if l.strip()]
        lengths = {len(l) for l in lines}
        self.assertEqual(len(lengths), 1, msg=f"Unequal line lengths: {lengths}")

    def test_fret_appears_on_correct_string(self):
        # Fret 7 on string 5 (low E string of standard guitar)
        placed = [PlacedNote(string_idx=5, fret=7, grid_pos=0, duration_grid=4)]
        tab = self._simple_tab(placed, beats_per_measure=4, measures_per_line=1)
        lines = [l for l in tab.splitlines() if l.strip()]
        # Last line = low E string; should contain "7"
        self.assertIn("7", lines[-1])
        # All other lines should not contain "7"
        for line in lines[:-1]:
            content = line.split("|", 1)[-1]  # strip label
            self.assertNotIn("7", content)

    def test_two_digit_fret_renders(self):
        placed = [PlacedNote(string_idx=0, fret=12, grid_pos=0, duration_grid=4)]
        tab = self._simple_tab(placed, beats_per_measure=4, measures_per_line=1)
        self.assertIn("12", tab)

    def test_bar_lines_present(self):
        placed = [PlacedNote(string_idx=0, fret=0, grid_pos=0, duration_grid=4)]
        tab = self._simple_tab(placed, beats_per_measure=4, measures_per_line=2)
        # Each line should start with label, then "|", then end with "|"
        for line in tab.splitlines():
            if line.strip():
                self.assertIn("|", line)

    def test_multiple_measures_per_line(self):
        # One note per measure across 8 consecutive measures (no silent gaps).
        # grids_per_measure = 4 beats × 4 = 16.
        placed = [
            PlacedNote(string_idx=0, fret=i % 10, grid_pos=16 * i, duration_grid=4)
            for i in range(8)
        ]
        tab2 = self._simple_tab(placed, beats_per_measure=4, measures_per_line=2)
        tab4 = self._simple_tab(placed, beats_per_measure=4, measures_per_line=4)
        # 4-measure systems produce wider lines than 2-measure systems
        len2 = max(len(l) for l in tab2.splitlines() if l.strip())
        len4 = max(len(l) for l in tab4.splitlines() if l.strip())
        self.assertGreater(len4, len2)


# ── 5. MIDI parser ────────────────────────────────────────────────────────────

class TestMidiParser(unittest.TestCase):

    def setUp(self):
        self._tmp_files = []

    def tearDown(self):
        for p in self._tmp_files:
            try:
                os.unlink(p)
            except OSError:
                pass

    def _midi(self, events, **kw):
        path = _make_midi(events, **kw)
        self._tmp_files.append(path)
        return path

    def test_single_note_parsed(self):
        path = self._midi([(64, 0, 480)])
        notes, tpb, _, _, _ = parse_midi(path)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].pitch, 64)

    def test_ticks_per_beat_preserved(self):
        path = self._midi([(64, 0, 480)], ticks_per_beat=960)
        _, tpb, _, _, _ = parse_midi(path)
        self.assertEqual(tpb, 960)

    def test_multiple_notes_sorted_by_start(self):
        path = self._midi([(45, 960, 480), (64, 0, 480), (50, 480, 480)])
        notes, _, _, _, _ = parse_midi(path)
        starts = [n.start_tick for n in notes]
        self.assertEqual(starts, sorted(starts))

    def test_duration_positive(self):
        path = self._midi([(64, 0, 480)])
        notes, _, _, _, _ = parse_midi(path)
        self.assertGreater(notes[0].duration_ticks, 0)

    def test_channel_filter_excludes_other_channels(self):
        # Note on channel 0 and channel 1
        mid = mido.MidiFile(ticks_per_beat=480)
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.Message("note_on",  note=64, velocity=64, time=0,   channel=0))
        track.append(mido.Message("note_off", note=64, velocity=0,  time=480, channel=0))
        track.append(mido.Message("note_on",  note=60, velocity=64, time=0,   channel=1))
        track.append(mido.Message("note_off", note=60, velocity=0,  time=480, channel=1))
        track.append(mido.MetaMessage("end_of_track", time=0))
        fd, path = tempfile.mkstemp(suffix=".mid")
        os.close(fd)
        mid.save(path)
        self._tmp_files.append(path)

        notes_ch0, _, _, _, _ = parse_midi(path, channel_filter=0)
        self.assertTrue(all(n.channel == 0 for n in notes_ch0))
        self.assertTrue(all(n.pitch == 64 for n in notes_ch0))

    def test_percussion_channel_skipped(self):
        path = self._midi([(64, 0, 480)], channel=9)
        notes, _, _, _, _ = parse_midi(path)
        self.assertEqual(len(notes), 0)

    def test_default_time_signature(self):
        path = self._midi([(64, 0, 480)])
        _, _, _, ts, _ = parse_midi(path)
        self.assertEqual(ts, (4, 4))

    def test_custom_time_signature_extracted(self):
        mid = mido.MidiFile(ticks_per_beat=480)
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage("time_signature",
                                      numerator=3, denominator=4,
                                      clocks_per_click=24,
                                      notated_32nd_notes_per_beat=8,
                                      time=0))
        track.append(mido.Message("note_on",  note=64, velocity=64, time=0))
        track.append(mido.Message("note_off", note=64, velocity=0, time=480))
        track.append(mido.MetaMessage("end_of_track", time=0))
        fd, path = tempfile.mkstemp(suffix=".mid")
        os.close(fd)
        mid.save(path)
        self._tmp_files.append(path)

        _, _, _, ts, _ = parse_midi(path)
        self.assertEqual(ts[0], 3)


# ── 6. PDF exporter ───────────────────────────────────────────────────────────

class TestPdfExporter(unittest.TestCase):

    def setUp(self):
        fd, self.pdf_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)

    def tearDown(self):
        try:
            os.unlink(self.pdf_path)
        except OSError:
            pass

    def test_pdf_file_created(self):
        export_pdf("e|--0--|", self.pdf_path, title="Test")
        self.assertTrue(os.path.exists(self.pdf_path))

    def test_pdf_non_empty(self):
        export_pdf("e|--0--|", self.pdf_path, title="Test")
        self.assertGreater(os.path.getsize(self.pdf_path), 0)

    def test_pdf_starts_with_magic_bytes(self):
        export_pdf("e|--0--|", self.pdf_path, title="Test")
        with open(self.pdf_path, "rb") as fh:
            header = fh.read(4)
        self.assertEqual(header, b"%PDF")

    def test_multipage_long_tab(self):
        # A very long tab should still produce a valid PDF (multi-page)
        long_tab = ("e|--0--|  \n" * 200)
        export_pdf(long_tab, self.pdf_path, title="Long Tab")
        self.assertGreater(os.path.getsize(self.pdf_path), 1024)

    def test_wide_tab_fits(self):
        # Lines wider than a typical page – font should scale down, not crash
        wide_line = "E3|" + "0--" * 64 + "|"
        export_pdf(wide_line, self.pdf_path, title="Wide Tab")
        self.assertTrue(os.path.exists(self.pdf_path))


# ── 7. Preset validation ──────────────────────────────────────────────────────

class TestPresets(unittest.TestCase):

    def test_all_preset_notes_parseable(self):
        for preset_name, notes in PRESETS.items():
            for n in notes:
                try:
                    parse_note_name(n)
                except ValueError as exc:
                    self.fail(f"Preset '{preset_name}' note '{n}' is invalid: {exc}")

    def test_all_preset_notes_in_dropdown(self):
        for preset_name, notes in PRESETS.items():
            for n in notes:
                self.assertIn(n, NOTE_OPTIONS,
                              msg=f"Preset '{preset_name}' note '{n}' not in NOTE_OPTIONS")

    def test_guitar_standard_high_to_low_order(self):
        notes = PRESETS["Guitar – Standard 6-string"]
        pitches = [parse_note_name(n) for n in notes]
        self.assertEqual(pitches, sorted(pitches, reverse=True),
                         msg="Guitar standard strings should be ordered high → low pitch")

    def test_bass_standard_high_to_low_order(self):
        notes = PRESETS["Bass – Standard 4-string"]
        pitches = [parse_note_name(n) for n in notes]
        self.assertEqual(pitches, sorted(pitches, reverse=True))

    def test_guitar_standard_shifted_up_from_original(self):
        # Original guitar low E was E2 (40); after shift it should be E3 (52)
        low_e = PRESETS["Guitar – Standard 6-string"][-1]
        self.assertEqual(parse_note_name(low_e), 52)

    def test_bass_5string_low_b_shifted_up(self):
        # Original low B was B0 (23); after shift it should be B1 (35)
        low_b = PRESETS["Bass – 5-string"][-1]
        self.assertEqual(parse_note_name(low_b), 35)

    def test_note_options_covers_all_presets(self):
        all_notes = {n for notes in PRESETS.values() for n in notes}
        for n in all_notes:
            self.assertIn(n, NOTE_OPTIONS)

    def test_note_options_range(self):
        # C0 and B7 should both be present
        self.assertIn("C0", NOTE_OPTIONS)
        self.assertIn("B7", NOTE_OPTIONS)
        self.assertEqual(len(NOTE_OPTIONS), 96)


# ── 8. Full pipeline ──────────────────────────────────────────────────────────

class TestFullPipeline(unittest.TestCase):
    """MIDI file → parse → assign → format → PDF"""

    def setUp(self):
        # Simple pentatonic melody on guitar
        tpb = 480
        self.midi_path = _make_midi([
            (52, 0,    tpb),      # E3  – open low E (shifted tuning)
            (57, tpb,  tpb),      # A3
            (62, tpb*2, tpb),     # D4
            (67, tpb*3, tpb),     # G4
            (71, tpb*4, tpb),     # B4
            (76, tpb*5, tpb),     # E5  – open high e
        ], ticks_per_beat=tpb)
        fd, self.pdf_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        # Shifted guitar tuning from PRESETS
        self.tuning = [parse_note_name(n) for n in PRESETS["Guitar – Standard 6-string"]]

    def tearDown(self):
        for p in (self.midi_path, self.pdf_path):
            try:
                os.unlink(p)
            except OSError:
                pass

    def test_pipeline_produces_tab(self):
        notes, tpb, _, _, _ = parse_midi(self.midi_path)
        self.assertGreater(len(notes), 0)

        placed = assign_notes(notes, self.tuning, tpb, beats_per_measure=4)
        self.assertGreater(len(placed), 0)

        tab = format_tab(placed, len(self.tuning), self.tuning,
                         beats_per_measure=4, measures_per_line=2)
        self.assertIsInstance(tab, str)
        self.assertGreater(len(tab), 0)
        self.assertIn("|", tab)

    def test_all_open_string_notes_placed_at_fret_zero(self):
        notes, tpb, _, _, _ = parse_midi(self.midi_path)
        placed = assign_notes(notes, self.tuning, tpb)
        fret_zero = [p for p in placed if p.fret == 0]
        # All 6 notes are open strings in the shifted tuning
        self.assertEqual(len(fret_zero), 6)

    def test_pipeline_to_pdf(self):
        notes, tpb, _, _, _ = parse_midi(self.midi_path)
        placed = assign_notes(notes, self.tuning, tpb)
        tab = format_tab(placed, len(self.tuning), self.tuning)
        export_pdf(tab, self.pdf_path, title="Pipeline Test")

        with open(self.pdf_path, "rb") as fh:
            self.assertEqual(fh.read(4), b"%PDF")

    def test_no_notes_skipped_for_in_range_pitches(self):
        notes, tpb, _, _, _ = parse_midi(self.midi_path)
        placed = assign_notes(notes, self.tuning, tpb)
        self.assertEqual(len(placed), len(notes),
                         msg="All 6 open-string notes should be playable")


if __name__ == "__main__":
    unittest.main(verbosity=2)
