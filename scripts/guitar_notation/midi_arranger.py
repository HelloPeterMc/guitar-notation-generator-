"""Zero-dependency Type 1 MIDI full-band arranger for guitar-notation (v0.2).

Generates a 7-track Logic Pro-ready MIDI file from a validated song dict:
  Track 1: Melody Guide (GM 73 Flute / Lead)
  Track 2: Guitar Reference (GM 24 Nylon Guitar - exact voicings & tab)
  Track 3: Keyboards (GM 4 Electric Piano - chord comping)
  Track 4: Electric Bass (GM 33 Finger Bass - root/fifth groove)
  Track 5: Horn Section (GM 61 Brass Section - harmonic stabs)
  Track 6: String Ensemble (GM 48 String Ensemble 1 - sustained pads)
  Track 7: Drums (GM Channel 10 - Kick, Snare, Hi-Hat)
"""
import struct
from fractions import Fraction
from pathlib import Path

from .render import resolve_event
from .validation import parse_duration, parse_meter, voicing_notes

PPQ = 480  # Ticks per quarter note


def _vlq(value: int) -> bytes:
    """Encode a non-negative integer as a MIDI Variable-Length Quantity."""
    value = max(0, int(value))
    chunks = [value & 0x7F]
    value >>= 7
    while value:
        chunks.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(chunks))


def _build_track(name: str, channel: int, program: int | None, events: list[tuple[int, bytes]]) -> bytes:
    """Build a complete MTrk chunk from (abs_tick, raw_midi_bytes) tuples."""
    track_events: list[tuple[int, int, bytes]] = []
    name_bytes = name.encode("ascii", errors="replace")
    track_events.append((0, 0, b"\xFF\x03" + _vlq(len(name_bytes)) + name_bytes))
    if program is not None:
        track_events.append((0, 1, bytes([0xC0 | (channel & 0x0F), program & 0x7F])))

    for idx, (tick, payload) in enumerate(events):
        # Ensure Note-Off (0x80) sorts before Note-On (0x90) at the exact same tick
        priority = 2 if (payload[0] & 0xF0) == 0x80 else 3
        track_events.append((max(0, int(tick)), priority, payload))

    track_events.sort(key=lambda item: (item[0], item[1]))

    body = bytearray()
    last_tick = 0
    for tick, _, payload in track_events:
        body.extend(_vlq(tick - last_tick))
        body.extend(payload)
        last_tick = tick

    body.extend(b"\x00\xFF\x2F\x00")  # End of Track
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def _add_note(events: list[tuple[int, bytes]], channel: int, pitch: int, start: int, end: int, vel: int = 90):
    p = max(0, min(127, int(pitch)))
    v = max(1, min(127, int(vel)))
    ch = channel & 0x0F
    if end <= start:
        end = start + 60
    events.append((start, bytes([0x90 | ch, p, v])))
    events.append((end, bytes([0x80 | ch, p, 0])))


def _chord_pitches(song: dict, chord_obj: dict) -> list[int]:
    """Return sorted MIDI pitches from a chord's 6-string voicing."""
    notes = voicing_notes(song["tuning"], chord_obj["voicing"])
    return sorted({n["midi"] for n in notes})


def render_midi_bytes(song: dict) -> bytes:
    """Compile a validated guitar-notation song dict into Type 1 MIDI bytes."""
    tempo_bpm = int(song.get("tempo", 120))
    us_per_quarter = int(round(60_000_000 / max(1, tempo_bpm)))
    num, den, _ = parse_meter(song.get("meter", "4/4"))
    den_pow = {1: 0, 2: 1, 4: 2, 8: 3, 16: 4}.get(den, 2)

    # Track 0: Conductor track (Tempo & Time Signature)
    conductor: list[tuple[int, bytes]] = [
        (0, b"\xFF\x51\x03" + us_per_quarter.to_bytes(3, "big")),
        (0, bytes([0xFF, 0x58, 0x04, num, den_pow, 24, 8])),
    ]

    melody_ev: list[tuple[int, bytes]] = []
    guitar_ev: list[tuple[int, bytes]] = []
    keys_ev: list[tuple[int, bytes]] = []
    bass_ev: list[tuple[int, bytes]] = []
    horns_ev: list[tuple[int, bytes]] = []
    strings_ev: list[tuple[int, bytes]] = []
    drums_ev: list[tuple[int, bytes]] = []

    whole_ticks = PPQ * 4
    bar_ticks = int(round(whole_ticks * Fraction(num, den)))
    quarter_ticks = PPQ
    eighth_ticks = PPQ // 2

    # Collect timeline spans for chord regions so pads/bass/keys sustain across chord changes
    chord_spans: list[tuple[int, int, list[int]]] = []
    active_chord: list[int] | None = None
    active_start = 0
    cursor = 0

    for bar in song["bars"]:
        for ev in bar["events"]:
            _, dur_frac = parse_duration(ev["duration"])
            dur_ticks = int(round(whole_ticks * dur_frac))
            resolved = resolve_event(song, ev)

            if ev.get("chord"):
                new_pitches = _chord_pitches(song, ev["chord"])
                if active_chord is not None and cursor > active_start:
                    chord_spans.append((active_start, cursor, active_chord))
                active_chord = new_pitches
                active_start = cursor

            # Track 1 & 2: Melody Guide (top note) and Guitar Reference (all resolved notes)
            if resolved:
                top_note = resolved[-1]["midi"]
                _add_note(melody_ev, 0, top_note, cursor, cursor + int(dur_ticks * 0.92), vel=100)
                for idx, n in enumerate(resolved):
                    # Slight 15-tick strum roll for multi-note guitar voicings
                    strum_offset = idx * 15 if len(resolved) > 1 else 0
                    _add_note(
                        guitar_ev,
                        1,
                        n["midi"],
                        cursor + strum_offset,
                        cursor + int(dur_ticks * 0.95),
                        vel=88,
                    )

            cursor += dur_ticks

    total_ticks = cursor
    if active_chord is not None and total_ticks > active_start:
        chord_spans.append((active_start, total_ticks, active_chord))

    # Populate Backing Band Tracks across each chord span
    for start, end, pitches in chord_spans:
        if not pitches:
            continue
        root = pitches[0]
        while root > 52:  # Keep bass in E1–E3 register
            root -= 12
        while root < 28:
            root += 12
        fifth = root + 7

        # Upper voicing for keys/strings/horns (C3–C5 register)
        upper = [p + 12 if p < 48 else p for p in pitches]

        # Track 6: String Ensemble (warm sustained pad across the chord span)
        for p in upper:
            _add_note(strings_ev, 5, p, start, end - 20, vel=64)

        # Track 5: Horn Section (punchy harmonic stab on the chord change)
        stab_len = min(quarter_ticks, end - start - 10)
        for p in upper[-3:]:
            _add_note(horns_ev, 4, p, start, start + stab_len, vel=84)

        # Track 3: Keyboards (rhythmic quarter-note comping)
        t = start
        while t < end:
            step = min(quarter_ticks, end - t)
            for p in upper:
                _add_note(keys_ev, 2, p, t, t + int(step * 0.85), vel=76)
            t += quarter_ticks

        # Track 4: Electric Bass (root on beat 1/3, fifth on beat 2/4)
        t = start
        beat_idx = 0
        while t < end:
            step = min(quarter_ticks, end - t)
            bass_note = root if beat_idx % 2 == 0 else fifth
            _add_note(bass_ev, 3, bass_note, t, t + int(step * 0.88), vel=94)
            t += quarter_ticks
            beat_idx += 1

    # Track 7: Drums (GM Channel 9 -> MIDI Ch 10: 36=Kick, 38=Snare, 42=Closed Hat)
    t = 0
    step_idx = 0
    while t < total_ticks:
        bar_pos = t % max(1, bar_ticks)
        beat_in_bar = bar_pos // quarter_ticks
        is_on_beat = (bar_pos % quarter_ticks) == 0

        _add_note(drums_ev, 9, 42, t, t + 90, vel=72 if is_on_beat else 56)
        if is_on_beat and beat_in_bar % 2 == 0:
            _add_note(drums_ev, 9, 36, t, t + 120, vel=105)
        elif is_on_beat and beat_in_bar % 2 == 1:
            _add_note(drums_ev, 9, 38, t, t + 120, vel=98)

        t += eighth_ticks
        step_idx += 1

    tracks = [
        _build_track("Conductor", 0, None, conductor),
        _build_track("Melody Guide", 0, 73, melody_ev),
        _build_track("Guitar Reference", 1, 24, guitar_ev),
        _build_track("Keyboards", 2, 4, keys_ev),
        _build_track("Electric Bass", 3, 33, bass_ev),
        _build_track("Horn Section", 4, 61, horns_ev),
        _build_track("String Ensemble", 5, 48, strings_ev),
        _build_track("Drums", 9, None, drums_ev),
    ]

    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), PPQ)
    return header + b"".join(tracks)


def write_midi(song: dict, path: str | Path) -> Path:
    out_path = Path(path)
    out_path.write_bytes(render_midi_bytes(song))
    return out_path
