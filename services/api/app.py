import logging
import re
import uuid
from functools import lru_cache
from hashlib import sha256
from time import monotonic

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from services.agent import hitl, loop
from services.memory import images, runs, store
from services.observability import trace
from services.observability.render import load_run
from services.observability.trace import RUN_ID_PATTERN, broken_at
from services.ui.text import DEFAULT_LANG, DEFAULT_REGISTER, LANGS, REGISTERS, strings
from services.ui.views import (
    THUMB_WIDTH,
    activity_page,
    asset_page,
    error_page,
    index_page,
    landing_page,
    queue_page,
    render_html,
    static_asset,
)

ASSET_ID_PATTERN = re.compile(r"^[a-z0-9-]{1,64}$")
LANG_COOKIE = "afterimage-lang"
REGISTER_COOKIE = "afterimage-register"
CHOICE_MAX_AGE = 365 * 24 * 3600
CHOICES = ((LANG_COOKIE, "lang", LANGS), (REGISTER_COOKIE, "register", REGISTERS))
# ponytail: the Function URL rejects bodies over 6 MB anyway; this guard is for local uvicorn
MAX_UPLOAD_BYTES = 6 * 1024 * 1024

logger = logging.getLogger(__name__)
app = FastAPI(title="afterimage")


class ApiError(HTTPException):
    def __init__(self, status_code: int, detail: str, code: str,
                 retryable: bool = False, retry_url: str = ""):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code
        self.retryable = retryable
        self.retry_url = retry_url


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, rejected: StarletteHTTPException):
    code = getattr(rejected, "code", f"http_{rejected.status_code}")
    retryable = getattr(rejected, "retryable", False)
    retry_url = getattr(rejected, "retry_url", "")
    payload = {"detail": str(rejected.detail), "code": code, "retryable": retryable}
    if wants_html(request):
        return HTMLResponse(
            error_page(
                rejected.status_code,
                code,
                str(rejected.detail),
                retryable=retryable,
                retry_url=retry_url,
                lang=language(request),
                register=register(request),
            ),
            status_code=rejected.status_code,
        )
    return JSONResponse(payload, status_code=rejected.status_code)


@app.exception_handler(Exception)
async def internal_error(request: Request, error: Exception):
    logger.error(
        "Unhandled request error",
        exc_info=(type(error), error, error.__traceback__),
    )
    detail = "the request could not be completed"
    payload = {"detail": detail, "code": "internal_error", "retryable": False}
    if wants_html(request):
        return HTMLResponse(
            error_page(
                500,
                "internal_error",
                detail,
                lang=language(request),
                register=register(request),
            ),
            status_code=500,
        )
    return JSONResponse(payload, status_code=500)


@app.get("/health")
def health():
    return {"ok": True}


def wants_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "")


def _offered(header: str) -> str:
    for chunk in header.split(","):
        code = chunk.split(";")[0].strip().lower()[:2]
        if code in LANGS:
            return code
    return DEFAULT_LANG


def _chosen(request: Request, param: str, cookie: str, allowed, fallback: str) -> str:
    asked = request.query_params.get(param, "")
    if asked in allowed:
        return asked
    saved = request.cookies.get(cookie, "")
    return saved if saved in allowed else fallback


def language(request: Request) -> str:
    preferred = _offered(request.headers.get("accept-language", ""))
    return _chosen(request, "lang", LANG_COOKIE, LANGS, preferred)


def register(request: Request) -> str:
    return _chosen(request, "register", REGISTER_COOKIE, REGISTERS, DEFAULT_REGISTER)


@app.middleware("http")
async def remember_choices(request: Request, call_next):
    answer = await call_next(request)
    for cookie, param, allowed in CHOICES:
        asked = request.query_params.get(param, "")
        if asked in allowed and request.cookies.get(cookie) != asked:
            answer.set_cookie(cookie, asked, max_age=CHOICE_MAX_AGE, samesite="lax")
    return answer


@app.get("/")
def landing(lang: str = Depends(language), reading: str = Depends(register)):
    return HTMLResponse(landing_page(lang=lang, register=reading))


@app.get("/app")
def index(lang: str = Depends(language), reading: str = Depends(register)):
    return HTMLResponse(index_page(store.list_assets(), lang=lang, register=reading))


@app.get("/activity")
def activity(q: str = "", status: str = "", lang: str = Depends(language),
             reading: str = Depends(register)):
    items = runs.recent(runs.runs_dir(), limit=50, q=q, status=status)
    return HTMLResponse(
        activity_page(items, q=q, status=status, lang=lang, register=reading)
    )


@app.get("/assets/{asset_id}")
def asset_history(asset_id: str, lang: str = Depends(language),
                  reading: str = Depends(register)):
    if not ASSET_ID_PATTERN.fullmatch(asset_id):
        raise ApiError(404, "asset not found", "asset_not_found")
    return HTMLResponse(
        asset_page(asset_id, store.history(asset_id), lang=lang, register=reading)
    )


async def _accept_capture(asset_id: str, image: UploadFile | None, t: dict):
    if not ASSET_ID_PATTERN.fullmatch(asset_id):
        raise ApiError(400, t["err_asset_id"], "invalid_asset_id")
    if image is None:
        raise ApiError(400, t["err_image_required"], "image_required")
    data = await image.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise ApiError(413, t["js_too_large"], "upload_too_large")
    try:
        return images.decode(data)
    except ValueError:
        raise ApiError(400, t["js_not_an_image"], "invalid_image")


@app.post("/inspections")
async def create_inspection(request: Request, asset_id: str = Form(""),
                            image: UploadFile | None = File(None),
                            lang: str = Depends(language),
                            reading: str = Depends(register)):
    try:
        capture = await _accept_capture(asset_id, image, strings(lang, reading))
    except ApiError as rejected:
        if not wants_html(request):
            raise
        return HTMLResponse(
            index_page(
                store.list_assets(),
                error=str(rejected.detail),
                asset_id=asset_id,
                lang=lang,
                register=reading,
            ),
            status_code=rejected.status_code,
        )
    store.put_asset(asset_id)
    capture_key = images.put_image(asset_id, uuid.uuid4().hex[:12], "capture", capture)
    started = loop.start(asset_id, capture_key, runs_dir=runs.runs_dir())
    return RedirectResponse(f"/traces/{started['run_id']}", status_code=303)


@app.post("/runs/{run_id}/execute")
async def execute_run(run_id: str):
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ApiError(404, "run not found", "run_not_found")
    try:
        result = await loop.resume(run_id, runs_dir=runs.runs_dir())
    except FileNotFoundError:
        raise ApiError(404, "run not found", "run_not_found")
    except loop.AlreadyStarted:
        raise ApiError(409, "run already started", "run_already_started")
    return {"run_id": result.run_id, "status": result.status, "branch": result.branch}


def _retry_payload(run_id: str, retry_of: str) -> dict:
    return {
        "retry_of": retry_of,
        "run_id": run_id,
        "status": trace.UNSTARTED,
        "trace_url": f"/traces/{run_id}",
        "execute_url": f"/runs/{run_id}/execute",
    }


@app.post("/runs/{run_id}/retry")
def retry_run(run_id: str, request: Request):
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ApiError(404, "run not found", "run_not_found")
    root = runs.runs_dir()
    original_dir = root / run_id
    events = trace.read_events(original_dir)
    started = trace.started_event(events)
    finished = next(
        (event for event in reversed(events) if event.get("type") == "run_finished"),
        None,
    )
    if started is None:
        raise ApiError(404, "run not found", "run_not_found")
    if finished is None or finished.get("status") != trace.FAILED:
        raise ApiError(409, "only a failed run can be retried", "run_not_failed")

    candidate = uuid.uuid4().hex[:12]
    created, marker = runs.write_once(
        original_dir,
        runs.RETRY,
        {"run_id": candidate, "retry_of": run_id},
    )
    retry_id = marker["run_id"]
    if created:
        try:
            trace.emit(
                root / retry_id,
                "run_started",
                run_id=retry_id,
                asset_id=started["asset_id"],
                capture_key=started["capture_key"],
                retry_of=run_id,
            )
        except Exception:
            runs.delete(original_dir, runs.RETRY)
            raise
    payload = _retry_payload(retry_id, run_id)
    if wants_html(request):
        return RedirectResponse(payload["trace_url"], status_code=303)
    return payload


# ponytail: list_assets is a table scan and the empty queue re-renders every 5 s, so the count is
# memoised per minute; a GSI or a counter item is the upgrade if the table ever grows
@lru_cache(maxsize=1)
def _assets_in_memory(minute: int) -> int:
    return len(store.list_assets())


@app.get("/queue")
def queue(lang: str = Depends(language), reading: str = Depends(register)):
    pending = runs.pending(runs.runs_dir())
    settled = 0 if pending else _assets_in_memory(int(monotonic() // 60))
    return HTMLResponse(
        queue_page(pending, assets_in_memory=settled, lang=lang, register=reading)
    )


def _actor(request: Request) -> str:
    # The trace is public, so the approver is recorded as a fingerprint rather than an address:
    # enough to tell two actors apart and to correlate approvals, not enough to identify anyone.
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    client = forwarded or (request.client.host if request.client else "unknown")
    fingerprint = f"{client}\n{request.headers.get('user-agent', '')}".encode()
    return sha256(fingerprint).hexdigest()[:12]


@app.post("/queue/{run_id}/{verdict}")
def resolve_pending(request: Request, run_id: str, verdict: str):
    if verdict not in ("approve", "reject") or not RUN_ID_PATTERN.fullmatch(run_id):
        raise ApiError(404, "not found", "approval_not_found")
    try:
        hitl.resolve(
            runs.runs_dir() / run_id,
            approved=verdict == "approve",
            actor=_actor(request),
        )
    except FileNotFoundError:
        raise ApiError(404, "nothing pending for this run", "approval_not_found")
    return RedirectResponse("/queue", status_code=303)


@app.get("/static/{name}")
def static(name: str):
    found = static_asset(name)
    if found is None:
        raise ApiError(404, "asset not found", "static_asset_not_found")
    body, media_type = found
    return Response(
        body,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/images/{key:path}")
def image(key: str, w: int | None = None):
    if w is not None and w != THUMB_WIDTH:
        raise ApiError(400, f"w must be {THUMB_WIDTH}", "invalid_image_width")
    try:
        images.ids_from_key(key)
        body = images.thumbnail_png(key, w) if w else images.get_png(key)
    except ValueError:
        raise ApiError(404, "image not found", "image_not_found")
    return Response(body, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


def chain_verdict(events: list[dict]) -> dict:
    broken = broken_at(events)
    return {"algorithm": "sha256", "verified": broken is None, "broken_at": broken}


@app.get("/traces/{run_id}")
def get_trace(run_id: str, request: Request, lang: str = Depends(language),
              reading: str = Depends(register)):
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ApiError(404, "trace not found", "trace_not_found")
    run_dir = runs.runs_dir() / run_id
    state, events = load_run(run_dir)
    if not events:
        raise ApiError(404, "trace not found", "trace_not_found")
    if wants_html(request) and request.query_params.get("format") != "json":
        return HTMLResponse(render_html(state, events, lang=lang, register=reading))
    return {"state": state, "events": events, "chain": chain_verdict(events)}
