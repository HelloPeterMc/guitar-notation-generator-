"""Validation and music-theory helpers for guitar-notation (v0.2).

CONVENTIONS (the JSON must follow these; the validator enforces them)
  * Every pitch is SOUNDING pitch in scientific notation (C4 = middle C).
    Standard tuning is E2 A2 D3 G3 B3 E4. The staff is engraved with a
    treble_8 clef, which is how LilyPond shows guitar's written octave.
  * `tuning` lists strings low -> high.
  * Strings are numbered 1 (high e) .. 6 (low E) in `tab`.
  * `voicing` arrays run low E -> high e; -1 = muted, 0 = open.
  * `tab` is the source of truth. `melody` must sound the same pitches.
"""
import re
from fractions import Fraction

PITCHES = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
           "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10,
           "Bb": 10, "B": 11}
SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
STANDARD_TUNING = ["E2", "A2", "D3", "G3", "B3", "E4"]
NOTE_RE = re.compile(r"^([A-G])([#b]?)(-?\d+)$")
KEY_RE = re.compile(r"^([A-G])([#b]?)\s+(major|minor)$", re.I)
KNOWN_EVENT_KEYS = {"duration", "chord", "melody", "tab", "play_chord"}
REQUIRED_FIELDS = ("title", "tempo", "meter", "tuning", "bars")


# --------------------------------------------------------------------------
# pitch and rhythm helpers
# --------------------------------------------------------------------------
def midi_note(note):
    m = NOTE_RE.match(note) if isinstance(note, str) else None
    if not m:
        raise ValueError(f"Invalid pitch {note!r}; use E4, F#5 or Bb3")
    name = m.group(1) + m.group(2)
    if name not in PITCHES:
        raise ValueError(f"Unsupported pitch spelling: {note}")
    return 12 * (int(m.group(3)) + 1) + PITCHES[name]


def note_name(midi, flats=False):
    names = FLAT_NAMES if flats else SHARP_NAMES
    return f"{names[midi % 12]}{midi // 12 - 1}"


def parse_duration(d):
    """Return (lilypond_token, Fraction_of_whole_note). Accepts 4, "4", "4."."""
    m = re.match(r"^(1|2|4|8|16)(\.{0,2})$", str(d)) if not isinstance(d, bool) else None
    if not m:
        raise ValueError(f"duration must be 1, 2, 4, 8 or 16 (optionally dotted, e.g. \"4.\"); got {d!r}")
    value = Fraction(1, int(m.group(1)))
    add = value
    for _ in m.group(2):
        add /= 2
        value += add
    return str(d), value


def parse_meter(meter):
    m = re.match(r"^([1-9]\d*)/(1|2|4|8|16)$", meter) if isinstance(meter, str) else None
    if not m or int(m.group(1)) == 0:
        raise ValueError(f"meter must look like 4/4, 3/4 or 6/8; got {meter!r}")
    n, d = int(m.group(1)), int(m.group(2))
    return n, d, Fraction(n, d)


def tab_pitch(tuning, string_no, fret):
    """Sounding MIDI pitch of a fretted note. string_no 1 = high e, 6 = low E."""
    return midi_note(tuning[6 - string_no]) + fret


def voicing_notes(tuning, voicing):
    """Sounding notes of a chord voicing (low E -> high e), sorted low to high."""
    out = []
    for i, fret in enumerate(voicing):
        if fret >= 0:
            out.append({"string": 6 - i, "fret": fret, "midi": midi_note(tuning[i]) + fret})
    return sorted(out, key=lambda n: (n["midi"], -n["string"]))


def auto_position(tuning, midi):
    """Lowest-fret (string, fret) for a pitch, or None if it is not playable."""
    for max_fret in (12, 24):
        best = None
        for sn in range(1, 7):
            fret = midi - midi_note(tuning[6 - sn])
            if 0 <= fret <= max_fret and (best is None or (fret, sn) < best):
                best = (fret, sn)
        if best:
            return {"string": best[1], "fret": best[0]}
    return None


# --------------------------------------------------------------------------
# chord-name analysis (catches names that don't match the voicing)
# --------------------------------------------------------------------------
_CHORD_RE = re.compile(r"^([A-G][#b]?)((?:6/9|[^/])*)(?:/([A-G][#b]?))?$")
_MODS = ("add13", "add11", "add9", "sus4", "sus2", "sus", "alt", "no5",
         "b13", "#11", "#9", "b9", "#5", "b5")


def chord_spec(name):
    """Describe which pitch classes a chord name allows/requires, or None if the
    name uses symbols we cannot parse (then the check is skipped with a warning)."""
    m = _CHORD_RE.match(name.strip())
    if not m:
        return None
    root, q, bass = m.groups()
    if root not in PITCHES or (bass and bass not in PITCHES):
        return None
    s = re.sub(r"[()\s,]", "", q)
    s = (s.replace("Maj", "maj").replace("min", "m").replace("\u0394", "maj7")
          .replace("\u2206", "maj7").replace("\u00b0", "dim").replace("\u00f8", "m7b5"))
    s = re.sub(r"^M(?=\d)", "maj", s)
    if s.startswith("-"):
        s = "m" + s[1:]
    if s.startswith("+"):
        s = "aug" + s[1:]

    quality = "major"
    for prefix, qual in (("maj", "maj"), ("dim", "dim"), ("aug", "aug"), ("m", "min")):
        if s.startswith(prefix):
            quality, s = qual, s[len(prefix):]
            break
    num = re.match(r"^(6/9|69|6|7|9|11|13|5)?", s).group(1) or ""
    s = s[len(num):]
    if quality == "maj" and not num:
        num = "7"

    third, fifth, seventh = 4, 7, None
    req, opt = set(), set()
    if quality == "dim":
        third, fifth = 3, 6
    elif quality == "min":
        third = 3
    elif quality == "aug":
        fifth = 8
    if num in ("6", "69", "6/9"):
        req.add(9)
        if num != "6":
            req.add(2)
    elif num in ("7", "9", "11", "13"):
        seventh = 9 if quality == "dim" else 11 if quality == "maj" else 10
        req.add(seventh)
        if num == "9":
            req.add(2)
        elif num == "11":
            req.add(5)
            opt.add(2)
        elif num == "13":
            req.add(9)
            opt.update((2, 5))
    elif num == "5":
        third = None

    while s:
        tok = next((t for t in _MODS if s.startswith(t)), None)
        if tok is None:
            return None
        s = s[len(tok):]
        if tok == "add13":
            req.add(9)
        elif tok == "add11":
            req.add(5)
        elif tok == "add9":
            req.add(2)
        elif tok in ("sus4", "sus"):
            third = None
            req.add(5)
        elif tok == "sus2":
            third = None
            req.add(2)
        elif tok == "alt":
            opt.update((1, 3, 6, 8))
            fifth = None
            if seventh is None:
                seventh = 10
                req.add(10)
        elif tok == "no5":
            fifth = None
        elif tok == "b13":
            req.add(8)
        elif tok == "#11":
            req.add(6)
        elif tok == "#9":
            req.add(3)
        elif tok == "b9":
            req.add(1)
        elif tok == "#5":
            fifth = 8
        elif tok == "b5":
            fifth = 6

    root_pc = PITCHES[root]
    rel_allowed = {0} | req | opt
    required = set(req)
    for x in (third, seventh):
        if x is not None:
            rel_allowed.add(x)
            required.add(x)
    if fifth is not None:
        rel_allowed.add(fifth)
    allowed = {(root_pc + x) % 12 for x in rel_allowed}
    bass_pc = PITCHES[bass] if bass else None
    if bass_pc is not None:
        allowed.add(bass_pc)
    return {"allowed": allowed, "required": {(root_pc + x) % 12 for x in required}, "bass": bass_pc}


def analyze_chord(name, midis):
    """Return None if the name can't be parsed, else (extra_pcs, missing_pcs, bass_wrong)."""
    spec = chord_spec(name)
    if spec is None:
        return None
    pcs = {m % 12 for m in midis}
    bass_wrong = spec["bass"] is not None and midis[0] % 12 != spec["bass"]
    return sorted(pcs - spec["allowed"]), sorted(spec["required"] - pcs), bass_wrong


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------
def _is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def _names(midis):
    return " ".join(note_name(m) for m in midis)


def _check_event(song, tuning_ok, where, ev):
    errors, warnings, value = [], [], None
    if not isinstance(ev, dict):
        return [f"{where}: event must be an object"], warnings, None
    for k in ev:
        if k not in KNOWN_EVENT_KEYS:
            warnings.append(f"{where}: unknown field '{k}' is ignored")
    try:
        _, value = parse_duration(ev.get("duration"))
    except ValueError as e:
        errors.append(f"{where}: {e}")
    tuning = song["tuning"] if tuning_ok else None

    melody_midis = []
    mel = ev.get("melody", [])
    if not isinstance(mel, list):
        errors.append(f"{where}: melody must be a list of pitches such as [\"E4\"]")
        mel = []
    for n in mel:
        try:
            melody_midis.append(midi_note(n))
        except ValueError as e:
            errors.append(f"{where}: {e}")

    tab_midis, tab = [], ev.get("tab", [])
    if not isinstance(tab, list):
        errors.append(f"{where}: tab must be a list of {{\"string\": n, \"fret\": n}}")
        tab = []
    seen = set()
    for t in tab:
        if not isinstance(t, dict) or not _is_int(t.get("string")) or not 1 <= t["string"] <= 6:
            errors.append(f"{where}: tab string must be 1 (high e) through 6 (low E)")
            continue
        if not _is_int(t.get("fret")) or not 0 <= t["fret"] <= 24:
            errors.append(f"{where}: tab fret must be 0-24")
            continue
        if t["string"] in seen:
            errors.append(f"{where}: tab uses string {t['string']} twice in one event")
            continue
        seen.add(t["string"])
        if tuning:
            tab_midis.append(tab_pitch(tuning, t["string"], t["fret"]))

    voicing_midis, chord_ok, c = [], False, ev.get("chord")
    if c is not None:
        if not isinstance(c, dict) or not isinstance(c.get("name"), str) or not c["name"].strip():
            errors.append(f"{where}: chord needs a 'name' string and a 'voicing' list")
        else:
            if "show" in c and not isinstance(c["show"], bool):
                errors.append(f"{where}: chord show must be true or false")
            v = c.get("voicing")
            if not isinstance(v, list) or len(v) != 6 or any(not _is_int(x) or x < -1 or x > 24 for x in v):
                errors.append(f"{where}: chord '{c['name']}' voicing must be six values, low E to high e "
                              f"(-1 = muted, 0-24 = fret)")
            elif all(x == -1 for x in v):
                errors.append(f"{where}: chord '{c['name']}' voicing has no sounding strings")
            else:
                chord_ok = True
                if tuning:
                    voicing_midis = [n["midi"] for n in voicing_notes(tuning, v)]
                    res = analyze_chord(c["name"], voicing_midis)
                    if res is None:
                        warnings.append(f"{where}: cannot verify chord name '{c['name']}' against its voicing")
                    else:
                        extra, missing, bass_wrong = res
                        if extra or missing or bass_wrong:
                            detail = []
                            if extra:
                                detail.append("notes not in the chord: " + " ".join(SHARP_NAMES[p] for p in extra))
                            if missing:
                                detail.append("missing: " + " ".join(SHARP_NAMES[p] for p in missing))
                            if bass_wrong:
                                detail.append("lowest note is not the slash-chord bass")
                            spelled = " ".join(SHARP_NAMES[m % 12] for m in voicing_midis)
                            errors.append(f"{where}: voicing {v} spells {spelled}, which does not match "
                                          f"'{c['name']}' ({'; '.join(detail)})")

    if "play_chord" in ev and not isinstance(ev["play_chord"], bool):
        errors.append(f"{where}: play_chord must be true or false")
    elif ev.get("play_chord"):
        if not chord_ok:
            errors.append(f"{where}: play_chord needs a valid chord voicing")
        if tab:
            errors.append(f"{where}: play_chord takes its tab from the voicing; remove 'tab'")
        elif tuning and melody_midis:
            for m in melody_midis:
                if auto_position(tuning, m) is None:
                    errors.append(f"{where}: {note_name(m)} cannot be played in this tuning (frets 0-24)")
    elif tuning:
        if melody_midis and tab_midis and sorted(melody_midis) != sorted(tab_midis):
            errors.append(f"{where}: melody sounds {_names(sorted(melody_midis))} but tab sounds "
                          f"{_names(sorted(tab_midis))}. Tab is the source of truth.")
        if melody_midis and not tab_midis:
            for m in melody_midis:
                if auto_position(tuning, m) is None:
                    errors.append(f"{where}: {note_name(m)} cannot be played in this tuning (frets 0-24)")
    return errors, warnings, value


def check_song(song):
    """Return (errors, warnings). Errors block rendering; warnings do not."""
    errors, warnings = [], []
    if not isinstance(song, dict):
        return ["The JSON must be a single object"], warnings
    for f in REQUIRED_FIELDS:
        if f not in song:
            errors.append(f"Missing required field: {f}")
    if errors:
        return errors, warnings

    if not isinstance(song["title"], str) or not song["title"].strip():
        errors.append("title must be a non-empty string")
    for field in ("composer", "key", "notes"):
        if field in song and not isinstance(song[field], str):
            errors.append(f"{field} must be a string")
    if not _is_int(song["tempo"]) or song["tempo"] <= 0:
        errors.append("tempo must be a positive integer")
    bar_len = None
    try:
        _, _, bar_len = parse_meter(song["meter"])
    except ValueError as e:
        errors.append(str(e))

    tuning_ok, tg = False, song["tuning"]
    if not isinstance(tg, list) or len(tg) != 6:
        errors.append("tuning must be six pitches, low string to high string (standard: E2 A2 D3 G3 B3 E4)")
    else:
        bad = False
        for p in tg:
            try:
                midi_note(p)
            except ValueError as e:
                errors.append(str(e))
                bad = True
        tuning_ok = not bad
        if tuning_ok and any(midi_note(tg[i]) >= midi_note(tg[i + 1]) for i in range(5)):
            warnings.append("tuning is not strictly ascending; list the lowest string first")

    if song.get("pitch_convention", "sounding") != "sounding":
        errors.append('pitch_convention must be "sounding" (this version only supports sounding pitch)')
    ks = song.get("key_signature")
    if ks is not None and not (isinstance(ks, str) and KEY_RE.match(ks)):
        errors.append('key_signature must look like "E minor" or "Bb major"')
    if song.get("accidentals") not in (None, "sharps", "flats"):
        errors.append('accidentals must be "sharps" or "flats"')
    if "layout" in song:
        layout = song["layout"]
        if not isinstance(layout, dict):
            errors.append("layout must be an object")
        elif "bars_per_line" in layout and (not _is_int(layout["bars_per_line"]) or layout["bars_per_line"] < 1):
            errors.append("layout bars_per_line must be a positive integer")

    bars = song["bars"]
    if not isinstance(bars, list) or not bars:
        return errors + ["bars must be a non-empty list"], warnings
    for bi, bar in enumerate(bars, 1):
        if not isinstance(bar, dict) or not isinstance(bar.get("events"), list) or not bar["events"]:
            errors.append(f"Bar {bi}: needs a non-empty 'events' list")
            continue
        if "section" in bar and (not isinstance(bar["section"], str) or not bar["section"].strip()):
            errors.append(f"Bar {bi}: section must be a non-empty string when supplied")
        total, durations_ok = Fraction(0), True
        for ei, ev in enumerate(bar["events"], 1):
            e, w, val = _check_event(song, tuning_ok, f"Bar {bi}, event {ei}", ev)
            errors += e
            warnings += w
            if val is None:
                durations_ok = False
            else:
                total += val
        if durations_ok and bar_len is not None and total != bar_len:
            n, d, _ = parse_meter(song["meter"])
            beats = float(total * d)
            errors.append(f"Bar {bi}: durations add up to {beats:g} beats of 1/{d}; "
                          f"{song['meter']} needs {n}. Every melody note must be present.")
    return errors, warnings


def validate_song(song):
    """Backward-compatible: errors only."""
    return check_song(song)[0]
