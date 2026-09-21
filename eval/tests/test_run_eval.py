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
        "defect": run_eval.NO_DEFECT,
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


def test_a_crashing_scenario_does_not_discard_the_others(tmp_path, monkeypatch):
    monkeypatch.setattr(run_eval.store, "ensure_table", lambda: None)
    monkeypatch.setattr(run_eval.images, "ensure_bucket", lambda: None)
    monkeypatch.setattr(run_eval.scenarios_module, "load", lambda path: SCENARIOS)
    monkeypatch.setattr(run_eval, "run_scenario", fake_run_scenario)
    monkeypatch.setattr(sys, "argv", ["run_eval", "--out", str(tmp_path)])

    with pytest.raises(SystemExit) as exit_info:
        run_eval.main()

    results = json.loads((tmp_path / "results.json").read_text())
    assert [record["id"] for record in results["scenarios"]] == ["boom", "fine"]
    assert results["summary"]["scenarios"] == 2
    assert results["summary"]["passed"] == 1
    summary = (tmp_path / "summary.md").read_text()
    assert "RuntimeError: s3 is down" in summary
    assert "boom" in str(exit_info.value)
