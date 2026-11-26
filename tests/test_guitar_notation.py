import json
import re
import unittest
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from guitar_notation.render import chord_changes, render_lilypond, render_markdown  # noqa: E402
from guitar_notation.midi_arranger import render_midi_bytes  # noqa: E402
from guitar_notation.validation import auto_position, check_song, chord_spec, analyze_chord, midi_note  # noqa: E402

EXAMPLE = json.loads((ROOT / "references" / "example.json").read_text(encoding="utf-8"))
LESSON = json.loads((ROOT / "references" / "example_lesson_plan.json").read_text(encoding="utf-8"))
BAD = json.loads((ROOT / "tests" / "fixtures" / "montmartre_original_bad.json").read_text(encoding="utf-8"))
TUNING = ["E2", "A2", "D3", "G3", "B3", "E4"]


def midi_tracks(midi):
    count = int.from_bytes(midi[10:12], "big")
    offset = 14
    tracks = []
    for _ in range(count):
        assert midi[offset:offset + 4] == b"MTrk"
        length = int.from_bytes(midi[offset + 4:offset + 8], "big")
        tracks.append(midi[offset + 8:offset + 8 + length])
        offset += 8 + length
    return tracks


def read_vlq(data, offset):
    value = 0
    while True:
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if byte < 0x80:
            return value, offset


def note_ons(track):
    events, offset, tick = [], 0, 0
    while offset < len(track):
        delta, offset = read_vlq(track, offset)
        tick += delta
        status = track[offset]
        offset += 1
        if status == 0xFF:
            meta_type = track[offset]
            length, offset = read_vlq(track, offset + 1)
            offset += length
            if meta_type == 0x2F:
                break
            continue
        size = 1 if status & 0xF0 in (0xC0, 0xD0) else 2
        values = track[offset:offset + size]
        offset += size
        if status & 0xF0 == 0x90 and len(values) == 2 and values[1] > 0:
            events.append((tick, status & 0x0F, values[0]))
    return events


def chord_errors(name, voicing):
    """Errors for a chord; also fails the test if the name could not be parsed at all."""
    song = deepcopy(EXAMPLE)
    song["bars"] = [{"events": [{"duration": 1, "chord": {"name": name, "voicing": voicing}}]}]
    errors, warnings = check_song(song)
    assert not any("cannot verify" in w for w in warnings), f"{name} was not parsed"
    return errors


class ValidationTests(unittest.TestCase):
    def test_example_is_clean(self):
        errors, warnings = check_song(EXAMPLE)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_lesson_plan_example_is_clean(self):
        errors, warnings = check_song(LESSON)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_original_draft_is_rejected(self):
        errors = "\n".join(check_song(BAD)[0])
        self.assertIn("melody sounds E5 but tab sounds E4", errors)
        self.assertIn("does not match 'Em6'", errors)

    def test_chord_names(self):
        self.assertEqual(chord_errors("Em9", [0, 2, 4, 0, 3, 0]), [])      # open Em9 is valid
        self.assertEqual(chord_errors("Em6", [0, 2, 2, 0, 2, 0]), [])      # open Em6 is valid
        self.assertEqual(chord_errors("Em6/9", [0, 2, 2, 0, 2, 2]), [])
        self.assertEqual(chord_errors("B7b13", [7, -1, 7, 8, 8, -1]), [])
        self.assertEqual(chord_errors("B7alt", [7, -1, 7, 8, 8, -1]), [])
        self.assertTrue(chord_errors("B7#9", [7, -1, 7, 8, 8, -1]))        # mislabeled
        self.assertTrue(chord_errors("Em6", [-1, 7, 6, 9, 8, -1]))         # spells E G# E G
        self.assertTrue(chord_errors("Em", [0, 2, 2, 0, 2, 0]))            # extra C#
        self.assertEqual(chord_errors("Cmaj7/E", [0, 3, 2, 0, 0, 0]), [])  # slash bass
        self.assertTrue(chord_errors("Cmaj7/E", [-1, 3, 2, 0, 0, 0]))      # bass is C, not E

    def test_unparseable_chord_is_warning_not_error(self):
        song = deepcopy(EXAMPLE)
        song["bars"][0]["events"][0]["chord"]["name"] = "Em(hip)"
        errors, warnings = check_song(song)
        self.assertEqual(errors, [])
        self.assertTrue(any("cannot verify" in w for w in warnings))

    def test_bar_length_and_dotted_durations(self):
        song = deepcopy(EXAMPLE)
        song["bars"][0]["events"][0]["duration"] = 8
        self.assertTrue(any("Bar 1" in e for e in check_song(song)[0]))

        song = deepcopy(EXAMPLE)
        song["bars"][0]["events"][1]["duration"] = "8."
        song["bars"][0]["events"][2]["duration"] = 16
        self.assertEqual(check_song(song)[0], [])

    def test_play_chord_supports_an_independent_melody_guide(self):
        song = deepcopy(EXAMPLE)
        song["bars"][0]["events"][0]["melody"] = ["G3"]
        self.assertEqual(check_song(song), ([], []))

    def test_bar_sections_are_validated(self):
        song = deepcopy(EXAMPLE)
        song["bars"][0]["section"] = "Shell voicings"
        self.assertEqual(check_song(song), ([], []))
        song["bars"][0]["section"] = " "
        self.assertTrue(any("section must be" in e for e in check_song(song)[0]))

    def test_bad_shapes_do_not_crash(self):
        for bad in ({}, [], {"title": "x", "tempo": 90, "meter": "4/4", "tuning": TUNING, "bars": [5]},
                    {"title": "x", "tempo": "fast", "meter": "4/4", "tuning": TUNING, "bars": [{"events": [1]}]}):
            self.assertTrue(check_song(bad)[0])

    def test_optional_schema_fields_are_checked(self):
        song = deepcopy(EXAMPLE)
        song["layout"] = {"bars_per_line": True}
        self.assertTrue(any("bars_per_line" in error for error in check_song(song)[0]))

        song = deepcopy(EXAMPLE)
        song["composer"] = 4
        self.assertTrue(any("composer must be a string" in error for error in check_song(song)[0]))

        song = deepcopy(EXAMPLE)
        song["bars"][0]["events"][0]["chord"]["show"] = "yes"
        self.assertTrue(any("chord show must" in error for error in check_song(song)[0]))

    def test_auto_position(self):
        self.assertEqual(auto_position(TUNING, midi_note("E4")), {"string": 1, "fret": 0})
        self.assertIsNone(auto_position(TUNING, midi_note("C2")))


class RenderTests(unittest.TestCase):
    def test_lilypond_is_balanced(self):
        ly = render_lilypond(EXAMPLE)
        self.assertEqual(ly.count("{"), ly.count("}"))
        self.assertEqual(ly.count("<<"), ly.count(">>"))
        self.assertEqual(ly.count('"') % 2, 0)
        self.assertIn('\\clef "treble_8"', ly)

    def test_chord_voice_covers_whole_song(self):
        marks, total = chord_changes(EXAMPLE)
        self.assertEqual(total, Fraction(8))
        ly = render_lilypond(EXAMPLE)
        skips = [int(x) for x in re.findall(r"s64\*(\d+)", ly)]
        self.assertEqual(sum(skips), 8 * 64)
        self.assertEqual(
            [c["name"] for _, c in marks],
            ["Em7", "Fmaj7", "Em7", "Dm7", "Fmaj7", "Dm7", "Fmaj7", "Em7"],
        )

    def test_repeated_chord_gets_one_diagram(self):
        song = deepcopy(EXAMPLE)
        first_bar = song["bars"][0]
        song["bars"] = [{"events": [first_bar["events"][0], first_bar["events"][3]]}]
        self.assertEqual([c["name"] for _, c in chord_changes(song)[0]], ["Em7"])

    def test_staff_and_tab_have_same_rhythm(self):
        ly = render_lilypond(EXAMPLE)
        staff = re.search(r"melodyStaff = \{(.*?)\n\}", ly, re.S).group(1)
        tab = re.search(r"melodyTab = \{(.*?)\n\}", ly, re.S).group(1)
        event_durations = lambda voice: re.findall(
            r"(?:<[^>]+>|[a-gr](?:is|es)?[',]*)(16|1|2|4|8)(\.{0,2})", voice
        )
        self.assertEqual(event_durations(staff), event_durations(tab))
        self.assertEqual(len(event_durations(staff)), sum(len(bar["events"]) for bar in EXAMPLE["bars"]))

    def test_markdown_mentions_every_chord(self):
        md = render_markdown(EXAMPLE)
        for name in ("Em7", "Fmaj7", "Dm7"):
            self.assertIn(name, md)

    def test_markdown_shows_section_and_independent_melody(self):
        song = deepcopy(EXAMPLE)
        song["bars"][0]["section"] = "Shell voicings"
        song["bars"][0]["events"][0]["melody"] = ["G3"]
        md = render_markdown(song)
        self.assertIn("### Shell voicings", md)
        self.assertIn("| G3 |", md)

    def test_lesson_plan_renders_sections_and_melody_targets(self):
        md = render_markdown(LESSON)
        self.assertIn("### 1. Shell voicings", md)
        self.assertIn("### 2. Ninth and thirteenth colors", md)
        self.assertIn("| F3 |", md)


class MidiTests(unittest.TestCase):
    def test_midi_has_eight_ordered_tracks(self):
        midi = render_midi_bytes(EXAMPLE)
        self.assertEqual(midi[:4], b"MThd")
        tracks = midi_tracks(midi)
        self.assertEqual(len(tracks), 8)
        names = [
            b"Classical Acoustic Guitar Melody",
            b"Classical Acoustic Guitar Chords",
            b"Mellotron Flute",
            b"60s Warm Rhodes",
            b"Upright Acoustic Bass",
            b"Muted Jazz Trumpet",
            b"Warm Tape Strings",
            b"Lo-Fi Brush Kit",
        ]
        for track, name in zip(tracks, names):
            self.assertIn(name, track)

    def test_melody_guitar_and_mellotron_are_melody_only(self):
        tracks = midi_tracks(render_midi_bytes(LESSON))
        guitar_melody = note_ons(tracks[0])
        mellotron = note_ons(tracks[2])
        guitar_chords = note_ons(tracks[1])
        self.assertTrue(guitar_melody)
        self.assertEqual([(t, p) for t, _, p in guitar_melody],
                         [(t, p) for t, _, p in mellotron])
        self.assertIn((0, 1, 50), guitar_chords)
        self.assertIn((12, 1, 53), guitar_chords)

    def test_chord_track_hits_downbeats_and_each_change(self):
        song = deepcopy(EXAMPLE)
        song["bars"] = [
            {"events": [
                {"duration": 4, "chord": {"name": "Em7", "voicing": [0, 2, 0, 0, 0, 0]}},
                {"duration": 4},
                {"duration": 4, "chord": {"name": "Fmaj7", "voicing": [-1, -1, 3, 2, 1, 0]}},
                {"duration": 4},
            ]},
            {"events": [
                {"duration": 4, "chord": {"name": "Fmaj7", "voicing": [-1, -1, 3, 2, 1, 0]}},
                {"duration": 4, "chord": {"name": "Em7", "voicing": [0, 2, 0, 0, 0, 0]}},
                {"duration": 4, "chord": {"name": "G7", "voicing": [3, -1, 3, 4, -1, -1]}},
                {"duration": 4, "chord": {"name": "Dm7", "voicing": [-1, -1, 0, 2, 1, 1]}},
            ]},
        ]
        events = note_ons(midi_tracks(render_midi_bytes(song))[1])
        ticks = sorted(tick for tick, channel, _ in events if channel == 1)
        hit_starts = []
        for tick in ticks:
            if not hit_starts or tick - hit_starts[-1] > 60:
                hit_starts.append(tick)
        self.assertEqual(hit_starts, [0, 960, 1920, 2400, 2880, 3360])

    def test_lesson_midi_uses_explicit_independent_melody(self):
        midi = render_midi_bytes(LESSON)
        self.assertEqual(int.from_bytes(midi[10:12], "big"), 8)
        # The first melody guide note is F3 (MIDI 53), the third of Dm7.
        self.assertIn(b"\x90\x35", midi)
        self.assertIn(b"60s Warm Rhodes", midi)


if __name__ == "__main__":
    unittest.main()
