"""Markdown and LilyPond renderers for guitar-notation (v0.2).

Design: every output (staff, tab, markdown, chord diagrams) is built from the
same resolved events (resolve_event), so they cannot drift apart. Chord diagrams
live in their own invisible voice whose skips are timed from the music, so each
diagram sits above the beat where the chord changes.
"""
import re
from fractions import Fraction
from pathlib import Path

from .validation import (KEY_RE, STANDARD_TUNING, auto_position,
                         midi_note, note_name, parse_duration, parse_meter, tab_pitch,
                         voicing_notes)

STRING_LABELS = {1: "e", 2: "B", 3: "G", 4: "D", 5: "A", 6: "E"}
FLAT_MAJOR = {"F", "Bb", "Eb", "Ab", "Db", "Gb"}
FLAT_MINOR = {"D", "G", "C", "F", "Bb", "Eb"}


# --------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------
def _key_parts(song):
    m = KEY_RE.match(song["key_signature"]) if song.get("key_signature") else None
    if not m:
        return None
    return m.group(1).upper() + m.group(2).lower(), m.group(3).lower()


def use_flats(song):
    if song.get("accidentals") in ("sharps", "flats"):
        return song["accidentals"] == "flats"
    parts = _key_parts(song)
    if parts:
        tonic, mode = parts
        return tonic in (FLAT_MAJOR if mode == "major" else FLAT_MINOR)
    return False


def resolve_event(song, ev):
    """Return the sounding notes of an event, low to high, each with
    midi, name (spelled), string and fret. Empty list = rest."""
    tuning = song["tuning"]
    given = {midi_note(n): n for n in ev.get("melody", [])}
    if ev.get("play_chord") and ev.get("chord"):
        src = voicing_notes(tuning, ev["chord"]["voicing"])
    elif ev.get("tab"):
        src = sorted(({"string": t["string"], "fret": t["fret"],
                       "midi": tab_pitch(tuning, t["string"], t["fret"])} for t in ev["tab"]),
                     key=lambda n: (n["midi"], -n["string"]))
    else:
        src = []
        for m in sorted(given):
            pos = auto_position(tuning, m)
            src.append({"string": pos["string"], "fret": pos["fret"], "midi": m})
    flats = use_flats(song)
    for n in src:
        n["name"] = given.get(n["midi"]) or note_name(n["midi"], flats)
    return src


def _chord_key(c):
    return (c["name"], tuple(c["voicing"]))


def chord_changes(song):
    """[(offset_in_whole_notes, chord)] where a new diagram is shown, plus total length."""
    marks, pos, prev = [], Fraction(0), None
    for bar in song["bars"]:
        for ev in bar["events"]:
            c = ev.get("chord")
            if c and (prev is None or c.get("show") or _chord_key(c) != prev):
                marks.append((pos, c))
                prev = _chord_key(c)
            pos += parse_duration(ev["duration"])[1]
    return marks, pos


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------
def chord_ascii(name, voicing):
    """Chord box, low E on the left (same orientation as the voicing array)."""
    pos = [x for x in voicing if x > 0]
    start = 1 if not pos or max(pos) <= 4 else min(pos)
    last = max(start + 3, max(pos)) if pos else start + 3
    head = " ".join("x" if x == -1 else "o" if x == 0 else " " for x in voicing)
    lines = [f"      {name}", "      E A D G B e", "      " + head]
    for f in range(start, last + 1):
        lines.append(f"{f:>4}  " + " ".join("\u25cf" if x == f else "\u2502" for x in voicing))
    return "\n".join(lines)


def tab_ascii(song, bar, marks_by_event):
    """ASCII tab for one bar with chord names above the beat where they change."""
    cols = []
    for ei, ev in enumerate(bar["events"]):
        frets = {n["string"]: str(n["fret"]) for n in resolve_event(song, ev)}
        label = marks_by_event.get(id(ev), "")
        width = max(4, len(label) + 1, max((len(f) for f in frets.values()), default=1) + 2)
        cols.append((label, frets, width))
    out = ["    " + "".join(label.ljust(w) for label, _, w in cols)]
    for sn in range(1, 7):
        cells = "".join(("-" + frets[sn]).ljust(w, "-") if sn in frets else "-" * w
                        for _, frets, w in cols)
        out.append(f"  {STRING_LABELS[sn]}|{cells}|")
    return "\n".join(out)


def render_markdown(song, warnings=()):
    _, d, _ = parse_meter(song["meter"])
    out = [f"# {song['title']}", ""]
    if song.get("composer"):
        out += [f"*{song['composer']}*", ""]
    out += [f"**Key:** {song.get('key', 'Not specified')}  ",
            f"**Tempo:** {song['tempo']} BPM \u00b7 **Meter:** {song['meter']}  ",
            f"**Tuning:** {' '.join(song['tuning'])} (low to high, sounding pitch)  ",
            "**Conventions:** strings 1 (high e) to 6 (low E); voicings low E to high e; "
            "x = muted, o = open. Pitches are sounding pitch; the staff uses a treble_8 clef.", ""]
    if song.get("notes"):
        out += [f"> {song['notes']}", ""]
    for w in warnings:
        out.append(f"> Warning: {w}")
    if warnings:
        out.append("")

    shapes, order = {}, []
    for ei_bar, bar in enumerate(song["bars"], 1):
        for ev in bar["events"]:
            c = ev.get("chord")
            if c:
                k = _chord_key(c)
                if k not in shapes:
                    shapes[k] = {"chord": c, "bars": []}
                    order.append(k)
                if ei_bar not in shapes[k]["bars"]:
                    shapes[k]["bars"].append(ei_bar)
    out += ["## Chord shapes", ""]
    for k in order:
        c = shapes[k]["chord"]
        used = ", ".join(str(b) for b in shapes[k]["bars"])
        out += [f"### {c['name']}  (bar {used})", "",
                f"Voicing low E to high e: `{' '.join('x' if x == -1 else str(x) for x in c['voicing'])}`",
                "", "```text", chord_ascii(c["name"], c["voicing"]), "```", ""]

    # map event identity -> chord label when a new diagram starts there
    marks_by_event, prev = {}, None
    for bar in song["bars"]:
        for ev in bar["events"]:
            c = ev.get("chord")
            if c and (prev is None or c.get("show") or _chord_key(c) != prev):
                marks_by_event[id(ev)] = c["name"]
                prev = _chord_key(c)

    out += ["## Bars", ""]
    previous_section = None
    for bi, bar in enumerate(song["bars"], 1):
        section = bar.get("section")
        if section and section != previous_section:
            out += [f"### {section}", ""]
            previous_section = section
        out += [f"#### Bar {bi}", "", "| Beat | Chord | Notes | Melody | Tab (string/fret) |", "|---|---|---|---|---|"]
        offset = Fraction(0)
        for ev in bar["events"]:
            notes = resolve_event(song, ev)
            beat = f"{float(offset * d + 1):g}"
            chord = ev["chord"]["name"] if ev.get("chord") else ""
            names = " ".join(n["name"] for n in notes) or "rest"
            melody = " ".join(ev.get("melody", []))
            tabs = " ".join(f"{n['string']}/{n['fret']}" for n in notes) or "-"
            out.append(f"| {beat} | {chord} | {names} | {melody} | {tabs} |")
            offset += parse_duration(ev["duration"])[1]
        out += ["", "```text", tab_ascii(song, bar, marks_by_event), "```", ""]
    return "\n".join(out)


# --------------------------------------------------------------------------
# LilyPond
# --------------------------------------------------------------------------
def ly_str(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


def lpitch(note):
    m = re.match(r"^([A-G])([#b]?)(-?\d+)$", note)
    letter, acc, octs = m.groups()
    n = letter.lower() + ("is" if acc == "#" else "es" if acc == "b" else "")
    o = int(octs)
    return n + ("'" * (o - 3) if o >= 4 else "," * (3 - o))


# --------------------------------------------------------------------------
# LilyPond (Stacked Melody Staff + Chords Staff + Unified TabStaff)
# --------------------------------------------------------------------------
def _event_ly(notes, token, strings):
    """One LilyPond event. With strings=True each note carries its string hint."""
    if not notes:
        return "r" + token

    def hint(n):
        return "\\%d" % n["string"] if strings else ""
    if len(notes) == 1:
        return lpitch(notes[0]["name"]) + token + hint(notes[0])
    return "<" + " ".join(lpitch(n["name"]) + hint(n) for n in notes) + ">" + token


def _split_melody_and_chords(song, ev):
    """Split an event into (melody_notes, chord_notes) while keeping full notes for Tab."""
    full_notes = resolve_event(song, ev)
    if not full_notes:
        return [], [], []

    # Explicit melody field takes priority for the top Melody staff
    if ev.get("melody"):
        mel_midis = {midi_note(m) for m in ev["melody"]}
        melody_notes = [n for n in full_notes if n["midi"] in mel_midis]
        if not melody_notes:
            flats = use_flats(song)
            melody_notes = []
            for m in sorted(mel_midis):
                pos = auto_position(song["tuning"], m)
                melody_notes.append({"midi": m, "name": note_name(m, flats),
                                    "string": pos["string"], "fret": pos["fret"]})
    elif ev.get("play_chord") or len(full_notes) > 1:
        # In chord-melody events without explicit melody, top voice goes to Melody staff
        melody_notes = [full_notes[-1]]
    else:
        melody_notes = list(full_notes)

    # Chord staff gets full voicings whenever a chord is struck (or multi-note voicing plays)
    if ev.get("play_chord") and ev.get("chord"):
        chord_notes = list(full_notes)
    elif len(full_notes) > 1:
        chord_notes = list(full_notes)
    else:
        chord_notes = []

    return melody_notes, chord_notes, full_notes


def fret_markup(c):
    parts = []
    for sn, f in enumerate(reversed(c["voicing"]), 1):
        parts.append(f"(mute {sn})" if f == -1 else f"(open {sn})" if f == 0 else f"(place-fret {sn} {f})")
    return ('\\markup \\column { \\center-align "' + ly_str(c["name"]) +
            "\" \\fret-diagram-verbose #'( " + " ".join(parts) + " ) }")


def chord_voice(song):
    """Invisible voice of skips timed from the music; each change carries one diagram."""
    marks, total = chord_changes(song)
    unit = 64
    out = []
    first = marks[0][0] if marks else total
    if first > 0:
        out.append(f"s{unit}*{int(first * unit)}")
    for i, (pos, c) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else total
        out.append(f"s{unit}*{int((end - pos) * unit)}^{fret_markup(c)}")
    return "\n  ".join(out)


def _bars_per_line(song):
    n = (song.get("layout") or {}).get("bars_per_line")
    if isinstance(n, int) and n > 0:
        return n
    densest = max(sum(1 for ev in bar["events"] if ev.get("chord")) for bar in song["bars"])
    return 4 if densest <= 2 else 2


def _tonic_ly(tonic):
    letter, acc = tonic[0].lower(), tonic[1:]
    if acc == "#":
        return letter + "is"
    if acc == "b":
        return letter + "es"
    return letter


def render_lilypond(song):
    n, d, _ = parse_meter(song["meter"])
    nbars, bpl = len(song["bars"]), _bars_per_line(song)
    mel_staff, chd_staff, tabs = [], [], []
    for bi, bar in enumerate(song["bars"], 1):
        m_ev, c_ev, t_ev = [], [], []
        for ev in bar["events"]:
            token = parse_duration(ev["duration"])[0]
            mel_notes, chd_notes, full_notes = _split_melody_and_chords(song, ev)
            m_ev.append(_event_ly(mel_notes, token, False))
            c_ev.append(_event_ly(chd_notes, token, False))
            t_ev.append(_event_ly(full_notes, token, True))
        end = ' \\bar "|."' if bi == nbars else " |"
        brk = " \\break" if bi % bpl == 0 and bi < nbars else ""
        mel_staff.append(f"  % Bar {bi}\n  " + " ".join(m_ev) + end + brk)
        chd_staff.append(f"  % Bar {bi}\n  " + " ".join(c_ev) + end)
        tabs.append(f"  % Bar {bi}\n  " + " ".join(t_ev) + end)

    key = ""
    parts = _key_parts(song)
    if parts:
        key = f"\\key {_tonic_ly(parts[0])} \\{parts[1]} "
    tuned = ""
    if [midi_note(x) for x in song["tuning"]] != [midi_note(x) for x in STANDARD_TUNING]:
        pitches = " ".join(lpitch(x) for x in song["tuning"])
        tuned = f" stringTunings = \\stringTuning <{pitches}>"
    header = ['  title = "' + ly_str(song["title"]) + '"']
    if song.get("composer"):
        header.append('  composer = "' + ly_str(song["composer"]) + '"')
    header.append("  tagline = ##f")

    lines = ['\\version "2.24.0"', "", "\\header {", *header, "}", "",
             "\\paper {", '  #(set-paper-size "a4")', "  ragged-right = ##f", "  ragged-last = ##f", "}", "",
             "melodyStaff = {", *mel_staff, "}", "",
             "chordsStaff = {", *chd_staff, "}", "",
             "melodyTab = {", *tabs, "}", "",
             "chordDiagrams = {", "  " + chord_voice(song), "}", "",
             "\\score {", "  <<",
             '    \\new Staff = "melody" \\with { instrumentName = "Melody" } <<',
             '      \\new Voice = "notes" {',
             f'        \\clef "treble_8" \\time {n}/{d} {key}\\tempo 4 = {song["tempo"]}',
             "        \\melodyStaff", "      }",
             '      \\new Voice = "chords" { \\chordDiagrams }',
             "    >>",
             '    \\new Staff = "harmony" \\with { instrumentName = "Chords" } {',
             f'      \\clef "treble_8" \\time {n}/{d} {key}',
             "      \\chordsStaff",
             "    }",
             '    \\new TabStaff = "guitar" \\with { instrumentName = "Guitar"' + tuned + " } {",
             f"      \\clef moderntab \\time {n}/{d}", "      \\melodyTab", "    }",
             "  >>", "  \\layout { ragged-right = ##f }", "}"]
    return "\n".join(lines) + "\n"


def _clean_output_dir(out: Path):
    """Remove previous generated score artifacts so each prompt starts fresh."""
    if not out.exists():
        return
    for ext in ("*.md", "*.ly", "*.pdf", "*.mid"):
        for old_file in out.glob(ext):
            try:
                old_file.unlink()
            except OSError:
                pass


def write_outputs(song, outdir, stem="score", warnings=(), include_midi=True, clean_first=True):
    from .midi_arranger import write_midi

    out = Path(outdir)
    if clean_first:
        _clean_output_dir(out)
    out.mkdir(parents=True, exist_ok=True)
    md, ly = out / f"{stem}.md", out / f"{stem}.ly"
    md.write_text(render_markdown(song, warnings), encoding="utf-8")
    ly.write_text(render_lilypond(song), encoding="utf-8")
    result = {"markdown": str(md), "lilypond": str(ly)}
    if include_midi:
        mid = out / f"{stem}_full_band.mid"
        write_midi(song, mid)
        result["midi"] = str(mid)
    return result
