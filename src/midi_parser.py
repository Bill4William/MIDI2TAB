from dataclasses import dataclass
from typing import List, Optional, Tuple
import mido


@dataclass
class MidiNote:
    pitch: int
    start_tick: int
    duration_ticks: int
    channel: int
    velocity: int


def parse_midi(
    file_path: str,
    channel_filter: Optional[int] = None,
) -> Tuple[List[MidiNote], int, int, Tuple[int, int], Optional[str]]:
    """
    Parse a MIDI file and return (notes, ticks_per_beat, tempo_us, time_sig, key_sig).
    time_sig is (numerator, denominator) e.g. (4, 4).
    key_sig is a string like 'C', 'Am', 'F#', 'Bbm', or None if not present.
    Percussion channel 9 is always skipped.
    """
    mid = mido.MidiFile(file_path)
    ticks_per_beat: int = mid.ticks_per_beat
    tempo: int = 500000  # default 120 BPM
    time_sig: Tuple[int, int] = (4, 4)
    key_sig: Optional[str] = None

    # Collect all messages with absolute tick times across all tracks
    events: List[Tuple[int, mido.Message]] = []
    for track in mid.tracks:
        abs_tick = 0
        for msg in track:
            abs_tick += msg.time
            events.append((abs_tick, msg))
    events.sort(key=lambda x: x[0])

    # Extract tempo, time signature, and key signature from meta messages
    for _, msg in events:
        if msg.type == "set_tempo":
            tempo = msg.tempo
        elif msg.type == "time_signature":
            time_sig = (msg.numerator, msg.denominator)
        elif msg.type == "key_signature":
            key_sig = msg.key

    # Build Note objects from note_on / note_off pairs
    active: dict = {}  # (channel, pitch) -> (start_tick, velocity)
    notes: List[MidiNote] = []

    for abs_tick, msg in events:
        if not hasattr(msg, "channel"):
            continue
        if msg.channel == 9:  # skip percussion
            continue
        if channel_filter is not None and msg.channel != channel_filter:
            continue

        if msg.type == "note_on" and msg.velocity > 0:
            key = (msg.channel, msg.note)
            active[key] = (abs_tick, msg.velocity)
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            key = (msg.channel, msg.note)
            if key in active:
                start, vel = active.pop(key)
                duration = abs_tick - start
                notes.append(
                    MidiNote(
                        pitch=msg.note,
                        start_tick=start,
                        duration_ticks=max(1, duration),
                        channel=msg.channel,
                        velocity=vel,
                    )
                )

    # Close any notes still open at end of file
    max_tick = events[-1][0] if events else 0
    for (ch, pitch), (start, vel) in active.items():
        notes.append(
            MidiNote(
                pitch=pitch,
                start_tick=start,
                duration_ticks=max(1, max_tick - start),
                channel=ch,
                velocity=vel,
            )
        )

    notes.sort(key=lambda n: n.start_tick)
    return notes, ticks_per_beat, tempo, time_sig, key_sig
