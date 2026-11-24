import argparse,json,shutil,subprocess,sys
from pathlib import Path
from .validation import validate_song
from .render import write_outputs
def main():
    p=argparse.ArgumentParser(prog="guitar-notation")
    s=p.add_subparsers(dest="command",required=True)
    r=s.add_parser("render"); r.add_argument("song"); r.add_argument("--out",default="output"); r.add_argument("--name",default="score"); r.add_argument("--no-pdf",action="store_true")
    a=p.parse_args()
    try: song=json.loads(Path(a.song).read_text(encoding="utf-8"))
    except Exception as e: print(f"Could not read JSON: {e}",file=sys.stderr); return 2
    errors=validate_song(song)
    if errors:
        print("Validation failed:",file=sys.stderr)
        for e in errors: print(" - "+e,file=sys.stderr)
        return 2
    paths=write_outputs(song,a.out,a.name)
    print("Markdown:",paths["markdown"]); print("LilyPond:",paths["lilypond"])
    exe=shutil.which("lilypond")
    if not a.no_pdf and exe:
        result=subprocess.run([exe,"-o",str(Path(a.out)/a.name),paths["lilypond"]],capture_output=True,text=True)
        if result.returncode: print(result.stderr[-2500:],file=sys.stderr); return result.returncode
        print("PDF:",Path(a.out)/(a.name+".pdf"))
    elif not a.no_pdf: print("PDF skipped: install LilyPond to compile .ly source.")
    return 0
if __name__=="__main__": raise SystemExit(main())
