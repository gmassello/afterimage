import json

from eval import harvest_rejections, smoke_jev
from services.agent import hitl
from services.memory import runs
from services.observability import trace


def test_the_smoke_score_ignores_calls_that_did_not_answer():
    rows = [(0.9, True), (0.85, False), (0.2, True), (None, True), (0.1, False)]

    assert smoke_jev.score(rows, 0.8) == {
        "answered": 4, "asked": 5, "recall": 0.5, "precision": 0.5,
    }
    assert smoke_jev.score([(None, True)], 0.8)["recall"] is None


def test_the_labelled_sentences_cover_both_answers():
    assert {truth for _, _, truth in smoke_jev.MESSAGES} == {True, False}
    assert {truth for _, truth in smoke_jev.REASONS} == {True, False}


def test_only_capture_artefacts_become_scenario_stubs(tmp_path, capsys, monkeypatch):
    for run_id, branch in (("aaaaaaaaaaaa", "rejected_capture_artefact"),
                           ("bbbbbbbbbbbb", "rejected_asset_finding")):
        run_dir = tmp_path / run_id
        trace.emit(run_dir, "run_started", run_id=run_id, asset_id="panel",
                   capture_key=f"assets/panel/{run_id}/capture.png")
        runs.write(run_dir, runs.VERDICT, {"approved": False, "reason": "glare"})
        trace.emit(run_dir, "tool_call", tool=hitl.JEV_REJECTION, args={}, duration_ms=1.0,
                   metrics={}, policy={"input_metric": "capture_artefact", "value": 0.9,
                                       "threshold": 0.8, "branch": branch})
    (tmp_path / "not-a-run.txt").write_text("")

    monkeypatch.setattr("sys.argv", ["harvest", "--runs", str(tmp_path)])
    harvest_rejections.main()
    stubs = json.loads(capsys.readouterr().out)

    assert [stub["source_run"] for stub in stubs] == ["aaaaaaaaaaaa"]
    assert stubs[0]["reason"] == "glare"
    assert stubs[0]["capture_key"] == "assets/panel/aaaaaaaaaaaa/capture.png"


def test_the_smoke_run_writes_what_it_measured(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(smoke_jev, "PAUSE_S", 0.0)
    monkeypatch.setattr(smoke_jev.jev, "configured", lambda: True)
    monkeypatch.setattr(smoke_jev.jev, "overstates", lambda message, verdict: (0.9, None))
    monkeypatch.setattr(smoke_jev.jev, "capture_artefact", lambda reason: (None, "HTTP 429"))
    out = tmp_path / "jev.json"
    monkeypatch.setattr("sys.argv", ["smoke_jev", str(out)])

    smoke_jev.main()

    report = json.loads(out.read_text())
    assert report["overstates"]["answered"] == len(smoke_jev.MESSAGES)
    assert report["capture_artefact"]["answered"] == 0
    assert report["errors"] == ["HTTP 429"] * len(smoke_jev.REASONS)
    assert "failed" in capsys.readouterr().err


def test_the_smoke_run_refuses_without_a_key(monkeypatch):
    monkeypatch.setattr(smoke_jev.jev, "configured", lambda: False)
    try:
        smoke_jev.main()
    except SystemExit as stop:
        assert "AI_GATEWAY_API_KEY" in str(stop)
    else:
        raise AssertionError("expected SystemExit")
