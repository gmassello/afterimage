from mcp.server.mcpserver import MCPServer

from services.memory import images
from services.perception import alignment, diffing, quality, severity

server = MCPServer("afterimage")


def _bbox(raw: list[float]) -> tuple[int, int, int, int]:
    if len(raw) != 4:
        raise ValueError(f"bbox must be [x, y, w, h], got {raw!r}")
    return tuple(int(v) for v in raw)


def _diff_payload(result: diffing.DiffResult) -> dict:
    return {
        "changed_ratio": round(float(result.changed_ratio), 4),
        "regions": [
            {
                "bbox": list(region.bbox),
                "area_px": region.area_px,
                "area_ratio": round(float(region.area_ratio), 6),
                "mean_delta": round(float(region.mean_delta), 4),
            }
            for region in result.regions
        ],
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
    if result.warped is not None:
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
    result = diffing.diff_against_memory(
        images.get_image(aligned_key), images.get_image(baseline_key), valid_mask
    )
    return _diff_payload(result)


@server.tool()
def crop_and_rescan(aligned_key: str, baseline_key: str, bbox: list[float]) -> dict:
    result = diffing.crop_and_rescan(
        images.get_image(aligned_key), images.get_image(baseline_key), _bbox(bbox)
    )
    return _diff_payload(result)


@server.tool()
def classify_severity(aligned_key: str, baseline_key: str, bbox: list[float], area_ratio: float) -> dict:
    box = _bbox(bbox)
    result = severity.classify_severity(
        diffing.crop_region(images.get_image(aligned_key), box),
        diffing.crop_region(images.get_image(baseline_key), box),
        float(area_ratio),
    )
    return {
        "label": result.label,
        "score": float(result.score),
        "features": {name: float(value) for name, value in result.features.items()},
    }


if __name__ == "__main__":
    server.run("stdio")
