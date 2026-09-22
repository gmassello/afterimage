import json
import sys

import pytest

from eval import run_eval

SCENARIOS = [
    {"id": "boom", "base": {"kind": "synthetic"}, "expect": {"branch": "auto_write"}},
    {"id": "fine", "base": {"kind": "synthetic"}, "expect": {"branch": "recapture"}},
]


def fake_run_scenario(scenario, runs_dir):
    if scenario["id"] == "boom":
        raise RuntimeError("s3 is down")
    return {
        "id": scenario["id"],
        "source": "synthetic",
        "run_id": "r1",
        "status": "completed",
        "expected_branch": scenario["expect"]["branch"],
        "branch": scenario["expect"]["branch"],
        "branch_ok": True,
        "expected_defect": run_eval.NO_DEFECT,
        "score_defect": True,
        "defect": None,
        "severity_ran": False,
        "path": [scenario["expect"]["branch"]],
        "expected_in_path": [],
        "truth_bbox": None,
        "located_bbox": None,
        "iou": None,
        "quality": {},
        "deciding_number": "blur_variance 300.0 vs 100.0",
        "decisions": [],
        "defect_ok": True,
        "passed": True,
    }


def test_a_crashing_scenario_does_not_publish_results(tmp_path, monkeypatch):
    monkeypatch.setattr(run_eval.store, "ensure_table", lambda: None)
    monkeypatch.setattr(run_eval.images, "ensure_bucket", lambda: None)
    monkeypatch.setattr(run_eval.scenarios_module, "load", lambda path: SCENARIOS)
    monkeypatch.setattr(run_eval, "run_scenario", fake_run_scenario)
    monkeypatch.setattr(sys, "argv", ["run_eval", "--out", str(tmp_path)])

    with pytest.raises(SystemExit) as exit_info:
        run_eval.main()

    assert not (tmp_path / "results.json").exists()
    assert "boom" in str(exit_info.value)


def test_a_failed_tool_call_keeps_its_branch_instead_of_raising():
    events = [
        {"type": "tool_call", "tool": "assess_quality", "error": "S3 timed out"},
        {"type": "tool_call", "tool": "classify_severity", "error": "S3 timed out"},
    ]
    assert run_eval._quality_metrics(events) == {}
    assert run_eval._severity_label(events) == run_eval.CLASSIFICATION_ERROR


def test_an_abstention_on_a_real_defect_is_scored_as_missed(tmp_path, monkeypatch):
    def run(scenario, runs_dir):
        record = fake_run_scenario(scenario, runs_dir)
        if scenario["id"] == "missed":
            record.update(
                branch="recapture", branch_ok=False, expected_defect="hotspot",
                defect=run_eval.MISSED, defect_ok=False, passed=False,
            )
        if scenario["id"] == "seen":
            record.update(expected_defect="hotspot", defect="hotspot", severity_ran=True)
        return record

    monkeypatch.setattr(run_eval.store, "ensure_table", lambda: None)
    monkeypatch.setattr(run_eval.images, "ensure_bucket", lambda: None)
    monkeypatch.setattr(run_eval.scenarios_module, "load", lambda path: [
        {"id": name, "base": {"kind": "synthetic"}, "expect": {"branch": "human_approval"}}
        for name in ("fine", "seen", "missed")
    ])
    monkeypatch.setattr(run_eval, "run_scenario", run)
    monkeypatch.setattr(sys, "argv", ["run_eval", "--out", str(tmp_path)])

    run_eval.main()

    defect = json.loads((tmp_path / "results.json").read_text())["summary"]["defect"]
    assert defect["accuracy"] == 0.5
    assert set(defect["per_class"]) == {"hotspot", run_eval.MISSED}
    assert "| `missed` | human_approval / hotspot | recapture / MISSED |" in (
        tmp_path / "summary.md"
    ).read_text()
