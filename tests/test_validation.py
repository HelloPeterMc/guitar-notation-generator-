import json
from pathlib import Path
from guitar_notation.validation import validate_song, tab_pitch
def sample():
    return json.loads((Path(__file__).parents[1]/"references/example.json").read_text())
def test_sample_schema():
    assert validate_song(sample()) == []
def test_bad_bar_duration():
    s=sample(); s["bars"][0]["events"][0]["duration"]=2
    assert any("durations add up" in e for e in validate_song(s))
def test_standard_tuning():
    assert tab_pitch(["E2","A2","D3","G3","B3","E4"],1,0)==64
    assert tab_pitch(["E2","A2","D3","G3","B3","E4"],6,0)==40
