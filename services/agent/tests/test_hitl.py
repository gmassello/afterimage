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
    assert [d["branch"] for d in _decisions(run_dir)] == [hitl.APPROVED]
    assert not (run_dir / "pending.json").exists()
