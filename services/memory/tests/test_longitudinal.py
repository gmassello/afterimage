import os

import pytest

from services.memory import images, store
from services.perception.alignment import CLASSIC, align_to_baseline
from services.perception.diffing import crop_region, diff_against_memory
from services.perception.quality import assess_quality
from services.perception.severity import CRACK, classify_severity
from services.perception.tests.panels import (
    cell_bbox,
    centre,
    contains,
    shifted,
    solar_panel,
    with_crack,
)

ASSET = "panel-a7"
CRACK_CELL = (2, 4)
FIRST = "2026-03-01T09:00:00Z"
SECOND = "2026-06-01T09:00:00Z"

localstack = pytest.mark.skipif(
    "AWS_ENDPOINT_URL" not in os.environ, reason="requires LocalStack"
)


def _record(inspection_id, captured_at, image, metrics):
    key = images.put_image(ASSET, inspection_id, "capture", image)
    store.put_inspection(ASSET, inspection_id, captured_at, metrics, {"capture": key})
    return key


@localstack
def test_second_inspection_compares_against_the_first():
    clean = solar_panel(seed=7)
    store.put_asset(ASSET, kind="solar_panel", site="atacama")

    first_quality = assess_quality(clean)
    first_key = _record("insp-1", FIRST, clean, {"blur_variance": first_quality.blur_variance})
    store.promote_baseline(ASSET, "insp-1", FIRST, first_key, first_quality.blur_variance)

    recapture = shifted(with_crack(clean, *CRACK_CELL))

    baseline = store.current_baseline(ASSET)
    assert baseline["inspection_id"] == "insp-1"
    remembered = images.get_image(baseline["image_key"])

    alignment = align_to_baseline(recapture, remembered, detector=CLASSIC)
    assert alignment.warped is not None

    diff = diff_against_memory(alignment.warped, remembered, alignment.valid_mask)
    assert diff.regions, "nothing changed against the remembered baseline"

    region = diff.regions[0]
    assert contains(region.bbox, centre(cell_bbox(*CRACK_CELL)))
    severity = classify_severity(
        crop_region(alignment.warped, region.bbox),
        crop_region(remembered, region.bbox),
        region.area_ratio,
    )
    assert severity.label == CRACK

    second_quality = assess_quality(recapture)
    second_key = _record(
        "insp-2",
        SECOND,
        recapture,
        {
            "blur_variance": second_quality.blur_variance,
            "inlier_ratio": alignment.inlier_ratio,
            "changed_ratio": diff.changed_ratio,
            "area_ratio": region.area_ratio,
            "score": severity.score,
        },
    )
    store.promote_baseline(ASSET, "insp-2", SECOND, second_key, second_quality.blur_variance)

    records = store.history(ASSET)
    inspections = [item for item in records if item["sk"].startswith(store.INSPECTION)]
    assert [item["inspection_id"] for item in inspections] == ["insp-2", "insp-1"]
    assert isinstance(inspections[0]["metrics"]["inlier_ratio"], float)

    baselines = [item for item in records if item["sk"].startswith(store.BASELINE)]
    assert [item["inspection_id"] for item in baselines] == ["insp-2", "insp-1"]
    assert baselines[1]["superseded_by"] == "insp-2"
    assert "superseded_by" not in baselines[0]
    assert store.current_baseline(ASSET)["inspection_id"] == "insp-2"
