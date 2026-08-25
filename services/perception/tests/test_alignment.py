import numpy as np
import pytest
from services.perception.tests.panels import shifted, solar_panel

from services.perception.alignment import CLASSIC, NEURAL, align_to_baseline
from services.perception.weights import neural_weights_available

# inlier_ratio is not comparable across detectors: on the same pair ORB scores 0.41 and
# ALIKED 0.997, because a repetitive cell grid produces ambiguous ORB matches between
# identical cells. Week 4 policy needs one threshold per detector, not a shared one.
DETECTORS = [
    (CLASSIC, 0.30),
    pytest.param(
        NEURAL,
        0.90,
        marks=pytest.mark.skipif(
            not neural_weights_available(), reason="ONNX weights missing, run `make weights`"
        ),
    ),
]


@pytest.mark.parametrize("detector,threshold", DETECTORS)
def test_same_panel_aligns(panel, detector, threshold):
    result = align_to_baseline(shifted(panel), panel, detector)

    assert result.homography is not None
    assert result.inlier_ratio > threshold
    assert result.mean_reprojection_error < 3.0
    assert result.warped.shape == panel.shape


@pytest.mark.parametrize("detector,threshold", DETECTORS)
def test_foreign_input_does_not_align(panel, detector, threshold):
    noise = np.random.default_rng(1).integers(0, 255, panel.shape, dtype=np.uint8)

    for other in (solar_panel(seed=99, rows=4, cols=7, cell=80), noise):
        assert align_to_baseline(other, panel, detector).inlier_ratio < threshold


def test_unknown_detector_is_rejected(panel):
    with pytest.raises(ValueError, match="unknown detector"):
        align_to_baseline(panel, panel, "sift+flann")
