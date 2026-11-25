import json
import re
import sys
import unittest
from copy import deepcopy
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from guitar_notation.render import chord_changes, render_lilypond, render_markdown  # noqa: E402
from guitar_notation.validation import auto_position, check_song, chord_spec, analyze_chord, midi_note  # noqa: E402

EXAMPLE = json.loads((ROOT / "references" / "example.json").read_text(encoding="utf-8"))
BAD = json.loads((Path(__file__).parent / "fixtures" / "montmartre_original_bad.json").read_text(encoding="utf-8"))
TUNING = ["E2", "A2", "D3", "G3", "B3", "E4"]


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
        song["bars"][3]["events"][3]["duration"] = 8
        self.assertTrue(any("Bar 4" in e for e in check_song(song)[0]))
        song["bars"][3]["events"][2]["duration"] = "4."
        song["bars"][3]["events"][3]["duration"] = 8
        self.assertEqual(check_song(song)[0], [])

    def test_play_chord_melody_must_be_top_note(self):
        song = deepcopy(EXAMPLE)
        song["bars"][0]["events"][0]["melody"] = ["A4"]
        self.assertTrue(any("top note" in e for e in check_song(song)[0]))

    def test_bad_shapes_do_not_crash(self):
        for bad in ({}, [], {"title": "x", "tempo": 90, "meter": "4/4", "tuning": TUNING, "bars": [5]},
                    {"title": "x", "tempo": "fast", "meter": "4/4", "tuning": TUNING, "bars": [{"events": [1]}]}):
            self.assertTrue(check_song(bad)[0])

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
        self.assertEqual(total, Fraction(4))
        ly = render_lilypond(EXAMPLE)
        skips = [int(x) for x in re.findall(r"s64\*(\d+)", ly)]
        self.assertEqual(sum(skips), 4 * 64)
        self.assertEqual([c["name"] for _, c in marks], ["Em9", "Cmaj7#11", "Am9", "D13", "B7b13", "Em6"])

    def test_repeated_chord_gets_one_diagram(self):
        song = deepcopy(EXAMPLE)
        song["bars"][3]["events"][0]["chord"] = deepcopy(song["bars"][2]["events"][2]["chord"])
        self.assertEqual(len(chord_changes(song)[0]), 6)

    def test_staff_and_tab_have_same_rhythm(self):
        ly = render_lilypond(EXAMPLE)
        staff = re.search(r"melodyStaff = \{(.*?)\n\}", ly, re.S).group(1)
        tab = re.search(r"melodyTab = \{(.*?)\n\}", ly, re.S).group(1)
        strip = lambda t: re.sub(r"\\\d", "", re.sub(r"%.*", "", t))
        self.assertEqual(strip(staff).split(), strip(tab).split())

    def test_markdown_mentions_every_chord(self):
        md = render_markdown(EXAMPLE)
        for name in ("Em9", "Cmaj7#11", "Am9", "D13", "B7b13", "Em6"):
            self.assertIn(name, md)


if __name__ == "__main__":
    unittest.main()
