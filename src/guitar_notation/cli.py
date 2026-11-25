import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from .render import write_outputs
from .validation import check_song


def _load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:  # unreadable file or invalid JSON
        print(f"Could not read JSON: {e}", file=sys.stderr)
        return None


def _report(errors, warnings):
    for w in warnings:
        print(" ! " + w, file=sys.stderr)
    if errors:
        print("Validation failed:", file=sys.stderr)
        for e in errors:
            print(" - " + e, file=sys.stderr)


def main(argv=None):
    p = argparse.ArgumentParser(prog="guitar-notation",
                                description="Validate guitar song JSON and render Markdown, LilyPond and PDF.")
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check", help="validate only; print errors and warnings")
    c.add_argument("song")
    r = sub.add_parser("render", help="validate, then write .md and .ly and compile a PDF")
    r.add_argument("--no-midi", dest="no_midi", action="store_true", help="skip generating the 7-track backing MIDI file")
    r.add_argument("song")
    r.add_argument("--out", default="output")
    r.add_argument("--name", default="score")
    r.add_argument("--no-pdf", "--lilypond-only", dest="no_pdf", action="store_true",
                   help="write .md and .ly but do not run LilyPond")
    r.add_argument("--force", action="store_true", help="render even if validation reports errors")
    a = p.parse_args(argv)

    song = _load(a.song)
    if song is None:
        return 2
    errors, warnings = check_song(song)
    _report(errors, warnings)
    if a.command == "check":
        if not errors:
            print("OK: no errors" + (f", {len(warnings)} warning(s)" if warnings else ""))
        return 2 if errors else 0
    if errors and not a.force:
        return 2

    try:
        paths = write_outputs(song, a.out, a.name, warnings, include_midi=not a.no_midi)
    except Exception as e:
        print(f"Render failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 3
    print("Markdown:", paths["markdown"])
    print("LilyPond:", paths["lilypond"])
    if "midi" in paths:
        print("MIDI:", paths["midi"])
    exe = shutil.which("lilypond")
    if a.no_pdf:
        return 0
    if not exe:
        print("PDF skipped: install LilyPond (https://lilypond.org) to compile the .ly file.")
        return 0
    result = subprocess.run([exe, "-o", str(Path(a.out) / a.name), paths["lilypond"]],
                            capture_output=True, text=True)
    if result.returncode:
        print(result.stderr[-2500:], file=sys.stderr)
        return result.returncode
    print("PDF:", Path(a.out) / (a.name + ".pdf"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
