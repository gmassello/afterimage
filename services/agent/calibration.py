from functools import lru_cache

from services.agent import policy
from services.perception import alignment
from services.perception.panels import shifted, solar_panel


@lru_cache(maxsize=1)
def calibration() -> dict:
    reference = solar_panel(seed=0)
    detector = alignment.default_detector()
    result = alignment.align_to_baseline(shifted(reference), reference, detector)
    return policy.evaluate(
        "alignment",
        {"detector": detector, "inlier_ratio": result.inlier_ratio},
        policy.Policy.from_env(),
    )


def healthy() -> bool:
    return calibration()["branch"] == policy.ALIGNED
