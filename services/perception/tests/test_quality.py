from services.perception.tests.panels import blurred, overexposed, partial_frame

from services.perception.quality import assess_quality


def test_blur_lowers_the_variance(panel):
    assert assess_quality(blurred(panel)).blur_variance < assess_quality(panel).blur_variance


def test_overexposure_clips_the_bright_end(panel):
    assert assess_quality(overexposed(panel)).clipped_bright_ratio > assess_quality(panel).clipped_bright_ratio
    assert assess_quality(overexposed(panel)).mean_brightness > assess_quality(panel).mean_brightness


def test_partial_frame_lowers_coverage(panel):
    assert assess_quality(partial_frame(panel)).coverage_ratio < assess_quality(panel).coverage_ratio
