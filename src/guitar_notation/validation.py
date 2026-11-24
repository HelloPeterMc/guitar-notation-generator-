import re
PITCHES = {"C":0,"C#":1,"Db":1,"D":2,"D#":3,"Eb":3,"E":4,"F":5,"F#":6,"Gb":6,"G":7,"G#":8,"Ab":8,"A":9,"A#":10,"Bb":10,"B":11}
NOTE_RE = re.compile(r"^([A-G])([#b]?)(-?\d+)$")
def midi_note(note):
    m = NOTE_RE.match(note)
    if not m: raise ValueError(f"Invalid pitch {note!r}; use E4, F#5 or Bb3")
    n = m.group(1)+m.group(2)
    if n not in PITCHES: raise ValueError(f"Unsupported pitch spelling: {note}")
    return 12*(int(m.group(3))+1)+PITCHES[n]
def validate_song(song):
    errors=[]
    for f in ("title","tempo","meter","tuning","bars"):
        if f not in song: errors.append(f"Missing required field: {f}")
    if errors: return errors
    if not isinstance(song["tempo"],int) or song["tempo"]<=0: errors.append("tempo must be a positive integer")
    if song["meter"]!="4/4": errors.append("Version 0.1 supports 4/4 only")
    if len(song["tuning"])!=6: errors.append("tuning must contain six pitches, low string to high string")
    else:
        for p in song["tuning"]:
            try: midi_note(p)
            except ValueError as e: errors.append(str(e))
    if not isinstance(song["bars"],list) or not song["bars"]: return errors+["bars must be a non-empty array"]
    for bi,bar in enumerate(song["bars"],1):
        total=0
        for ei,ev in enumerate(bar.get("events",[]),1):
            where=f"Bar {bi}, event {ei}"
            d=ev.get("duration")
            if d not in (1,2,4,8,16): errors.append(f"{where}: duration must be 1, 2, 4, 8 or 16")
            else: total+=4/d
            for n in ev.get("melody",[]):
                try: midi_note(n)
                except ValueError as e: errors.append(f"{where}: {e}")
            for t in ev.get("tab",[]):
                if not isinstance(t.get("string"),int) or not 1<=t["string"]<=6: errors.append(f"{where}: tab string must be 1 (high e) through 6 (low E)")
                if not isinstance(t.get("fret"),int) or not 0<=t["fret"]<=24: errors.append(f"{where}: tab fret must be 0–24")
            c=ev.get("chord")
            if c:
                v=c.get("voicing")
                if not isinstance(v,list) or len(v)!=6: errors.append(f"{where}: chord voicing must have six frets, low E to high e")
                elif any(not isinstance(x,int) or x < -1 or x>24 for x in v): errors.append(f"{where}: chord frets must be -1 (muted) or 0–24")
        if total!=4: errors.append(f"Bar {bi}: durations total {total:g} quarter-note beats; 4/4 requires 4")
    return errors
def tab_pitch(tuning,string_no,fret):
    return midi_note(tuning[6-string_no])+fret
