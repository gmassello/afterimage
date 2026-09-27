from services.agent import calibration, policy


def test_the_reference_pair_aligns_on_the_detector_in_use():
    calibration.calibration.cache_clear()
    verdict = calibration.calibration()

    assert verdict["input_metric"] == "inlier_ratio"
    assert verdict["branch"] == policy.ALIGNED
    assert calibration.healthy()

