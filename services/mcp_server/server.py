import numpy as np
from mcp.server.mcpserver import MCPServer

from services.agent.policy import Policy
from services.memory import images, store
from services.perception import alignment, diffing, evidence, quality, recognition, severity

server = MCPServer("afterimage")


def _bbox(raw: list[float]) -> tuple[int, int, int, int]:
    if len(raw) != 4:
        raise ValueError(f"bbox must be [x, y, w, h], got {raw!r}")
    x, y, width, height = (int(v) for v in raw)
    if width <= 0 or height <= 0:
        raise ValueError(f"bbox width and height must be positive, got {raw!r}")
    return x, y, width, height


def _diff_payload(result: diffing.DiffResult) -> dict:
    return {
        "changed_ratio": round(float(result.changed_ratio), 4),
        "largest_area_ratio": round(float(result.largest_area_ratio), 6),
        "regions": [
            {
                "bbox": list(region.bbox),
                "area_px": region.area_px,
                "area_ratio": round(float(region.area_ratio), 6),
                "mean_delta": round(float(region.mean_delta), 4),
                **(
                    {"zoom_area_ratio": round(float(region.zoom_area_ratio), 6)}
                    if region.zoom_area_ratio is not None
                    else {}
                ),
            }
            for region in result.regions
        ],
    }


def _baseline_descriptors(image_key: str, detector: str) -> np.ndarray | None:
    key = images.sibling_key(image_key, f"descriptors-{detector.replace('+', '-')}.npy")
    stored = images.get_array(key)
    if stored is not None:
        return stored
    described = recognition.describe(images.get_image(image_key), detector)
    if described is not None:
        images.put_array(key, described)
    return described


# ponytail: descriptors are cached per baseline in S3, so identification costs one detector pass
# plus one small read per asset, and the ANNIndex is rebuilt on every call; persist the index
# itself (ANNIndex.save/load) once the fleet outgrows a few hundred assets
@server.tool()
def identify_asset(image_key: str, detector: str, candidates: list[str] | None = None) -> dict:
    wanted = set(candidates) if candidates is not None else None
    described = {}
    for asset in store.list_assets():
        asset_id = asset["asset_id"]
        if wanted is not None and asset_id not in wanted:
            continue
        baseline = store.current_baseline(asset_id)
        if baseline is not None and images.exists(baseline["image_key"]):
            described[asset_id] = _baseline_descriptors(baseline["image_key"], detector)
    result = recognition.identify(
        recognition.describe(images.get_image(image_key), detector),
        described,
        Policy.from_env().identity_match_ratio,
    )
    return {
        "detector": detector,
        "asset_id": result.asset_id,
        "votes": result.votes,
        "vote_share": round(float(result.vote_share), 4),
        "runner_up": result.runner_up,
        "runner_up_votes": result.runner_up_votes,
        "query_keypoints": result.query_keypoints,
        "candidates": result.candidates,
    }


@server.tool()
def assess_quality(image_key: str) -> dict:
    report = quality.assess_quality(images.get_image(image_key))
    return {
        "blur_variance": round(float(report.blur_variance), 4),
        "mean_brightness": round(float(report.mean_brightness), 4),
        "clipped_dark_ratio": round(float(report.clipped_dark_ratio), 6),
        "clipped_bright_ratio": round(float(report.clipped_bright_ratio), 6),
        "coverage_ratio": round(float(report.coverage_ratio), 6),
    }


@server.tool()
def align_to_baseline(image_key: str, baseline_key: str, detector: str) -> dict:
    result = alignment.align_to_baseline(
        images.get_image(image_key), images.get_image(baseline_key), detector
    )
    aligned_key = valid_mask_key = None
    if result.warped is not None and result.valid_mask is not None:
        asset_id, inspection_id = images.ids_from_key(image_key)
        aligned_key = images.put_image(asset_id, inspection_id, "aligned", result.warped)
        valid_mask_key = images.put_image(asset_id, inspection_id, "valid_mask", result.valid_mask)
    return {
        "detector": result.detector,
        "keypoints_query": result.keypoints_query,
        "keypoints_train": result.keypoints_train,
        "matches": result.matches,
        "inliers": result.inliers,
        "inlier_ratio": round(float(result.inlier_ratio), 4),
        "mean_reprojection_error": (
            None if result.mean_reprojection_error is None
            else round(float(result.mean_reprojection_error), 4)
        ),
        "aligned_key": aligned_key,
        "valid_mask_key": valid_mask_key,
    }


@server.tool()
def diff_against_memory(aligned_key: str, baseline_key: str, valid_mask_key: str | None = None) -> dict:
    valid_mask = quality.gray(images.get_image(valid_mask_key)) if valid_mask_key else None
    policy = Policy.from_env()
    result = diffing.diff_against_memory(
        images.get_image(aligned_key),
        images.get_image(baseline_key),
        valid_mask,
        delta_threshold=policy.diff_delta_threshold,
        min_region_area_ratio=policy.diff_min_region_area_ratio,
    )
    return _diff_payload(result)


@server.tool()
def crop_and_rescan(aligned_key: str, baseline_key: str, bbox: list[float]) -> dict:
    policy = Policy.from_env()
    result = diffing.crop_and_rescan(
        images.get_image(aligned_key),
        images.get_image(baseline_key),
        _bbox(bbox),
        delta_threshold=policy.diff_delta_threshold,
        min_region_area_ratio=policy.diff_min_region_area_ratio,
    )
    return _diff_payload(result)


@server.tool()
def classify_severity(aligned_key: str, baseline_key: str, bbox: list[float], area_ratio: float) -> dict:
    box = _bbox(bbox)
    full = images.get_image(aligned_key)
    aligned = diffing.crop_region(full, box)
    baseline = diffing.crop_region(images.get_image(baseline_key), box)
    if aligned.size == 0 or baseline.size == 0:
        raise ValueError(f"bbox is outside image bounds: {bbox!r}")
    result = severity.classify_severity(
        aligned,
        baseline,
        float(area_ratio),
        full_scale_delta=Policy.from_env().severity_full_scale_delta,
    )
    asset_id, inspection_id = images.ids_from_key(aligned_key)
    annotated = evidence.annotate(
        full, box, f"{result.label} · score {result.score:.2f} · Δ{result.features['brightness_delta']:+.0f}"
    )
    return {
        "label": result.label,
        "score": float(result.score),
        "features": {name: float(value) for name, value in result.features.items()},
        "evidence_key": images.put_image(asset_id, inspection_id, "evidence", annotated),
    }


if __name__ == "__main__":
    server.run("stdio")
