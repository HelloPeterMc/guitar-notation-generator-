from pathlib import Path
import re
from .validation import tab_pitch

def chord_ascii(name,voicing):
    frets=list(reversed(voicing))
    positives=[x for x in frets if x>0]
    start=1 if not positives or min(positives)<=4 else min(positives)
    lines=[f"      {name}","     e B G D A E","     "+" ".join("X" if x==-1 else "O" if x==0 else str(x) for x in frets)]
    for f in range(start,start+4):
        lines.append(f"{f:>3}  "+" ".join("●" if x==f else "│" for x in frets))
    return "\\n".join(lines)

def render_markdown(song):
    out=[f"# {song['title']}","",f"**Key:** {song.get('key','Not specified')}  ",f"**Tempo:** {song['tempo']} BPM · **Meter:** {song['meter']}  ",f"**Tuning:** {' '.join(song['tuning'])} (low to high)","","JSON is the authoritative musical source. Review draft musical content before performance.",""]
    for i,bar in enumerate(song["bars"],1):
        out += [f"## Bar {i}",""]
        for ev in bar["events"]:
            c=ev.get("chord")
            if c:
                out += [f"### {c['name']}","",f"Voicing low E → high e: `{' '.join('x' if x==-1 else str(x) for x in c['voicing'])}`","","```text",chord_ascii(c["name"],c["voicing"]),"```",""]
            if ev.get("melody"): out.append("Melody: "+", ".join(ev["melody"]))
            if ev.get("tab"): out.append("Tab: "+" ".join(f"string {t['string']} fret {t['fret']}" for t in ev["tab"]))
            out.append("")
    return "\\n".join(out)

def lpitch(note):
    m=re.match(r"^([A-G])([#b]?)(-?\\d+)$",note)
    letter,acc,octs=m.groups()
    n=letter.lower()+("is" if acc=="#" else "es" if acc=="b" else "")
    o=int(octs)
    return n+("'"*(o-3) if o>=4 else ","*(3-o))

def ltab(song,string_no,fret):
    midi=tab_pitch(song["tuning"],string_no,fret)
    names=["c","cis","d","dis","e","f","fis","g","gis","a","ais","b"]
    o=midi//12-1
    return names[midi%12]+("'"*(o-3) if o>=4 else ","*(3-o))+f"\\\\{string_no}"

def fret_markup(c):
    parts=[]
    for sn,f in enumerate(reversed(c["voicing"]),1):
        parts.append(f"(mute {sn})" if f==-1 else f"(open {sn})" if f==0 else f"(place-fret {sn} {f})")
    return '\\\\markup \\\\column { \\\\center-align "'+c["name"]+'" \\\\fret-diagram-verbose #\\'('+" ".join(parts)+') }'

def render_lilypond(song):
    staff=[]; tabs=[]
    for bar in song["bars"]:
        for ev in bar["events"]:
            d=str(ev["duration"]); notes=ev.get("melody",[])
            p="r" if not notes else lpitch(notes[0]) if len(notes)==1 else "<"+" ".join(lpitch(x) for x in notes)+">"
            staff.append(p+d+("^"+fret_markup(ev["chord"]) if ev.get("chord") else ""))
            ts=ev.get("tab",[])
            tabs.append("<"+" ".join(ltab(song,t["string"],t["fret"]) for t in ts)+">"+d if ts else "r"+d)
        staff.append("|"); tabs.append("|")
    # Build LilyPond source without relying on external Python packages.
    lines=['\\\\version "2.24.0"', '\\\\header {', f'  title = "{song["title"].replace(chr(34), chr(92)+chr(34))}"', '  tagline = ##f', '}', '\\\\paper { #(set-paper-size "a4") }', '\\\\score {', '  <<', '    \\\\new Staff = "melody" \\\\with { instrumentName = "Melody" } {', '      \\\\clef treble \\\\time 4/4', f'      \\\\tempo 4 = {song["tempo"]}', '      '+' '.join(staff), '    }', '    \\\\new TabStaff = "guitar" \\\\with { instrumentName = "Guitar" } {', '      \\\\clef moderntab \\\\time 4/4', '      '+' '.join(tabs), '    }', '  >>', '  \\\\layout { }', '}']
    return "\\n".join(lines)+"\\n"

def write_outputs(song,outdir,stem="score"):
    out=Path(outdir); out.mkdir(parents=True,exist_ok=True)
    md=out/f"{stem}.md"; ly=out/f"{stem}.ly"
    md.write_text(render_markdown(song),encoding="utf-8")
    ly.write_text(render_lilypond(song),encoding="utf-8")
    return {"markdown":str(md),"lilypond":str(ly)}
