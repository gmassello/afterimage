import pytest

from services.agent import policy as pol
from services.agent.policy import Policy, evaluate

CONTRACT_FIELDS = {"input_metric", "value", "threshold", "branch"}


def quality_metrics(**overrides):
    metrics = {
        "blur_variance": 500.0,
        "mean_brightness": 120.0,
        "clipped_dark_ratio": 0.0,
        "clipped_bright_ratio": 0.0,
        "coverage_ratio": 0.9,
    }
    metrics.update(overrides)
    return metrics


def test_pass_verdict_carries_the_contract_fields():
    decision = evaluate("quality", quality_metrics(), Policy())
    assert CONTRACT_FIELDS <= set(decision)
    assert decision["branch"] == pol.QUALITY_OK


def test_blur_triggers_recapture():
    decision = evaluate("quality", quality_metrics(blur_variance=10.0), Policy())
    assert decision == {
        "input_metric": "blur_variance",
        "value": 10.0,
        "threshold": Policy().blur_variance_min,
        "branch": pol.RECAPTURE,
    }


def test_overexposure_triggers_recapture():
    decision = evaluate("quality", quality_metrics(mean_brightness=240.0), Policy())
    assert decision["input_metric"] == "mean_brightness"
    assert decision["branch"] == pol.RECAPTURE


def test_threshold_is_per_detector():
    policy = Policy()
    neural = evaluate("alignment", {"detector": "aliked+lightglue", "inlier_ratio": 0.407}, policy)
    assert neural["branch"] == pol.RETRY_CLASSIC
    assert neural["threshold"] == policy.inlier_ratio_min_neural
    classic = evaluate("alignment", {"detector": "orb+bf", "inlier_ratio": 0.020}, policy)
    assert classic["branch"] == pol.UNRECOGNIZED_ASSET
    assert classic["threshold"] == policy.inlier_ratio_min_classic
    same_panel_orb = evaluate("alignment", {"detector": "orb+bf", "inlier_ratio": 0.409}, policy)
    assert same_panel_orb["branch"] == pol.ALIGNED
    assert same_panel_orb["value"] < policy.inlier_ratio_min_neural


def test_unknown_detector_raises():
    with pytest.raises(KeyError):
        evaluate("alignment", {"detector": "sift", "inlier_ratio": 0.5}, Policy())


def test_no_regions_is_no_change():
    decision = evaluate("diff", {"changed_ratio": 0.0, "regions": []}, Policy())
    assert decision["branch"] == pol.NO_CHANGE


def test_faint_change_triggers_rescan_with_bbox():
    region = {"bbox": [120, 60, 40, 40], "area_px": 1600, "area_ratio": 0.0008, "mean_delta": 22.0}
    decision = evaluate("diff", {"changed_ratio": 0.0008, "regions": [region]}, Policy())
    assert decision["branch"] == pol.CROP_AND_RESCAN
    assert decision["value"] == 22.0
    assert decision["extra"]["bbox"] == [120, 60, 40, 40]


def test_strong_change_is_confirmed_without_rescan():
    region = {"bbox": [0, 0, 10, 10], "area_px": 100, "area_ratio": 0.01, "mean_delta": 45.0}
    decision = evaluate("diff", {"changed_ratio": 0.01, "regions": [region]}, Policy())
    assert decision["branch"] == pol.CHANGE_CONFIRMED


def test_rescan_confirms_above_area_threshold():
    region = {"bbox": [0, 0, 10, 10], "area_px": 100, "area_ratio": 0.68, "mean_delta": 22.0}
    decision = evaluate("rescan", {"changed_ratio": 0.68, "regions": [region]}, Policy())
    assert decision["branch"] == pol.CHANGE_CONFIRMED


def test_rescan_dismisses_below_area_threshold():
    region = {"bbox": [0, 0, 2, 2], "area_px": 4, "area_ratio": 0.001, "mean_delta": 22.0}
    decision = evaluate("rescan", {"changed_ratio": 0.001, "regions": [region]}, Policy())
    assert decision["branch"] == pol.NO_CHANGE


def test_severity_gate_splits_on_score():
    policy = Policy()
    high = evaluate("severity", {"score": policy.severity_score_approve + 0.01}, policy)
    low = evaluate("severity", {"score": policy.severity_score_approve - 0.01}, policy)
    assert high["branch"] == pol.HUMAN_APPROVAL
    assert low["branch"] == pol.AUTO_WRITE


def test_env_override(monkeypatch):
    monkeypatch.setenv("AFTERIMAGE_BLUR_VARIANCE_MIN", "999")
    assert Policy.from_env().blur_variance_min == 999.0


def test_unknown_stage_raises():
    with pytest.raises(ValueError):
        evaluate("nonsense", {}, Policy())


def test_dispatch_tables_stay_consistent():
    from services.agent import loop

    assert set(loop.STAGE_OF.values()) == set(pol._STAGES)
    assert set(loop.NEXT_TOOL.values()) <= set(loop.STAGE_OF)
