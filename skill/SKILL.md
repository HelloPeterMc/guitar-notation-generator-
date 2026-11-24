---
name: guitar-notation-generator
description: Create structured guitar chord, melody and tablature data and render Markdown and scores using the local Guitar Notation Generator.
---
# Guitar Notation Generator Skill

1. Create a JSON song file using examples/montmartre.json as a template.
2. JSON is authoritative; do not hand-draw diagrams in prose.
3. Run `guitar-notation render path/to/song.json --out output`.
4. Correct validation errors; do not claim success if validation fails.
5. Tell the user which musical assumptions remain uncertain.

## Data conventions
- Tuning: six pitches low string to high string, e.g. E2 A2 D3 G3 B3 E4.
- Chord voicing: six integers low E to high e; -1 muted, 0 open, positive integer fret.
- Tab string: standard numbering, 1 high e and 6 low E. Fret: 0–24.
- Melody: scientific pitches such as E4, F#5, Bb3.
- Duration: denominator 1, 2, 4, 8 or 16.
- Version 0.1 supports 4/4; event durations total four quarter-note beats per bar.

## Musical integrity
Do not invent missing notes/frets. Verify tab pitches against melody manually; automatic comparison is not yet implemented. Chord labels do not prove that voicings contain the correct chord tones. Mark uncertain arrangements as drafts.

## Agent integration
A local agent with terminal permission can invoke the CLI. Optional API:
`uvicorn guitar_notation.api:app --host 127.0.0.1 --port 8000`
POST JSON to `/validate` or `/render`. Cloud agents generally cannot access the user's localhost. Prefer CLI or a local MCP wrapper for local agents.
