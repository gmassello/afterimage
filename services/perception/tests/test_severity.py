import pytest
from conftest import cell_bbox, with_crack, with_delamination, with_hotspot, with_soiling

from services.perception.diffing import crop_region
from services.perception.severity import CRACK, DELAMINATION, HOTSPOT, SOILING, classify_severity

CASES = [
    (with_crack, (2, 4), CRACK),
    (with_hotspot, (3, 7), HOTSPOT),
    (with_delamination, (1, 2), DELAMINATION),
]


@pytest.mark.parametrize("damage,cell,expected", CASES)
def test_defect_class_is_recognised(panel, damage, cell, expected):
    bbox = cell_bbox(*cell)

    result = classify_severity(
        crop_region(damage(panel, *cell), bbox), crop_region(panel, bbox), area_ratio=0.01
    )

    assert result.label == expected
    assert result.score > 0.0


def test_soiling_is_told_apart_by_its_extent(panel):
    """Soiling looks like a faint hotspot on a crop; what separates it is covering the frame."""
    dirty = with_soiling(panel)

    assert classify_severity(dirty, panel, area_ratio=0.6).label == SOILING


def test_unchanged_crop_scores_zero(panel):
    crop = crop_region(panel, cell_bbox(2, 4))

    assert classify_severity(crop, crop, area_ratio=0.0).score == 0.0
