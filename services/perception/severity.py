from dataclasses import dataclass

import cv2
import numpy as np

from services.perception.quality import gray

CRACK = "crack"
HOTSPOT = "hotspot"
SOILING = "soiling"
DELAMINATION = "delamination"
UNKNOWN = "unknown"

# Thresholds measured on the synthetic fixtures (see tests/test_severity.py):
#   crack        brightness -28.7  saturation  -6.0
#   hotspot      brightness +29.6  saturation -19.0   (bright, washed out towards white)
#   delamination brightness +54.1  saturation +46.4   (bright, shifted to another colour)
#   soiling      brightness +18.4  saturation -12.8   spread over most of the frame
BRIGHTNESS_DELTA_HOTSPOT = 12.0
BRIGHTNESS_DELTA_CRACK = -12.0
SATURATION_DELTA_DELAMINATION = 20.0
AREA_RATIO_SOILING = 0.25
FULL_SCALE_DELTA = 64.0


@dataclass(frozen=True)
class SeverityResult:
    label: str
    score: float
    features: dict[str, float]


def _mean_hsv(image: np.ndarray) -> tuple[float, float]:
    if image.ndim == 2:
        return 0.0, 0.0
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    return float(hsv[:, :, 0].mean()), float(hsv[:, :, 1].mean())


def _features(crop: np.ndarray, baseline_crop: np.ndarray, area_ratio: float) -> dict[str, float]:
    crop_gray, baseline_gray = gray(crop), gray(baseline_crop)
    delta = cv2.absdiff(crop_gray, baseline_gray)
    mean_delta = float(delta.mean())
    crop_hue, crop_saturation = _mean_hsv(crop)
    baseline_hue, baseline_saturation = _mean_hsv(baseline_crop)
    return {
        "brightness_delta": float(crop_gray.mean()) - float(baseline_gray.mean()),
        "saturation_delta": crop_saturation - baseline_saturation,
        "hue_shift": abs(crop_hue - baseline_hue),
        "spatial_uniformity": mean_delta / (float(delta.max()) or 1.0),
        "mean_delta": mean_delta,
        "area_ratio": area_ratio,
    }


def _label(features: dict[str, float]) -> str:
    # ponytail: threshold heuristic over OpenCV features. Upgrade to a small trained
    # classifier if the week 7 evaluation shows these do not separate the defect classes.
    if features["brightness_delta"] < BRIGHTNESS_DELTA_CRACK:
        return CRACK
    if features["saturation_delta"] > SATURATION_DELTA_DELAMINATION:
        return DELAMINATION
    if features["area_ratio"] > AREA_RATIO_SOILING:
        return SOILING
    if features["brightness_delta"] > BRIGHTNESS_DELTA_HOTSPOT:
        return HOTSPOT
    return UNKNOWN


def classify_severity(
    crop: np.ndarray, baseline_crop: np.ndarray, area_ratio: float
) -> SeverityResult:
    features = _features(crop, baseline_crop, area_ratio)
    return SeverityResult(
        label=_label(features),
        score=round(min(features["mean_delta"] / FULL_SCALE_DELTA, 1.0), 4),
        features={name: round(value, 4) for name, value in features.items()},
    )
