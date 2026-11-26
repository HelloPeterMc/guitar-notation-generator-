import json
from pathlib import Path

from guitar_notation.render import render_lilypond, render_markdown


def sample():
    return json.loads((Path(__file__).parents[1] / "references/example.json").read_text())


def test_render_sample():
    song = sample()
    lilypond = render_lilypond(song)
    markdown = render_markdown(song)

    assert lilypond.startswith('\\version "2.24.0"\n')
    assert "chordDiagrams = {" in lilypond
    assert "fret-diagram-verbose" in lilypond
    assert "#### Bar 1" in markdown
