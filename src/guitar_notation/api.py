import tempfile
from pathlib import Path
from fastapi import FastAPI,HTTPException
from .validation import validate_song
from .render import write_outputs
app=FastAPI(title="Guitar Notation Generator",version="0.1.0")
@app.post("/validate")
def validate(payload:dict):
    errors=validate_song(payload)
    return {"valid":not errors,"errors":errors}
@app.post("/render")
def render(payload:dict):
    errors=validate_song(payload)
    if errors: raise HTTPException(status_code=422,detail=errors)
    folder=Path(tempfile.mkdtemp(prefix="guitar-notation-"))
    return write_outputs(payload,folder)
