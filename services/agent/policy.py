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
IDENTIFIED = "identified"
UNIDENTIFIED = "unidentified"
BASELINE_VERIFIED = "baseline_verified"
BASELINE_DRIFT = "baseline_drift"
PHRASING_OK = "phrasing_ok"
PHRASING_REJECTED = "phrasing_rejected"
REJECTED_CAPTURE = "rejected_capture_artefact"
REJECTED_FINDING = "rejected_asset_finding"

SEVERITY_METRIC = "score"
HUMAN_GATE_METRIC = "human_approved"
REOBSERVE_METRIC = "baseline_consistent"
PHRASING_METRIC = "overstates"
REJECTION_METRIC = "capture_artefact"
AUDIT_METRICS = (REOBSERVE_METRIC, PHRASING_METRIC, REJECTION_METRIC)


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
    diff_delta_threshold: float = 30.0
    diff_min_region_area_ratio: float = 0.0005
    mean_delta_confirm: float = 35.0
    rescan_area_ratio_min: float = 0.02
    severity_full_scale_delta: float = 64.0
    severity_score_approve: float = 0.40
    identity_match_ratio: float = 0.80
    identity_votes_min: float = 20.0
    identity_vote_share_min: float = 0.50
    jev_floor: float = 0.80

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
        return decision(
            "area_ratio", m["largest_area_ratio"], p.diff_min_region_area_ratio, NO_CHANGE
        )
    top = m["regions"][0]
    branch = CROP_AND_RESCAN if top["mean_delta"] < p.mean_delta_confirm else CHANGE_CONFIRMED
    return decision(
        "mean_delta", top["mean_delta"], p.mean_delta_confirm, branch,
        bbox=top["bbox"], area_ratio=top["area_ratio"],
    )


def _evaluate_rescan(m: dict, p: Policy) -> dict:
    if not m["regions"]:
        return decision(
            "area_ratio", m["largest_area_ratio"], p.rescan_area_ratio_min, NO_CHANGE
        )
    top = m["regions"][0]
    zoom_area_ratio = top["zoom_area_ratio"]
    if zoom_area_ratio < p.rescan_area_ratio_min:
        return decision("zoom_area_ratio", zoom_area_ratio, p.rescan_area_ratio_min, NO_CHANGE)
    return decision(
        "zoom_area_ratio", zoom_area_ratio, p.rescan_area_ratio_min, CHANGE_CONFIRMED,
        bbox=top["bbox"], area_ratio=top["area_ratio"], zoom_area_ratio=zoom_area_ratio,
    )


def _evaluate_severity(m: dict, p: Policy) -> dict:
    branch = HUMAN_APPROVAL if m["score"] >= p.severity_score_approve else AUTO_WRITE
    return decision("score", m["score"], p.severity_score_approve, branch)


def _evaluate_identity(m: dict, p: Policy) -> dict:
    if m["votes"] < p.identity_votes_min:
        return decision("votes", m["votes"], p.identity_votes_min, UNIDENTIFIED)
    if m["vote_share"] < p.identity_vote_share_min:
        return decision("vote_share", m["vote_share"], p.identity_vote_share_min, UNIDENTIFIED)
    return decision(
        "vote_share", m["vote_share"], p.identity_vote_share_min, IDENTIFIED,
        asset_id=m["asset_id"],
    )


def _evaluate_reobserve(m: dict, p: Policy) -> dict:
    branch = BASELINE_VERIFIED if m[REOBSERVE_METRIC] >= 1.0 else BASELINE_DRIFT
    return decision(REOBSERVE_METRIC, m[REOBSERVE_METRIC], 1.0, branch, **m.get("extra", {}))


def _evaluate_phrasing(m: dict, p: Policy) -> dict:
    value = m[PHRASING_METRIC]
    branch = PHRASING_REJECTED if value >= p.jev_floor else PHRASING_OK
    return decision(PHRASING_METRIC, value, p.jev_floor, branch)


def _evaluate_rejection(m: dict, p: Policy) -> dict:
    value = m[REJECTION_METRIC]
    branch = REJECTED_CAPTURE if value >= p.jev_floor else REJECTED_FINDING
    return decision(REJECTION_METRIC, value, p.jev_floor, branch)


_STAGES = {
    "quality": _evaluate_quality,
    "alignment": _evaluate_alignment,
    "diff": _evaluate_diff,
    "rescan": _evaluate_rescan,
    "severity": _evaluate_severity,
    "identity": _evaluate_identity,
    "reobserve": _evaluate_reobserve,
    "phrasing": _evaluate_phrasing,
    "rejection": _evaluate_rejection,
}


def evaluate(stage: str, metrics: dict, policy: Policy) -> dict:
    if stage not in _STAGES:
        raise ValueError(f"unknown stage {stage!r}, expected one of {sorted(_STAGES)}")
    return _STAGES[stage](metrics, policy)
