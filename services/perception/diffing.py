from dataclasses import dataclass

import cv2
import numpy as np

from services.perception.quality import gray

DELTA_THRESHOLD = 30
MIN_REGION_AREA_RATIO = 0.0005
BLUR_KERNEL = (7, 7)


@dataclass(frozen=True)
class ChangedRegion:
    bbox: tuple[int, int, int, int]
    area_px: int
    area_ratio: float
    mean_delta: float


@dataclass(frozen=True)
class DiffResult:
    regions: list[ChangedRegion]
    changed_ratio: float


def _normalized_gray(image: np.ndarray) -> np.ndarray:
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray(image))


def _delta_map(aligned: np.ndarray, baseline: np.ndarray) -> np.ndarray:
    return cv2.GaussianBlur(cv2.absdiff(aligned, baseline), BLUR_KERNEL, 0)


def diff_against_memory(
    aligned: np.ndarray, baseline: np.ndarray, valid_mask: np.ndarray | None = None
) -> DiffResult:
    # Pixels the homography never covered are black, and black against the baseline reads
    # as the largest change in the frame. Only the warp knows which those are.
    delta = _delta_map(_normalized_gray(aligned), _normalized_gray(baseline))
    if valid_mask is not None:
        delta = cv2.bitwise_and(delta, valid_mask)
    return _regions(delta)


def _regions(delta: np.ndarray) -> DiffResult:
    _, binary = cv2.threshold(delta, DELTA_THRESHOLD, 255, cv2.THRESH_BINARY)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)

    frame_area = float(delta.shape[0] * delta.shape[1])
    minimum_area = MIN_REGION_AREA_RATIO * frame_area
    regions = []
    for label in range(1, count):
        x, y, width, height, area = stats[label]
        if area < minimum_area:
            continue
        window = slice(y, y + height), slice(x, x + width)
        values = delta[window][labels[window] == label]
        regions.append(
            ChangedRegion(
                bbox=(int(x), int(y), int(width), int(height)),
                area_px=int(area),
                area_ratio=float(area) / frame_area,
                mean_delta=float(values.mean()),
            )
        )

    regions.sort(key=lambda region: region.area_px, reverse=True)
    return DiffResult(
        regions=regions,
        changed_ratio=float(np.count_nonzero(binary)) / frame_area,
    )


def crop_origin(bbox: tuple[int, int, int, int], margin: float) -> tuple[int, int]:
    x, y, width, height = bbox
    return max(x - int(width * margin), 0), max(y - int(height * margin), 0)


def crop_region(
    image: np.ndarray, bbox: tuple[int, int, int, int], margin: float = 0.15
) -> np.ndarray:
    x, y, width, height = bbox
    left, top = crop_origin(bbox, margin)
    right = min(x + width + int(width * margin), image.shape[1])
    bottom = min(y + height + int(height * margin), image.shape[0])
    return image[top:bottom, left:right]


def crop_and_rescan(
    aligned: np.ndarray,
    baseline: np.ndarray,
    bbox: tuple[int, int, int, int],
    margin: float = 0.15,
    scale: float = 2.0,
) -> DiffResult:
    # Normalize on the full frame, then crop. Running CLAHE on each crop independently
    # renormalizes them towards each other and erases the very defect being zoomed into.
    crops = [
        crop_region(_normalized_gray(image), bbox, margin) for image in (aligned, baseline)
    ]
    if any(crop.size == 0 for crop in crops):
        return DiffResult(regions=[], changed_ratio=0.0)

    enlarged = [
        cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC) for crop in crops
    ]
    rescanned = _regions(_delta_map(*enlarged))

    # Ratios stay relative to the crop — that is what the zoom measures. The bbox does not:
    # it comes back in full-frame coordinates so the agent can chain this into the next tool.
    left, top = crop_origin(bbox, margin)
    return DiffResult(
        regions=[
            ChangedRegion(
                bbox=(
                    int(left + region.bbox[0] / scale),
                    int(top + region.bbox[1] / scale),
                    int(region.bbox[2] / scale),
                    int(region.bbox[3] / scale),
                ),
                area_px=region.area_px,
                area_ratio=region.area_ratio,
                mean_delta=region.mean_delta,
            )
            for region in rescanned.regions
        ],
        changed_ratio=rescanned.changed_ratio,
    )
