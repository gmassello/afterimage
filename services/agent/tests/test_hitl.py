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


def _decisions(run_dir):
    return [e for e in trace.read_events(run_dir) if e["type"] == "decision"]


def test_the_opposite_verdict_on_the_same_run_is_refused(tmp_path):
    run_dir = tmp_path / "abcdef123456"
    _pending(run_dir)
    hitl.resolve(run_dir, approved=False, actor="first")
    _pending(run_dir)
    with pytest.raises(hitl.AlreadyResolved):
        hitl.resolve(run_dir, approved=True, actor="second")
    assert [decision["extra"]["actor"] for decision in _decisions(run_dir)] == ["first"]


def test_repeating_the_same_verdict_records_one_decision(tmp_path):
    run_dir = tmp_path / "abcdef123456"
    _pending(run_dir)
    hitl.resolve(run_dir, approved=False, actor="first")
    _pending(run_dir)
    assert hitl.resolve(run_dir, approved=False, actor="second")["extra"]["actor"] == "first"
    assert len(_decisions(run_dir)) == 1
    assert not (run_dir / "pending.json").exists()


def test_a_failed_approval_keeps_its_claim_and_can_be_retried(tmp_path, monkeypatch):
    run_dir = tmp_path / "abcdef123456"
    _pending(run_dir)
    monkeypatch.setattr(hitl, "commit", lambda *args: (_ for _ in ()).throw(RuntimeError("down")))

    with pytest.raises(RuntimeError, match="down"):
        hitl.resolve(run_dir, approved=True)

    assert (run_dir / "pending.json").exists()
    assert (run_dir / "verdict.json").exists()
    with pytest.raises(hitl.AlreadyResolved):
        hitl.resolve(run_dir, approved=False)
    monkeypatch.setattr(hitl, "commit", lambda *args: True)
    assert hitl.resolve(run_dir, approved=True)["branch"] == hitl.APPROVED


def test_a_failure_after_the_commit_resumes_the_approval_instead_of_allowing_a_reject(
    tmp_path, monkeypatch
):
    run_dir = tmp_path / "abcdef123456"
    _pending(run_dir)
    commits = []
    monkeypatch.setattr(hitl, "commit", lambda *args: commits.append(args) or True)
    real_write = hitl.runs.write

    def failing_state(run_dir, name, data):
        if name == "state.json":
            raise RuntimeError("s3 5xx")
        real_write(run_dir, name, data)

    monkeypatch.setattr(hitl.runs, "write", failing_state)
    with pytest.raises(RuntimeError, match="s3 5xx"):
        hitl.resolve(run_dir, approved=True)
    monkeypatch.setattr(hitl.runs, "write", real_write)

    with pytest.raises(hitl.AlreadyResolved):
        hitl.resolve(run_dir, approved=False)
    assert hitl.resolve(run_dir, approved=True)["branch"] == hitl.APPROVED
    assert len(commits) == 2
    human = [d for d in _decisions(run_dir) if d["input_metric"] == "human_approved"]
    assert [d["branch"] for d in human] == [hitl.APPROVED]
    assert not (run_dir / "pending.json").exists()


def test_a_rejection_keeps_the_reviewer_reason(tmp_path, monkeypatch):
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    run_dir = tmp_path / "abcdef123456"
    _pending(run_dir)

    record = hitl.resolve(run_dir, approved=False, actor="ops", reason="glare on the glass")

    assert record["extra"] == {"actor": "ops", "reason": "glare on the glass"}
    assert hitl.runs.read(run_dir, "verdict.json")["reason"] == "glare on the glass"
    assert not [e for e in trace.read_events(run_dir) if e["type"] == "tool_call"]


@pytest.mark.parametrize("answer,branch,error", [
    ((0.93, None), "rejected_capture_artefact", None),
    ((0.2, None), "rejected_asset_finding", None),
    ((None, "HTTP 403"), None, "HTTP 403"),
])
def test_the_reason_is_classified_once_when_a_second_opinion_is_configured(
    tmp_path, monkeypatch, answer, branch, error
):
    run_dir = tmp_path / "abcdef123456"
    _pending(run_dir)
    monkeypatch.setattr(hitl.jev, "configured", lambda: True)
    monkeypatch.setattr(hitl.jev, "capture_artefact", lambda reason: answer)

    hitl.resolve(run_dir, approved=False, reason="glare on the glass")
    hitl.classify_rejection(run_dir, "glare on the glass")

    spans = [e for e in trace.read_events(run_dir) if e.get("tool") == hitl.JEV_REJECTION]
    assert len(spans) == 1
    assert (spans[0].get("policy") or {}).get("branch") == branch
    assert spans[0].get("error") == error


@pytest.mark.parametrize("promoted,current,stored,branch,observed", [
    (True, "abcdef123456", True, "baseline_verified", "promoted"),
    (False, "newer000000", True, "baseline_verified", "historical"),
    (True, "newer000000", True, "baseline_drift", "historical"),
    (True, "abcdef123456", False, "baseline_drift", "missing"),
])
def test_reobservation_compares_what_memory_holds_with_what_was_written(
    monkeypatch, promoted, current, stored, branch, observed
):
    key = "assets/panel-gate/abcdef123456/capture.png"
    monkeypatch.setattr(hitl.store, "baseline_at", lambda asset_id, captured_at: {
        "sk": f"BASELINE#{captured_at}", "inspection_id": "abcdef123456", "image_key": key,
    })
    monkeypatch.setattr(hitl.store, "current_baseline", lambda asset_id: {"inspection_id": current})
    monkeypatch.setattr(hitl.images, "exists", lambda image_key: stored)

    verdict = hitl.reobserve("panel-gate", "abcdef123456", "2026-09-12", promoted)

    assert verdict["branch"] == branch
    assert verdict["extra"]["observed"] == observed


def test_an_approval_records_the_reobservation_after_the_human_decision(tmp_path, monkeypatch):
    run_dir = tmp_path / "abcdef123456"
    _pending(run_dir)
    monkeypatch.setattr(hitl, "commit", lambda *args: True)
    monkeypatch.setattr(hitl, "reobserve", lambda asset_id, inspection_id, captured_at, promoted: {
        "input_metric": "baseline_consistent", "value": 1.0, "threshold": 1.0,
        "branch": "baseline_verified",
    })

    hitl.resolve(run_dir, approved=True)

    assert [d["branch"] for d in _decisions(run_dir)] == ["approved", "baseline_verified"]
