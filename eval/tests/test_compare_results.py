import json
from pathlib import Path

import pytest

from eval import compare_results

SUMMARY = {
    "scenarios": 29,
    "real": 18,
    "synthetic": 11,
    "passed": 25,
    "branch": {"accuracy": 0.8621, "macro": {"f1": 0.8624}},
    "defect": {"accuracy": 0.9, "macro": {"f1": 0.8753}},
    "localisation": {"mean_iou": 0.7875, "measured": 14, "at_least_half": 12},
}


def _variant(**changes) -> dict:
    summary = json.loads(json.dumps(SUMMARY))
    summary.update(changes)
    return summary


def _results(path: Path, summary: dict) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "results.json").write_text(json.dumps({"summary": summary, "scenarios": []}))
    return path


def test_float_noise_below_the_tolerance_passes(tmp_path):
    drifted = _variant()
    drifted["branch"]["accuracy"] = 0.8600
    drifted["localisation"]["mean_iou"] = 0.7900
    compare_results.main([
        str(_results(tmp_path / "published", SUMMARY)),
        str(_results(tmp_path / "measured", drifted)),
    ])


def test_a_changed_count_or_a_real_drift_is_rejected(tmp_path):
    published = str(_results(tmp_path / "published", SUMMARY))
    counted = str(_results(tmp_path / "counted", _variant(passed=24)))
    with pytest.raises(SystemExit) as fewer:
        compare_results.main([published, counted])
    assert "passed" in str(fewer.value)

    drifted = _variant()
    drifted["localisation"]["mean_iou"] = 0.7
    with pytest.raises(SystemExit) as moved:
        compare_results.main([published, str(_results(tmp_path / "drifted", drifted))])
    assert "mean_iou" in str(moved.value)


def test_a_region_that_stops_being_located_is_rejected_even_when_the_mean_improves(tmp_path):
    published = str(_results(tmp_path / "published", SUMMARY))
    lost = _variant()
    lost["localisation"] = {"mean_iou": 0.8131, "measured": 13, "at_least_half": 12}
    with pytest.raises(SystemExit) as fewer:
        compare_results.main([published, str(_results(tmp_path / "lost", lost))])
    assert "localisation.measured" in str(fewer.value)
