import re
import uuid
from functools import lru_cache
from time import monotonic

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from services.agent import hitl, loop
from services.memory import images, runs, store
from services.observability.render import load_run
from services.observability.trace import RUN_ID_PATTERN
from services.ui.views import asset_page, index_page, queue_page, render_html, static_asset

ASSET_ID_PATTERN = re.compile(r"^[a-z0-9-]{1,64}$")
# ponytail: the Function URL rejects bodies over 6 MB anyway; this guard is for local uvicorn
MAX_UPLOAD_BYTES = 6 * 1024 * 1024

app = FastAPI(title="afterimage")


@app.get("/health")
def health():
    return {"ok": True}


def wants_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "")


@app.get("/")
def index():
    return HTMLResponse(index_page(store.list_assets()))


@app.get("/assets/{asset_id}")
def asset_history(asset_id: str):
    if not ASSET_ID_PATTERN.fullmatch(asset_id):
        raise HTTPException(status_code=404, detail="asset not found")
    return HTMLResponse(asset_page(asset_id, store.history(asset_id)))


async def _accept_capture(asset_id: str, image: UploadFile | None):
    if not ASSET_ID_PATTERN.fullmatch(asset_id):
        raise HTTPException(status_code=400, detail="asset_id must match [a-z0-9-]{1,64}")
    if image is None:
        raise HTTPException(status_code=400, detail="an image file is required")
    data = await image.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="image larger than 6 MB")
    try:
        return images.decode(data)
    except ValueError:
        raise HTTPException(status_code=400, detail="not a decodable image")


@app.post("/inspections")
async def create_inspection(request: Request, asset_id: str = Form(""),
                            image: UploadFile | None = File(None)):
    try:
        capture = await _accept_capture(asset_id, image)
    except HTTPException as rejected:
        if not wants_html(request):
            raise
        return HTMLResponse(index_page(store.list_assets(), error=str(rejected.detail)),
                            status_code=rejected.status_code)
    store.put_asset(asset_id)
    capture_key = images.put_image(asset_id, uuid.uuid4().hex[:12], "capture", capture)
    started = loop.start(asset_id, capture_key, runs_dir=runs.runs_dir())
    return RedirectResponse(f"/traces/{started['run_id']}", status_code=303)


@app.post("/runs/{run_id}/execute")
async def execute_run(run_id: str):
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise HTTPException(status_code=404, detail="run not found")
    try:
        result = await loop.resume(run_id, runs_dir=runs.runs_dir())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="run not found")
    except loop.AlreadyStarted:
        raise HTTPException(status_code=409, detail="run already started")
    return {"run_id": result.run_id, "status": result.status, "branch": result.branch}


# ponytail: list_assets is a table scan and the empty queue re-renders every 5 s, so the count is
# memoised per minute; a GSI or a counter item is the upgrade if the table ever grows
@lru_cache(maxsize=1)
def _assets_in_memory(minute: int) -> int:
    return len(store.list_assets())


@app.get("/queue")
def queue():
    pending = runs.pending(runs.runs_dir())
    settled = 0 if pending else _assets_in_memory(int(monotonic() // 60))
    return HTMLResponse(queue_page(pending, assets_in_memory=settled))


@app.post("/queue/{run_id}/{verdict}")
def resolve_pending(run_id: str, verdict: str):
    if verdict not in ("approve", "reject") or not RUN_ID_PATTERN.fullmatch(run_id):
        raise HTTPException(status_code=404, detail="not found")
    try:
        hitl.resolve(runs.runs_dir() / run_id, approved=verdict == "approve")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="nothing pending for this run")
    return RedirectResponse("/queue", status_code=303)


@app.get("/static/{name}")
def static(name: str):
    found = static_asset(name)
    if found is None:
        raise HTTPException(status_code=404, detail="asset not found")
    body, media_type = found
    return Response(
        body,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/images/{key:path}")
def image(key: str):
    try:
        images.ids_from_key(key)
        body = images.get_png(key)
    except ValueError:
        raise HTTPException(status_code=404, detail="image not found")
    return Response(body, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/traces/{run_id}")
def get_trace(run_id: str, request: Request):
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise HTTPException(status_code=404, detail="trace not found")
    run_dir = runs.runs_dir() / run_id
    state, events = load_run(run_dir)
    if not events:
        raise HTTPException(status_code=404, detail="trace not found")
    if wants_html(request) and request.query_params.get("format") != "json":
        return HTMLResponse(render_html(state, events))
    return {"state": state, "events": events}
