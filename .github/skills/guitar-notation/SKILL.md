---
name: guitar-notation
description: Turn guitar song ideas (chords, melody, tab, chord-melody arrangements) into validated structured JSON and render a readable lead sheet with a melody staff, guitar tablature and chord-shape diagrams above the bars where chords change (LilyPond PDF), plus agent-friendly Markdown. Use whenever the user asks for guitar chords, melodies, riffs, tab, chord progressions, chord-melody or "sheet music / a score / a PDF" for guitar, or wants an AI-written guitar arrangement checked, fixed or made readable, even if they never say "JSON" or "LilyPond".
---

# Guitar notation

Pipeline: song JSON -> validator -> Markdown (for agents) + LilyPond `.ly` -> PDF (for musicians).
The validator exists because AI-written guitar material routinely contradicts itself. Do not skip it.

## Workflow
1. Read `references/agent-prompt.md` and follow its conventions when writing the song.
2. Write the song as JSON (`references/schema.json`; a verified full example is `references/example.json`). Prefer shapes from `references/verified-voicings.md`.
3. Validate: `PYTHONPATH=scripts python -m guitar_notation check song.json`
4. Fix every error by correcting the music, not by deleting the data. Warnings (for example an unparseable chord name) need a look but do not block.
5. Render: `PYTHONPATH=scripts python -m guitar_notation render song.json --out output --name score`
   Writes `score.md`, `score.ly`, `score_full_band.mid` (a 7-track Logic Pro-ready arrangement with Melody Guide, Guitar Reference, Keyboards, Electric Bass, Horn Section, String Ensemble, and Drums), and `score.pdf` if `lilypond` is installed. Without LilyPond, tell the user the `.ly` file is ready to compile (`lilypond score.ly`).
6. Report the files and any warnings. If the user supplied prose or ASCII tab instead of JSON, convert it first and say what you had to change to make it consistent.

Run from this skill's folder (or add its `scripts/` directory to `PYTHONPATH`). Tests: `python -m unittest discover -s scripts/tests`.

## Conventions
- All pitches are sounding pitch (C4 = middle C); standard tuning E2 A2 D3 G3 B3 E4, low to high. The staff is engraved with a `treble_8` clef, so written notes appear an octave above sounding pitch. Never store written pitch.
- Strings: 1 = high e ... 6 = low E. `voicing` arrays go low E -> high e; -1 muted, 0 open.
- `tab` is the source of truth; `melody` must sound the same pitches (the validator checks).
- A chord diagram appears at the event where `chord` is set and lasts until the next chord change; repeating the same chord adds no diagram unless `"show": true`.
- `"play_chord": true` plays the whole voicing (chord-melody). Its `melody` must be the top note and `tab` is derived.
- Bars must add up to the meter exactly. Durations: 1, 2, 4, 8, 16, dotted as `"4."`.

## Do not
- Invent fingerings or chord names you have not checked against the notes.
- Call a chord by a name the validator rejects. Fix the voicing or rename the chord.
- Edit the generated `.ly` by hand; fix the JSON and re-render.
- Silently drop melody notes to make a bar fit.

## Layout notes
Chord diagrams live in a separate invisible voice timed from the music, so each sits above its beat. If diagrams crowd each other, set `"layout": {"bars_per_line": 2}` in the JSON. Output was designed for LilyPond 2.24.

## Musical style & vibe
- Every song should evoke a **lo-fi, mellow, soft jazz / flamenco / warm 1960s tube amp & vinyl** aesthetic:
  - Favor extended and colorful voicings (`Em9`, `Cmaj7#11`, `Am9`, `B7b13`, `Fmaj7`, `Dm9`, `E7b9`, Andalusian cadences, and smooth voice-leading) over basic open power chords.
  - Keep melodies lyrical, expressive, and unhurried with space to breathe.
  - Include style keywords in `notes` (e.g., `"Lo-fi soft jazz / flamenco groove, warm 60s tube vibe"`) so the MIDI arranger selects the matching Mellotron flute, upright bass, brushed drums, and muted brass palette.
- Rendering automatically clears previous `.md`, `.ly`, `.pdf`, and `.mid` files in `--out` before writing the new score and 7-track MIDI file.
