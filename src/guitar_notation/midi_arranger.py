"""Vibe-aware Lo-Fi / 60s Tube / Soft Jazz & Flamenco MIDI Arranger (-12dB Headroom).

Generates a 7-track Logic Pro-ready Type 1 MIDI file calibrated with low channel
gain (CC 7) and soft dynamics so Stereo Out maintains ~-12 dB of headroom for
live acoustic guitar tracking.
"""
import random
import struct
from fractions import Fraction
from pathlib import Path

from .render import resolve_event
from .validation import midi_note, parse_duration, parse_meter, voicing_notes

PPQ = 480

# Curated Lo-Fi / Soft Jazz / Flamenco / 60s Warm Tube GM Instrument Palettes
# Tuple format: (track_label, midi_channel, gm_program, cc7_volume, base_velocity)
VIBE_PALETTES = {
    "flamenco_jazz": {
        "melody": ("Mellotron Flute", 0, 73, 58, 72),
        "guitar": ("Flamenco Nylon", 1, 24, 52, 64),
        "keys": ("60s Warm Rhodes", 2, 4, 50, 58),
        "bass": ("Upright Acoustic Bass", 3, 32, 62, 74),
        "horns": ("Muted Jazz Trumpet", 4, 59, 48, 60),
        "strings": ("Warm Tape Strings", 5, 49, 44, 52),
        "drums": ("Lo-Fi Brush Kit", 9, None, 56, 66),
    },
    "lofi_60s_soul": {
        "melody": ("Mellotron Flute", 0, 73, 58, 72),
        "guitar": ("60s Hollowbody Jazz", 1, 26, 50, 62),
        "keys": ("60s Warm Rhodes", 2, 4, 50, 58),
        "bass": ("Warm Tube Fretless", 3, 35, 62, 74),
        "horns": ("Soft Flugelhorn", 4, 60, 48, 60),
        "strings": ("Mellotron Strings", 5, 49, 44, 50),
        "drums": ("Vintage 60s Kit", 9, None, 55, 65),
    },
    "mellow_bossa_lofi": {
        "melody": ("Mellotron Flute", 0, 73, 58, 72),
        "guitar": ("Nylon Bossa Guitar", 1, 24, 52, 64),
        "keys": ("Soft Wurlitzer EP", 2, 5, 50, 58),
        "bass": ("Upright Acoustic Bass", 3, 32, 62, 74),
        "horns": ("Warm Tenor Sax", 4, 66, 48, 58),
        "strings": ("Warm Tape Strings", 5, 49, 44, 50),
        "drums": ("Lo-Fi Rimshot Kit", 9, None, 55, 64),
    },
}


def _detect_vibe(song: dict) -> str:
    """Selects a sub-palette within the Lo-Fi / 60s Tube / Soft Jazz / Flamenco aesthetic."""
    blob = " ".join([
        str(song.get("title", "")),
        str(song.get("key", "")),
        str(song.get("notes", "")),
    ]).lower()
    tempo = int(song.get("tempo", 95))

    if any(w in blob for w in ("flamenco", "spanish", "andalus", "phrygian", "rumba", "gypsy")):
        return "flamenco_jazz"
    if any(w in blob for w in ("bossa", "montmartre", "latin", "samba", "waltz", "paris")):
        return "mellow_bossa_lofi"
    if tempo <= 88 or any(w in blob for w in ("soul", "60s", "vinyl", "lofi", "lo-fi", "chill", "tube", "rhodes")):
        return "lofi_60s_soul"
    return "mellow_bossa_lofi"


def _vlq(value: int) -> bytes:
    """Encode a non-negative integer as a MIDI Variable-Length Quantity."""
    value = max(0, int(value))
    chunks = [value & 0x7F]
    value >>= 7
    while value:
        chunks.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(chunks))


def _build_track(
    name: str,
    channel: int,
    program: int | None,
    cc7_vol: int,
    events: list[tuple[int, bytes]],
    add_tape_wobble: bool = False,
) -> bytes:
    """Build a complete MTrk chunk with -12dB headroom CC scaling and optional tape drift."""
    track_events: list[tuple[int, int, bytes]] = []
    ch = channel & 0x0F
    if name:
        name_bytes = name.encode("ascii", errors="replace")
        track_events.append((0, 0, b"\xFF\x03" + _vlq(len(name_bytes)) + name_bytes))

    if program is not None:
        track_events.append((0, 1, bytes([0xC0 | ch, program & 0x7F])))

    # Conservative CC 7 (Channel Volume) and CC 11 (Expression) for ~-12 dB master headroom
    track_events.append((0, 1, bytes([0xB0 | ch, 7, max(1, min(127, cc7_vol))])))
    track_events.append((0, 1, bytes([0xB0 | ch, 11, 96])))
    # Gentle low-pass warmth (CC 74 Brightness) for 60s tube amp character
    track_events.append((0, 1, bytes([0xB0 | ch, 74, 54])))

    max_tick = 0
    for tick, payload in events:
        t = max(0, int(tick))
        if t > max_tick:
            max_tick = t
        first_byte = payload[0]
        if first_byte == 0xFF:
            priority = 1
        elif (first_byte & 0xF0) == 0x80:
            priority = 2
        else:
            priority = 3
        track_events.append((t, priority, payload))


    # Subtle 60s analog tape wow/flutter micro-pitch drift (8192 = center pitch)
    if add_tape_wobble and max_tick > 0:
        wobble_steps = [8192, 8220, 8192, 8164]
        t = 0
        idx = 0
        while t < max_tick:
            val = wobble_steps[idx % len(wobble_steps)]
            lsb = val & 0x7F
            msb = (val >> 7) & 0x7F
            track_events.append((t, 2, bytes([0xE0 | ch, lsb, msb])))
            t += PPQ * 2
            idx += 1
        track_events.append((max_tick, 2, bytes([0xE0 | ch, 0x00, 0x40])))

    track_events.sort(key=lambda item: (item[0], item[1]))

    body = bytearray()
    last_tick = 0
    for tick, _, payload in track_events:
        body.extend(_vlq(tick - last_tick))
        body.extend(payload)
        last_tick = tick

    body.extend(b"\x00\xFF\x2F\x00")
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def _add_note(events: list[tuple[int, bytes]], channel: int, pitch: int, start: int, end: int, vel: int):
    p = max(0, min(127, int(pitch)))
    v = max(1, min(127, int(vel)))
    ch = channel & 0x0F
    if end <= start:
        end = start + 60
    events.append((start, bytes([0x90 | ch, p, v])))
    events.append((end, bytes([0x80 | ch, p, 0])))


def _chord_pitches(song: dict, chord_obj: dict) -> list[int]:
    notes = voicing_notes(song["tuning"], chord_obj["voicing"])
    return sorted({n["midi"] for n in notes})


def render_midi_bytes(song: dict) -> bytes:
    """Compile a validated guitar-notation song dict into Lo-Fi / 60s Jazz Type 1 MIDI bytes."""
    rng = random.Random(str(song.get("title", "seed")))
    vibe_key = _detect_vibe(song)
    palette = VIBE_PALETTES[vibe_key]

    tempo_bpm = int(song.get("tempo", 92))
    us_per_quarter = int(round(60_000_000 / max(1, tempo_bpm)))
    num, den, _ = parse_meter(song.get("meter", "4/4"))
    den_pow = {1: 0, 2: 1, 4: 2, 8: 3, 16: 4}.get(den, 2)

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

            if resolved:
                human_shift = rng.randint(-8, 12)
                mel_vel = palette["melody"][4] + rng.randint(-5, 5)
                guide_notes = [midi_note(note) for note in ev["melody"]] if ev.get("melody") else [resolved[-1]["midi"]]
                for guide_note in guide_notes:
                    _add_note(
                        melody_ev,
                        palette["melody"][1],
                        guide_note,
                        max(0, cursor + human_shift),
                        cursor + int(dur_ticks * 0.92),
                        vel=mel_vel,
                    )

                gtr_base_vel = palette["guitar"][4]
                for idx, n in enumerate(resolved):
                    strum_offset = idx * 24 if len(resolved) > 1 else 0
                    _add_note(
                        guitar_ev,
                        palette["guitar"][1],
                        n["midi"],
                        cursor + strum_offset,
                        cursor + int(dur_ticks * 0.94),
                        vel=gtr_base_vel + rng.randint(-4, 4),
                    )

            cursor += dur_ticks

    total_ticks = cursor
    if active_chord is not None and total_ticks > active_start:
        chord_spans.append((active_start, total_ticks, active_chord))

    is_compound_8 = (den == 8 and num in (6, 9, 12))
    pulse_ticks = (quarter_ticks + eighth_ticks) if is_compound_8 else quarter_ticks
    sub_ticks = eighth_ticks

    # Backing Band Arrangement (Meter-aware Soft Jazz / Flamenco / 60s Lo-Fi)
    for start, end, pitches in chord_spans:
        if not pitches:
            continue
        root = pitches[0]
        while root > 52:
            root -= 12
        while root < 28:
            root += 12
        fifth = root + 7
        third = (pitches[1] - 12) if len(pitches) > 1 and (pitches[1] - 12) >= 28 else root
        upper = [p + 12 if p < 48 else p for p in pitches]

        # Track 6: Warm Tape Strings (sustained pad across any meter)
        str_ch, _, _, str_vel = palette["strings"][1:]
        for p in upper:
            _add_note(strings_ev, str_ch, p, start + 15, end - 25, vel=str_vel)

        # Track 5: Muted Jazz Horns (warm swell scaled to the meter's pulse)
        horn_ch, _, _, horn_vel = palette["horns"][1:]
        stab_len = min(int(pulse_ticks * 1.35), end - start - 15)
        for p in upper[-3:]:
            _add_note(horns_ev, horn_ch, p, start + 10, start + stab_len, vel=horn_vel + rng.randint(-3, 3))

        # Track 3: Keys (adapts to 3/4 waltz, 6/8 compound, or odd/4/4 meters)
        keys_ch, _, _, keys_vel = palette["keys"][1:]
        t = start
        pulse_i = 0
        while t < end:
            bar_pos = t % max(1, bar_ticks)
            beat_num = bar_pos // pulse_ticks
            # In 3/4, play light stabs on beats 2 & 3; in other meters, syncopate off-pulses
            if num == 3 and den == 4 and beat_num == 0:
                t += pulse_ticks
                pulse_i += 1
                continue
            offset = int(sub_ticks * 0.12) if pulse_i % 2 == 1 else 0
            comp_len = min(int(pulse_ticks * 0.72), end - t)
            if comp_len > 40:
                for p in upper:
                    _add_note(keys_ev, keys_ch, p, t + offset, t + offset + comp_len, vel=keys_vel + rng.randint(-4, 4))
            t += pulse_ticks
            pulse_i += 1

        # Track 4: Upright / Fretless Bass (follows bar downbeats & meter accents)
        bass_ch, _, _, bass_vel = palette["bass"][1:]
        t = start
        while t < end:
            bar_pos = t % max(1, bar_ticks)
            beat_num = bar_pos // pulse_ticks
            step = min(int(pulse_ticks * 0.88), end - t)
            if beat_num == 0:
                b_note = root
            elif (num == 3 and beat_num == 2) or (num >= 4 and beat_num == 2):
                b_note = fifth
            elif beat_num == (max(1, bar_ticks // pulse_ticks) - 1):
                b_note = third
            else:
                b_note = root
            _add_note(bass_ev, bass_ch, b_note, t + rng.randint(-6, 8), t + step, vel=bass_vel + rng.randint(-4, 4))
            t += pulse_ticks

    # Track 7: Meter-Aware Lo-Fi Brush / Rimshot Groove
    drum_ch, _, _, drum_vel = palette["drums"][1:]
    t = 0
    while t < total_ticks:
        bar_pos = t % max(1, bar_ticks)
        step_in_bar = bar_pos // sub_ticks
        is_downbeat = (bar_pos == 0)

        if is_compound_8:
            # Compound time (6/8, 9/8, 12/8): 3-eighth-note triplets per main pulse
            is_pulse_start = (step_in_bar % 3 == 0)
            pulse_idx = step_in_bar // 3
            hat_note = 42 if is_pulse_start else 44
            _add_note(drums_ev, drum_ch, hat_note, t, t + 75, vel=int(drum_vel * (0.85 if is_pulse_start else 0.58)))
            if is_downbeat or (num == 12 and pulse_idx == 2 and is_pulse_start):
                _add_note(drums_ev, drum_ch, 36, t, t + 110, vel=drum_vel)
            elif is_pulse_start and pulse_idx % 2 == 1:
                _add_note(drums_ev, drum_ch, 37, t + rng.randint(-4, 6), t + 100, vel=int(drum_vel * 0.88))
        elif den == 8:
            # Odd eighth-note meters (5/8, 7/8): group in 3+2 or 2+2+3
            accents = {0, 3} if num == 5 else {0, 2, 4} if num == 7 else {0}
            is_accent = step_in_bar in accents
            _add_note(drums_ev, drum_ch, 42 if is_accent else 44, t, t + 75, vel=int(drum_vel * (0.85 if is_accent else 0.58)))
            if is_downbeat:
                _add_note(drums_ev, drum_ch, 36, t, t + 110, vel=drum_vel)
            elif is_accent:
                _add_note(drums_ev, drum_ch, 37, t, t + 100, vel=int(drum_vel * 0.85))
        else:
            # Quarter-note meters (3/4 jazz waltz, 4/4 bossa/lofi, 5/4 Take Five feel)
            beat_in_bar = bar_pos // quarter_ticks
            is_on_beat = (bar_pos % quarter_ticks) == 0
            swing_shift = int(sub_ticks * 0.14) if not is_on_beat else 0

            _add_note(
                drums_ev,
                drum_ch,
                42 if is_on_beat else 44,
                t + swing_shift,
                t + swing_shift + 80,
                vel=int(drum_vel * (0.85 if is_on_beat else 0.62)) + rng.randint(-4, 4),
            )
            if is_downbeat:
                _add_note(drums_ev, drum_ch, 36, t, t + 110, vel=drum_vel)
            elif num == 5 and is_on_beat and beat_in_bar == 3:
                # Classic 5/4 secondary pulse on beat 4
                _add_note(drums_ev, drum_ch, 36, t, t + 100, vel=int(drum_vel * 0.85))
            elif num == 4 and not is_on_beat and beat_in_bar in (1, 2):
                _add_note(drums_ev, drum_ch, 36, t + swing_shift, t + swing_shift + 100, vel=int(drum_vel * 0.78))

            # Rimshot placement by meter: beat 2 & 3 in 3/4, beat 2 & 4 in 4/4, beat 2 & 5 in 5/4
            rim_beats = {1, 2} if num == 3 else {1, 4} if num == 5 else {1, 3}
            if is_on_beat and beat_in_bar in rim_beats:
                _add_note(drums_ev, drum_ch, 37, t + rng.randint(-5, 8), t + 100, vel=int(drum_vel * 0.88))

        t += sub_ticks

    # Prepend Tempo & Time Signature meta-events onto Track 1 so Logic Pro does not
    # create an empty Track 0 channel strip on import
    melody_with_conductor = conductor + melody_ev

    tracks = [
        _build_track(*palette["melody"][:4], melody_with_conductor, add_tape_wobble=True),
        _build_track(*palette["guitar"][:4], guitar_ev, add_tape_wobble=False),
        _build_track(*palette["keys"][:4], keys_ev, add_tape_wobble=True),
        _build_track(*palette["bass"][:4], bass_ev, add_tape_wobble=False),
        _build_track(*palette["horns"][:4], horns_ev, add_tape_wobble=False),
        _build_track(*palette["strings"][:4], strings_ev, add_tape_wobble=True),
        _build_track(*palette["drums"][:4], drums_ev, add_tape_wobble=False),
    ]

    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), PPQ)
    return header + b"".join(tracks)


def write_midi(song: dict, path: str | Path) -> Path:
    out_path = Path(path)
    out_path.write_bytes(render_midi_bytes(song))
    return out_path
