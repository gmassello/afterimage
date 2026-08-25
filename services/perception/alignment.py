from dataclasses import dataclass
from functools import lru_cache

import cv2
import numpy as np

from services.perception.weights import aliked_path, lightglue_path

NEURAL = "aliked+lightglue"
CLASSIC = "orb+bf"
MIN_MATCHES = 4
RANSAC_REPROJECTION_THRESHOLD = 3.0
VALID_MASK_EROSION_KERNEL = np.ones((9, 9), np.uint8)


@dataclass(frozen=True)
class AlignmentResult:
    homography: np.ndarray | None
    warped: np.ndarray | None
    valid_mask: np.ndarray | None
    detector: str
    keypoints_query: int
    keypoints_train: int
    matches: int
    inliers: int
    inlier_ratio: float
    mean_reprojection_error: float | None


@lru_cache(maxsize=1)
def _aliked():
    return cv2.ALIKED.create(str(aliked_path()))


@lru_cache(maxsize=1)
def _lightglue():
    return cv2.LightGlueMatcher.create(str(lightglue_path()))


def _match_neural(query: np.ndarray, train: np.ndarray):
    detector = _aliked()
    query_keypoints, query_descriptors = detector.detectAndCompute(query, None)
    train_keypoints, train_descriptors = detector.detectAndCompute(train, None)
    if query_descriptors is None or train_descriptors is None:
        return query_keypoints, train_keypoints, []

    matcher = _lightglue()
    matcher.setPairInfo(
        cv2.KeyPoint.convert(query_keypoints),
        cv2.KeyPoint.convert(train_keypoints),
        (query.shape[1], query.shape[0]),
        (train.shape[1], train.shape[0]),
    )
    return query_keypoints, train_keypoints, matcher.match(query_descriptors, train_descriptors)


def _match_classic(query: np.ndarray, train: np.ndarray):
    detector = cv2.ORB.create(4000)
    query_keypoints, query_descriptors = detector.detectAndCompute(query, None)
    train_keypoints, train_descriptors = detector.detectAndCompute(train, None)
    if query_descriptors is None or train_descriptors is None:
        return query_keypoints, train_keypoints, []

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    return query_keypoints, train_keypoints, matcher.match(query_descriptors, train_descriptors)


MATCHERS = {NEURAL: _match_neural, CLASSIC: _match_classic}


def align_to_baseline(
    image: np.ndarray, baseline: np.ndarray, detector: str = NEURAL
) -> AlignmentResult:
    if detector not in MATCHERS:
        raise ValueError(f"unknown detector {detector!r}, expected one of {sorted(MATCHERS)}")

    image_keypoints, baseline_keypoints, matches = MATCHERS[detector](image, baseline)
    homography = mask = source = destination = None
    if len(matches) >= MIN_MATCHES:
        source = cv2.KeyPoint.convert(
            image_keypoints, [m.queryIdx for m in matches]
        ).reshape(-1, 1, 2)
        destination = cv2.KeyPoint.convert(
            baseline_keypoints, [m.trainIdx for m in matches]
        ).reshape(-1, 1, 2)
        homography, mask = cv2.findHomography(
            source, destination, cv2.USAC_MAGSAC, RANSAC_REPROJECTION_THRESHOLD
        )

    if homography is None:
        return AlignmentResult(
            homography=None,
            warped=None,
            valid_mask=None,
            detector=detector,
            keypoints_query=len(image_keypoints),
            keypoints_train=len(baseline_keypoints),
            matches=len(matches),
            inliers=0,
            inlier_ratio=0.0,
            mean_reprojection_error=None,
        )

    inlier_mask = mask.ravel() == 1
    errors = np.linalg.norm(
        cv2.perspectiveTransform(source, homography) - destination, axis=2
    ).ravel()[inlier_mask]

    height, width = baseline.shape[:2]
    image_height, image_width = image.shape[:2]
    corners = np.float32(
        [[0, 0], [image_width, 0], [image_width, image_height], [0, image_height]]
    ).reshape(-1, 1, 2)
    covered = np.zeros((height, width), np.uint8)
    cv2.fillConvexPoly(
        covered, cv2.perspectiveTransform(corners, homography).astype(np.int32), 255
    )
    return AlignmentResult(
        homography=homography,
        warped=cv2.warpPerspective(image, homography, (width, height)),
        valid_mask=cv2.erode(covered, VALID_MASK_EROSION_KERNEL),
        detector=detector,
        keypoints_query=len(image_keypoints),
        keypoints_train=len(baseline_keypoints),
        matches=len(matches),
        inliers=int(inlier_mask.sum()),
        inlier_ratio=float(inlier_mask.sum()) / len(matches),
        mean_reprojection_error=float(errors.mean()) if errors.size else None,
    )
