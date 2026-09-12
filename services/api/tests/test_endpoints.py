import json
import re
import uuid

import cv2
import pytest
from fastapi.testclient import TestClient

from services.api.app import app
from services.conftest import localstack
from services.memory import images, store
from services.perception.tests.panels import solar_panel
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
def test_index_lists_assets(client):
    asset_id = unique("api-index")
    store.put_asset(asset_id)
    response = client.get("/")
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
    assert undecodable.json() == {"detail": "not a decodable image"}


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
def test_queue_flow(client, tmp_path):
    from services.agent import hitl

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
