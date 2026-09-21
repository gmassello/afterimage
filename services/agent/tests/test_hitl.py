import pytest

from services.agent import hitl
from services.observability import trace


def _pending(run_dir):
    hitl.request_approval(run_dir, {
        "run_id": run_dir.name,
        "asset_id": "panel-gate",
        "captured_at": "2026-09-12T09:00:00.000+00:00",
        "metrics": {"quality": {"blur_variance": 300.0}},
        "image_keys": {"capture": "assets/panel-gate/abcdef123456/capture.png"},
    })


def test_a_second_verdict_on_the_same_run_is_refused(tmp_path):
    run_dir = tmp_path / "abcdef123456"
    _pending(run_dir)
    hitl.resolve(run_dir, approved=False, actor="first")
    _pending(run_dir)
    with pytest.raises(hitl.AlreadyResolved):
        hitl.resolve(run_dir, approved=False, actor="second")
    decisions = [e for e in trace.read_events(run_dir) if e["type"] == "decision"]
    assert [decision["extra"]["actor"] for decision in decisions] == ["first"]
