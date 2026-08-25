from dataclasses import dataclass

import cv2
import numpy as np

CLIPPING_BINS = 4


@dataclass(frozen=True)
class QualityReport:
    blur_variance: float
    mean_brightness: float
    clipped_dark_ratio: float
    clipped_bright_ratio: float
    coverage_ratio: float


def gray(image: np.ndarray) -> np.ndarray:
    return image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def laplacian_variance(image: np.ndarray) -> float:
    return float(cv2.Laplacian(gray(image), cv2.CV_64F).var())


def _coverage_ratio(image: np.ndarray) -> float:
    # ponytail: bbox of the largest edge contour; swap for segmentation if week 7 evaluation
    # shows it misreads panels against cluttered backgrounds.
    edges = cv2.Canny(cv2.GaussianBlur(image, (5, 5), 0), 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 0.0
    _, _, width, height = cv2.boundingRect(max(contours, key=cv2.contourArea))
    return float(width * height) / float(image.shape[0] * image.shape[1])


def assess_quality(image: np.ndarray) -> QualityReport:
    monochrome = gray(image)
    return QualityReport(
        blur_variance=laplacian_variance(monochrome),
        mean_brightness=float(monochrome.mean()),
        clipped_dark_ratio=float((monochrome < CLIPPING_BINS).mean()),
        clipped_bright_ratio=float((monochrome >= 256 - CLIPPING_BINS).mean()),
        coverage_ratio=_coverage_ratio(monochrome),
    )
