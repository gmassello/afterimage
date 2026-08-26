import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from services.observability.render import load_run, render_html
from services.observability.trace import RUN_ID_PATTERN

app = FastAPI(title="afterimage")


@app.get("/traces/{run_id}")
def get_trace(run_id: str, request: Request):
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise HTTPException(status_code=404, detail="trace not found")
    run_dir = Path(os.environ.get("AFTERIMAGE_RUNS_DIR", "runs")) / run_id
    state, events = load_run(run_dir)
    if not events:
        raise HTTPException(status_code=404, detail="trace not found")
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse(render_html(state, events))
    return {"state": state, "events": events}
