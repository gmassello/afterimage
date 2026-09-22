import json
import re
import uuid
from datetime import datetime, timedelta, timezone

import cv2
import pytest
from fastapi.testclient import TestClient

from services.api.app import app
from services.conftest import localstack
from services.memory import images, runs, store
from services.perception.panels import solar_panel
from services.ui import views

PANEL = solar_panel(seed=0)


def unique(name):
    return f"{name}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AFTERIMAGE_RUNS_DIR", str(tmp_path))
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    return TestClient(app, follow_redirects=False)


def png_bytes(image):
    encoded, buffer = cv2.imencode(".png", image)
    assert encoded
    return buffer.tobytes()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@localstack
def test_dashboard_lists_assets(client):
    asset_id = unique("api-index")
    store.put_asset(asset_id)
    response = client.get("/app")
    assert response.status_code == 200
    assert asset_id in response.text


@localstack
def test_upload_opens_the_trace_before_the_loop_runs(client):
    asset_id = unique("api-upload")
    response = client.post(
        "/inspections",
        data={"asset_id": asset_id},
        files={"image": ("panel.png", png_bytes(PANEL), "image/png")},
    )
    assert response.status_code == 303
    trace_path = response.headers["location"]
    run_id = trace_path.rsplit("/", 1)[-1]

    opened = client.get(trace_path)
    assert opened.status_code == 200
    assert [event["type"] for event in opened.json()["events"]] == ["run_started"]
    assert "data-run-state='unstarted'" in client.get(trace_path, headers={"accept": "text/html"}).text

    assert client.post(f"/runs/{run_id}/execute").status_code == 200
    events = client.get(trace_path).json()["events"]
    assert events[-1]["type"] == "run_finished"
    assert client.post(f"/runs/{run_id}/execute").status_code == 409

    history_page = client.get(f"/assets/{asset_id}")
    assert history_page.status_code == 200
    assert "baseline" in history_page.text


@localstack
def test_upload_rejects_bad_input(client):
    ok_image = png_bytes(PANEL)
    assert client.post(
        "/inspections",
        data={"asset_id": "UPPER CASE"},
        files={"image": ("panel.png", ok_image, "image/png")},
    ).status_code == 400
    undecodable = client.post(
        "/inspections",
        data={"asset_id": unique("api-bad")},
        files={"image": ("panel.png", b"not an image", "image/png")},
    )
    assert undecodable.status_code == 400
    assert undecodable.json() == {
        "detail": "not a decodable image",
        "code": "invalid_image",
        "retryable": False,
    }
    oversized = client.post(
        "/inspections",
        data={"asset_id": unique("api-big")},
        files={"image": ("panel.png", b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR"
                         + (5712).to_bytes(4, "big") + (4284).to_bytes(4, "big"), "image/png")},
    )
    assert oversized.status_code == 413
    assert oversized.json()["code"] == "image_too_many_pixels"


@localstack
def test_a_browser_sees_a_rejected_upload_inside_the_page(client):
    asset_id = unique("api-html")
    browser = client.post(
        "/inspections",
        data={"asset_id": asset_id},
        files={"image": ("phone.heic", b"not an image", "image/heic")},
        headers={"accept": "text/html,application/xhtml+xml"},
    )
    assert browser.status_code == 400
    assert browser.headers["content-type"].startswith("text/html")
    assert "assets in memory" in browser.text

    missing = client.post("/inspections", data={"asset_id": asset_id},
                          headers={"accept": "text/html"})
    assert missing.status_code == 400
    assert "an image file is required" in missing.text

    gone = client.get("/traces/ffffffffffff", headers={"accept": "text/html"})
    assert gone.status_code == 404
    assert "assets in memory" not in gone.text


@localstack
def test_the_empty_queue_counts_what_memory_holds(client):
    store.put_asset(unique("api-count"))
    page = client.get("/queue")
    assert page.status_code == 200
    assert f"{len(store.list_assets())} asset" in page.text


@localstack
def test_the_polled_queue_lists_the_runs_prefix_once_per_window(client, monkeypatch):
    from services.api import app as api

    listings = []
    monkeypatch.setattr(runs, "pending", lambda root: listings.append(root) or [])
    api._pending_in_memory.cache_clear()
    client.get("/queue")
    client.get("/queue")
    assert len(listings) == 1


@localstack
def test_a_verdict_that_lost_the_race_is_refused(client, tmp_path):
    from services.agent import hitl

    run_id = uuid.uuid4().hex[:12]
    payload = {
        "run_id": run_id,
        "asset_id": unique("api-race"),
        "captured_at": "2026-08-26T00:00:00+00:00",
        "metrics": {"quality": {"blur_variance": 300.0}},
        "image_keys": {"capture": f"assets/panel/{run_id}/capture.png"},
    }
    hitl.request_approval(tmp_path / run_id, payload)
    assert client.post(f"/queue/{run_id}/reject").status_code == 303
    hitl.request_approval(tmp_path / run_id, payload)
    refused = client.post(f"/queue/{run_id}/approve")
    assert refused.status_code == 409
    assert refused.json()["code"] == "approval_already_resolved"


@localstack
def test_queue_flow(client, tmp_path):
    from services.agent import hitl
    from services.observability import trace

    asset_id = unique("api-queue")
    run_id = uuid.uuid4().hex[:12]
    capture_key = images.put_image(asset_id, run_id, "capture", PANEL)
    store.put_asset(asset_id)
    hitl.request_approval(tmp_path / run_id, {
        "run_id": run_id,
        "asset_id": asset_id,
        "captured_at": "2026-08-26T00:00:00+00:00",
        "metrics": {"quality": {"blur_variance": 300.0}},
        "image_keys": {"capture": capture_key},
        "message": "confirm the change",
    })
    queue = client.get("/queue")
    assert queue.status_code == 200
    assert run_id in queue.text
    resolved = client.post(f"/queue/{run_id}/approve")
    assert resolved.status_code == 303
    approval = trace.read_events(tmp_path / run_id)[-1]
    assert approval["input_metric"] == "human_approved"
    assert approval["extra"]["actor"]
    assert run_id not in client.get("/queue").text
    assert client.post(f"/queue/{run_id}/approve").status_code == 404
    skus = [item["sk"] for item in store.history(asset_id)]
    assert any(sk.startswith(store.INSPECTION) for sk in skus)
    assert any(sk.startswith(store.BASELINE) for sk in skus)


@localstack
def test_images_endpoint(client):
    asset_id = unique("api-image")
    key = images.put_image(asset_id, "insp", "capture", PANEL)
    response = client.get(f"/images/{key}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert client.get("/images/not/a/valid/key.png").status_code == 404
    assert client.get(f"/images/assets/{asset_id}/missing/capture.png").status_code == 404


@localstack
def test_a_thumbnail_costs_a_fraction_of_the_capture(client):
    key = images.put_image(unique("api-thumb"), "insp", "capture", PANEL)
    full = client.get(f"/images/{key}")
    thumb = client.get(f"/images/{key}?w=180")
    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/png"
    assert len(thumb.content) < len(full.content) / 4
    assert images.decode(thumb.content).shape[1] == 180
    assert client.get(f"/images/{key}?w=4000").status_code == 400


def test_queue_refresh_yields_to_an_in_flight_navigation(client):
    page = views.queue_page([])
    assert "data-poll='5000'" in page
    script = client.get(re.search(r"/static/app\.[0-9a-f]{8}\.js", page).group())
    assert script.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert "addEventListener('submit', halt, true)" in script.text
    assert "if (!live" in script.text
    assert "busy()" in script.text


def test_execute_guards_unknown_and_already_started_runs(client, tmp_path):
    assert client.post("/runs/not-a-run-id/execute").status_code == 404
    assert client.post("/runs/000000000000/execute").status_code == 404
    run_id = "abcdef123456"
    (tmp_path / run_id).mkdir()
    (tmp_path / run_id / "events.json").write_text(json.dumps([
        {"type": "run_started", "ts": "2026-08-26T12:00:00.000+00:00", "run_id": run_id,
         "asset_id": "seeded", "capture_key": f"seeded/{run_id}/capture.png"},
        {"type": "run_finished", "ts": "2026-08-26T12:00:01.000+00:00",
         "status": "completed", "branch": "no_change", "message": ""},
    ]))
    assert client.post(f"/runs/{run_id}/execute").status_code == 409


def test_asset_timeline_scores_every_inspection_against_the_threshold():
    page = views.asset_page("array-rooftop", [
        {"sk": store.META, "asset_id": "array-rooftop"},
        {"sk": f"{store.INSPECTION}7f2ac91b04de", "inspection_id": "7f2ac91b04de",
         "captured_at": "2026-08-26T12:04:11+00:00",
         "image_keys": {"capture": "array-rooftop/7f2ac91b04de/capture.png"},
         "metrics": {"severity": {"label": "crack", "score": 0.6543}},
         "verdict": {"input_metric": "score", "value": 0.6543, "threshold": 0.4,
                     "branch": "human_approval"}},
        {"sk": f"{store.BASELINE}c904ab21fe58", "inspection_id": "c904ab21fe58",
         "captured_at": "2026-08-12T08:02:44+00:00",
         "image_key": "array-rooftop/c904ab21fe58/capture.png"},
    ])
    assert "score 0.6543" in page
    assert "threshold 0.4" in page
    assert "crack" in page
    assert "current baseline" in page


def test_queue_entry_shows_the_compared_pair_and_the_changed_region():
    page = views.queue_page(
        [{
            "run_id": "7f2ac91b04de", "asset_id": "array-rooftop", "message": "severe crack",
            "image_keys": {"capture": "array-rooftop/7f2ac91b04de/capture.png",
                           "aligned": "array-rooftop/7f2ac91b04de/aligned.png",
                           "baseline": "array-rooftop/c904ab21fe58/capture.png"},
            "metrics": {
                "diff": {"regions": [{"bbox": [412, 208, 96, 64], "mean_delta": 41.88}]},
                "severity": {"label": "crack", "score": 0.6543},
            },
        }],
    )
    assert "/images/array-rooftop/c904ab21fe58/capture.png" in page
    assert "/images/array-rooftop/7f2ac91b04de/aligned.png" in page
    assert "[412, 208, 96, 64]" in page
    assert "score 0.6543" in page


@localstack
def test_the_language_asked_for_is_kept_in_a_cookie(client):
    response = client.get("/?lang=es")
    assert response.status_code == 200
    assert "<html lang='es'" in response.text
    assert response.cookies["afterimage-lang"] == "es"


@localstack
def test_the_cookie_carries_the_language_to_a_url_that_cannot_ask(client):
    client.get("/?lang=es")
    assert "<html lang='es'" in client.get("/queue").text


@localstack
def test_the_browser_preference_decides_until_someone_chooses(client):
    spanish = client.get("/", headers={"accept-language": "es-AR,es;q=0.9,en;q=0.8"})
    assert "<html lang='es'" in spanish.text
    assert "afterimage-lang" not in spanish.cookies
    assert "<html lang='en'" in client.get("/", headers={"accept-language": "fr,en"}).text


@localstack
def test_a_language_nobody_ships_is_ignored(client):
    response = client.get("/?lang=de")
    assert "<html lang='en'" in response.text
    assert "afterimage-lang" not in response.cookies


@localstack
def test_a_rejected_upload_explains_itself_in_the_language_of_the_page(client):
    response = client.post(
        "/inspections?lang=es",
        data={"asset_id": unique("api-es")},
        files={"image": ("note.txt", b"not an image", "text/plain")},
        headers={"accept": "text/html"},
    )
    assert response.status_code == 400
    assert "<html lang='es'" in response.text
    assert "no es una imagen decodificable" in response.text


def test_the_sample_captures_are_served_like_every_other_static_asset(client):
    for stem, _ in views.SAMPLES:
        name = next(n for n in views._assets() if n.startswith(stem + "."))
        response = client.get(f"/static/{name}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert "immutable" in response.headers["cache-control"]


@localstack
def test_the_register_asked_for_is_kept_in_its_own_cookie(client):
    response = client.get("/?register=tech")
    assert response.status_code == 200
    assert response.cookies["afterimage-register"] == "tech"
    assert "runs the policy would not write unattended" in client.get("/queue").text


@localstack
def test_a_first_visitor_reads_the_plain_register(client):
    page = client.get("/").text
    assert "services/agent/policy.py" not in page
    assert "<a href='?register=plain' class='here' aria-current='true'" in page


@localstack
def test_a_register_nobody_ships_is_ignored(client):
    response = client.get("/?register=cryptic")
    assert "afterimage-register" not in response.cookies
    assert "<a href='?register=plain' class='here' aria-current='true'" in response.text


@localstack
def test_the_two_choices_are_remembered_apart(client):
    client.get("/?lang=es")
    client.get("/?register=tech")
    page = client.get("/queue").text
    assert "<html lang='es'" in page
    assert "corridas que la política no escribiría sin supervisión" in page


def test_root_is_the_public_landing_and_app_is_the_dashboard(client, monkeypatch):
    monkeypatch.setattr(store, "list_assets", lambda: [])
    landing = client.get("/")
    dashboard = client.get("/app")
    assert landing.status_code == 200
    assert dashboard.status_code == 200
    assert "href='/app'" in landing.text
    assert "new inspection" in dashboard.text


def _failed_run(root, run_id="abcdef123456"):
    from services.observability import trace

    run_dir = root / run_id
    trace.emit(
        run_dir,
        "run_started",
        run_id=run_id,
        asset_id="panel-retry",
        capture_key="assets/panel-retry/capture/capture.png",
    )
    trace.emit(
        run_dir,
        "run_finished",
        status=trace.FAILED,
        branch=None,
        message="RuntimeError: unavailable",
    )
    return run_dir


def test_activity_lists_recent_runs_and_applies_filters(client, tmp_path):
    _failed_run(tmp_path)
    page = client.get("/activity?q=panel-retry&status=failed")
    assert page.status_code == 200
    assert "abcdef123456" in page.text
    assert "panel-retry" in page.text
    assert "/runs/abcdef123456/retry" in page.text
    assert "abcdef123456" not in client.get("/activity?status=completed").text


def test_failed_run_retry_is_idempotent_and_preserves_the_original(client, tmp_path):
    from services.observability import trace

    original_dir = _failed_run(tmp_path)
    original_events = trace.read_events(original_dir)

    first = client.post("/runs/abcdef123456/retry")
    second = client.post("/runs/abcdef123456/retry")
    assert first.status_code == 200
    assert first.json() == second.json()
    payload = first.json()
    assert payload == {
        "retry_of": "abcdef123456",
        "run_id": payload["run_id"],
        "status": "unstarted",
        "trace_url": f"/traces/{payload['run_id']}",
        "execute_url": f"/runs/{payload['run_id']}/execute",
    }
    assert trace.read_events(original_dir) == original_events
    retried = trace.read_events(tmp_path / payload["run_id"])
    assert [event["type"] for event in retried] == ["run_started"]
    assert retried[0]["retry_of"] == "abcdef123456"

    browser = client.post(
        "/runs/abcdef123456/retry",
        headers={"accept": "text/html"},
    )
    assert browser.status_code == 303
    assert browser.headers["location"] == payload["trace_url"]


def test_retry_rejects_unknown_and_non_failed_runs_with_structured_errors(client, tmp_path):
    from services.observability import trace

    unknown = client.post("/runs/000000000000/retry")
    assert unknown.status_code == 404
    assert unknown.json() == {
        "detail": "run not found",
        "code": "run_not_found",
        "retryable": False,
    }

    run_id = "111111111111"
    trace.emit(
        tmp_path / run_id,
        "run_started",
        run_id=run_id,
        asset_id="panel-active",
        capture_key="assets/panel-active/capture/capture.png",
    )
    conflict = client.post(f"/runs/{run_id}/retry")
    assert conflict.status_code == 409
    assert conflict.json() == {
        "detail": "only a failed run can be retried",
        "code": "run_not_failed",
        "retryable": False,
    }
    html = client.post(f"/runs/{run_id}/retry", headers={"accept": "text/html"})
    assert html.status_code == 409
    assert html.headers["content-type"].startswith("text/html")
    assert "run_not_failed" in html.text


def test_unhandled_errors_have_html_and_json_contracts(tmp_path, monkeypatch):
    monkeypatch.setenv("AFTERIMAGE_RUNS_DIR", str(tmp_path))
    monkeypatch.setattr(runs, "recent", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    safe_client = TestClient(app, raise_server_exceptions=False)

    json_error = safe_client.get("/activity")
    assert json_error.status_code == 500
    assert json_error.json() == {
        "detail": "the request could not be completed",
        "code": "internal_error",
        "retryable": False,
    }
    html_error = safe_client.get("/activity", headers={"accept": "text/html"})
    assert html_error.status_code == 500
    assert html_error.headers["content-type"].startswith("text/html")
    assert "internal_error" in html_error.text


@localstack
def test_a_browser_without_javascript_starts_the_run_from_the_trace_page(client):
    asset_id = unique("api-noscript")
    created = client.post(
        "/inspections",
        data={"asset_id": asset_id},
        files={"image": ("panel.png", png_bytes(PANEL), "image/png")},
    )
    trace_path = created.headers["location"]
    run_id = trace_path.rsplit("/", 1)[-1]
    page = client.get(trace_path, headers={"accept": "text/html"})
    assert f"<noscript><form method='post' action='/runs/{run_id}/execute'>" in page.text

    started = client.post(f"/runs/{run_id}/execute", headers={"accept": "text/html"})
    assert started.status_code == 303
    assert started.headers["location"] == trace_path
    assert client.get(trace_path).json()["events"][-1]["type"] == "run_finished"


def test_an_interrupted_run_is_closed_and_retried_once_it_goes_stale(client, tmp_path, monkeypatch):
    from services.observability import trace

    run_id = "cccccccccccc"
    aged = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(timespec="milliseconds")
    run_dir = tmp_path / run_id
    with monkeypatch.context() as clock:
        clock.setattr(trace, "now", lambda: aged)
        trace.emit(
            run_dir, "run_started", run_id=run_id, asset_id="panel-stuck",
            capture_key="assets/panel-stuck/capture/capture.png",
        )
        trace.emit(run_dir, "tool_call", tool="assess_quality", args={}, duration_ms=1.0)

    assert f"/runs/{run_id}/retry" in client.get("/activity?q=panel-stuck").text
    response = client.post(f"/runs/{run_id}/retry")
    assert response.status_code == 200
    assert response.json()["retry_of"] == run_id

    events = trace.read_events(run_dir)
    assert events[-1]["type"] == "run_finished"
    assert events[-1]["status"] == "failed"
    assert trace.broken_at(events) is None


@localstack
def test_the_demo_samples_write_to_one_asset_per_visitor(client):
    first = client.get("/app")
    suffix = first.cookies["demo"]
    assert re.fullmatch(r"[a-z0-9]{6}", suffix)
    assert f"data-asset='{views.SAMPLE_ASSET}-{suffix}'" in first.text
    assert f"data-asset='{views.SAMPLE_ASSET}-{suffix}'" in client.get("/app").text

    stranger = TestClient(app, follow_redirects=False).get("/app")
    assert stranger.cookies["demo"] != suffix
