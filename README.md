# Guitar Notation Generator

Local-first Python starter project. Converts structured guitar-song JSON into Markdown chord diagrams, LilyPond source, and (when LilyPond is installed) printable PDF. The layout is inspired by the supplied *Near My House* reference: chord diagrams above treble staff at harmonic changes, extended with guitar tablature below the melody.

> Version 0.1: JSON validation, Markdown and LilyPond source generation are included. PDF depends on a separate LilyPond installation. Review all generated engraving; this is a starter, not publication-ready notation software.

## Local application?
Yes. The Python CLI runs on your computer without a cloud account or hosted service. The optional HTTP API is also local. A graphical frontend is deferred until the schema and renderer stabilize.

## Requirements
- Python 3.10+
- LilyPond 2.24+ for PDF
- Git recommended

Install LilyPond separately from https://lilypond.org/download.html; it is not a pip package. Check `python3 --version` and `lilypond --version`.

## Install
```bash
git clone <your-repository-url>
cd guitar-notation-generator
python3 -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```
Core CLI has no third-party Python dependencies.

Optional tests:
```bash
python -m pip install -e ".[dev]"
pytest
```
Optional API:
```bash
python -m pip install -e ".[api]"
```

## Quick start
```bash
guitar-notation render examples/montmartre.json --out output
```
Creates `output/score.md`, `output/score.ly`, and `output/score.pdf` if LilyPond is installed. Use `--no-pdf` to skip compilation. Without installing the console command:
```bash
PYTHONPATH=src python -m guitar_notation.cli render examples/montmartre.json --out output
```

## JSON conventions
- `tuning`: six pitches low string to high string.
- Chord `voicing`: six integers low E to high e; -1 muted, 0 open, positive integer fret.
- Tab `string`: 1 high e, 6 low E. `fret`: 0–24.
- Melody notes: scientific pitch names such as E4, F#5, Bb3.
- `duration`: denominator 1, 2, 4, 8 or 16.
- Version 0.1 supports 4/4; each bar totals four quarter-note beats.

Example event:
```json
{"duration":2,"chord":{"name":"Am","voicing":[-1,0,2,2,1,0]},"melody":["E5"],"tab":[{"string":1,"fret":0}]}
```

## Optional local HTTP API
Start with:
```bash
uvicorn guitar_notation.api:app --host 127.0.0.1 --port 8000
```
Validate:
```bash
curl -X POST http://127.0.0.1:8000/validate -H "Content-Type: application/json" --data-binary @examples/montmartre.json
```
Render:
```bash
curl -X POST http://127.0.0.1:8000/render -H "Content-Type: application/json" --data-binary @examples/montmartre.json
```
API returns local Markdown/LilyPond file paths; use CLI for PDF in this release.

### Can an AI Agent use localhost?
Only if its execution environment can reach your computer. A local agent with terminal/HTTP permission can call `127.0.0.1:8000`. A cloud agent normally cannot access your computer's localhost; giving it the URL alone does not grant access. Do not expose this unauthenticated API publicly. For local agents, CLI is simplest; a local MCP wrapper is a good next integration. A web frontend is for human editing/preview, not an agent connection by itself.

## Agent skill
Copy `skill/SKILL.md` into your agent's skill directory. The agent needs local filesystem and terminal permission to run the CLI.

## Architecture
```text
Song JSON -> Python validation/renderer -> Markdown
                                  -> LilyPond source -> LilyPond -> PDF
```

## Limitations
- 4/4 only; no dotted notes, ties, tuplets, pickups or complex subdivisions yet.
- Melody and tab are event-level collections; fine-grained rhythmic alignment within events is not implemented.
- Validator checks structure, pitch syntax, fret/string ranges and bar duration totals. It does not prove chord quality, fingering playability or tab/melody pitch equivalence.
- Markdown diagrams are text-based; PDF diagrams use LilyPond fret-diagram markup. Review engraving and spacing.
- Montmartre sample is a draft from the supplied AI conversation; chord, melody and tab details are not fully reconciled and are not a verified transcription.

## Roadmap
Richer rhythm model; automatic tab/melody and chord-tone checks; barre/finger-number diagrams; improved layout; MCP server; optional local web editor; MusicXML/MIDI.
Choose a repository license before publishing.
