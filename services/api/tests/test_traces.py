import json

import pytest
from fastapi.testclient import TestClient

from services.api.app import app
from services.observability.tests.sample_run import EVENTS, RUN_ID, STATE


@pytest.fixture
def client(tmp_path, monkeypatch):
    run_dir = tmp_path / RUN_ID
    run_dir.mkdir()
    (run_dir / "events.json").write_text(json.dumps(EVENTS))
    (run_dir / "state.json").write_text(json.dumps(STATE))
    monkeypatch.setenv("AFTERIMAGE_RUNS_DIR", str(tmp_path))
    return TestClient(app)


def test_json_trace_is_idempotent(client):
    first = client.get(f"/traces/{RUN_ID}")
    second = client.get(f"/traces/{RUN_ID}")
    assert first.status_code == 200
    assert first.json() == second.json() == {"state": STATE, "events": EVENTS}


def test_html_when_the_browser_asks_for_it(client):
    response = client.get(f"/traces/{RUN_ID}", headers={"accept": "text/html"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    for fragment in ("inlier_ratio", "0.259", "unrecognized_asset"):
        assert fragment in response.text


def test_unknown_run_is_404(client):
    assert client.get("/traces/000000000000").status_code == 404


def test_malformed_run_id_is_404(client):
    assert client.get("/traces/not-a-run-id").status_code == 404
    assert client.get("/traces/..%2F..%2Fetc").status_code == 404
    assert client.get(f"/traces/{RUN_ID.upper()}").status_code == 404
