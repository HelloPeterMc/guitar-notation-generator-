import json
from pathlib import Path

from guitar_notation.render import render_lilypond, render_markdown


def sample():
    return json.loads((Path(__file__).parents[1] / "examples/montmartre.json").read_text())


def test_render_sample():
    song = sample()
    lilypond = render_lilypond(song)
    markdown = render_markdown(song)

    assert lilypond.startswith('\\version "2.24.0"\n')
    assert "e''2^\\markup" in lilypond
    assert "\n## Bar 1\n" in markdown
