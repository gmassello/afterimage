import uuid

import cv2
import pytest
from fastapi.testclient import TestClient

from services.api.app import app
from services.conftest import localstack
from services.memory import images, store
from services.perception.tests.panels import solar_panel

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
def test_upload_runs_the_loop_and_redirects_to_the_trace(client):
    asset_id = unique("api-upload")
    response = client.post(
        "/inspections",
        data={"asset_id": asset_id},
        files={"image": ("panel.png", png_bytes(PANEL), "image/png")},
    )
    assert response.status_code == 303
    trace_path = response.headers["location"]
    trace = client.get(trace_path)
    assert trace.status_code == 200
    events = trace.json()["events"]
    assert events[0]["type"] == "run_started"
    assert events[-1]["type"] == "run_finished"
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
    assert client.post(
        "/inspections",
        data={"asset_id": unique("api-bad")},
        files={"image": ("panel.png", b"not an image", "image/png")},
    ).status_code == 400


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
