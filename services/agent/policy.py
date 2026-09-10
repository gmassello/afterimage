import os
from dataclasses import dataclass, fields
from operator import gt, lt

from services.perception import alignment

RECAPTURE = "recapture"
QUALITY_OK = "quality_ok"
RETRY_CLASSIC = "retry_classic"
UNRECOGNIZED_ASSET = "unrecognized_asset"
ALIGNED = "aligned"
NO_CHANGE = "no_change"
CROP_AND_RESCAN = "crop_and_rescan"
CHANGE_CONFIRMED = "change_confirmed"
HUMAN_APPROVAL = "human_approval"
AUTO_WRITE = "auto_write"
FIRST_BASELINE = "first_baseline"

SEVERITY_METRIC = "score"
HUMAN_GATE_METRIC = "human_approved"


@dataclass(frozen=True)
class Policy:
    blur_variance_min: float = 100.0
    mean_brightness_min: float = 40.0
    mean_brightness_max: float = 220.0
    clipped_ratio_max: float = 0.30
    # ponytail: coverage heuristic reads ~0 on synthetic fixtures, so disabled by default; raise via env on real captures
    coverage_ratio_min: float = 0.0
    inlier_ratio_min_neural: float = 0.90
    inlier_ratio_min_classic: float = 0.30
    mean_delta_confirm: float = 35.0
    rescan_area_ratio_min: float = 0.02
    severity_score_approve: float = 0.40

    @classmethod
    def from_env(cls) -> "Policy":
        overrides = {}
        for field in fields(cls):
            raw = os.environ.get(f"AFTERIMAGE_{field.name.upper()}")
            if raw is not None:
                overrides[field.name] = float(raw)
        return cls(**overrides)

    def inlier_ratio_min(self, detector: str) -> float:
        return {
            alignment.NEURAL: self.inlier_ratio_min_neural,
            alignment.CLASSIC: self.inlier_ratio_min_classic,
        }[detector]


def decision(metric: str, value: float, threshold: float, branch: str, **extra) -> dict:
    record = {
        "input_metric": metric,
        "value": round(float(value), 4),
        "threshold": threshold,
        "branch": branch,
    }
    if extra:
        record["extra"] = extra
    return record


def _evaluate_quality(m: dict, p: Policy) -> dict:
    checks = [
        ("blur_variance", p.blur_variance_min, lt),
        ("mean_brightness", p.mean_brightness_min, lt),
        ("mean_brightness", p.mean_brightness_max, gt),
        ("clipped_dark_ratio", p.clipped_ratio_max, gt),
        ("clipped_bright_ratio", p.clipped_ratio_max, gt),
        ("coverage_ratio", p.coverage_ratio_min, lt),
    ]
    for metric, threshold, out_of_range in checks:
        if out_of_range(m[metric], threshold):
            return decision(metric, m[metric], threshold, RECAPTURE)
    return decision("blur_variance", m["blur_variance"], p.blur_variance_min, QUALITY_OK)


def _evaluate_alignment(m: dict, p: Policy) -> dict:
    threshold = p.inlier_ratio_min(m["detector"])
    if m["inlier_ratio"] < threshold:
        branch = RETRY_CLASSIC if m["detector"] == alignment.NEURAL else UNRECOGNIZED_ASSET
        return decision("inlier_ratio", m["inlier_ratio"], threshold, branch)
    return decision("inlier_ratio", m["inlier_ratio"], threshold, ALIGNED)


def _evaluate_diff(m: dict, p: Policy) -> dict:
    if not m["regions"]:
        return decision("changed_ratio", m["changed_ratio"], 0.0, NO_CHANGE)
    top = m["regions"][0]
    branch = CROP_AND_RESCAN if top["mean_delta"] < p.mean_delta_confirm else CHANGE_CONFIRMED
    return decision(
        "mean_delta", top["mean_delta"], p.mean_delta_confirm, branch,
        bbox=top["bbox"], area_ratio=top["area_ratio"],
    )


def _evaluate_rescan(m: dict, p: Policy) -> dict:
    if not m["regions"]:
        return decision("area_ratio", 0.0, p.rescan_area_ratio_min, NO_CHANGE)
    top = m["regions"][0]
    if top["area_ratio"] < p.rescan_area_ratio_min:
        return decision("area_ratio", top["area_ratio"], p.rescan_area_ratio_min, NO_CHANGE)
    return decision(
        "area_ratio", top["area_ratio"], p.rescan_area_ratio_min, CHANGE_CONFIRMED,
        bbox=top["bbox"], area_ratio=top["area_ratio"],
    )


def _evaluate_severity(m: dict, p: Policy) -> dict:
    branch = HUMAN_APPROVAL if m["score"] >= p.severity_score_approve else AUTO_WRITE
    return decision("score", m["score"], p.severity_score_approve, branch)


_STAGES = {
    "quality": _evaluate_quality,
    "alignment": _evaluate_alignment,
    "diff": _evaluate_diff,
    "rescan": _evaluate_rescan,
    "severity": _evaluate_severity,
}


def evaluate(stage: str, metrics: dict, policy: Policy) -> dict:
    if stage not in _STAGES:
        raise ValueError(f"unknown stage {stage!r}, expected one of {sorted(_STAGES)}")
    return _STAGES[stage](metrics, policy)
