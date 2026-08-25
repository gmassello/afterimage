from conftest import cell_bbox, with_crack, with_faint_spot

from services.perception.diffing import crop_and_rescan, diff_against_memory

CRACK_CELL = (2, 4)


def _contains(bbox, point):
    x, y, width, height = bbox
    return x <= point[0] <= x + width and y <= point[1] <= y + height


def _centre(bbox):
    x, y, width, height = bbox
    return x + width // 2, y + height // 2


def test_identical_capture_reports_no_change(panel):
    result = diff_against_memory(panel, panel)

    assert result.regions == []
    assert result.changed_ratio == 0.0


def test_broken_cell_is_located(panel):
    result = diff_against_memory(with_crack(panel, *CRACK_CELL), panel)

    assert len(result.regions) == 1
    assert _contains(result.regions[0].bbox, _centre(cell_bbox(*CRACK_CELL)))
    assert result.regions[0].mean_delta > 0


def test_rescan_measures_a_faint_region_with_more_pixels(panel):
    """The ACTION 3 path: a change too marginal to measure well at full resolution."""
    damaged = with_faint_spot(panel, *CRACK_CELL)
    region = diff_against_memory(damaged, panel).regions[0]
    assert region.area_ratio < 0.01

    rescanned = crop_and_rescan(damaged, panel, region.bbox, scale=2.0)

    assert rescanned.regions
    assert rescanned.regions[0].area_px > 3 * region.area_px
    assert rescanned.regions[0].area_ratio > region.area_ratio


def test_rescan_returns_full_frame_coordinates(panel):
    """Without the remap the agent could not chain the zoom into the next tool."""
    damaged = with_crack(panel, *CRACK_CELL)
    region = diff_against_memory(damaged, panel).regions[0]

    rescanned = crop_and_rescan(damaged, panel, region.bbox)

    assert _contains(rescanned.regions[0].bbox, _centre(cell_bbox(*CRACK_CELL)))
