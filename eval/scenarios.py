import json
from pathlib import Path

import cv2

from services.perception.tests import panels

DATASET = Path(__file__).parent / "dataset"
MAX_SIDE = 800
BBOX_LESIONS = ("crack_at", "hotspot_at", "delamination_at", "faint_spot_at")
CELL_LESIONS = ("with_crack", "with_hotspot", "with_delamination", "with_faint_spot")


def load(path=None):
    return json.loads(Path(path or DATASET / "scenarios.json").read_text())


def _downscale(image):
    height, width = image.shape[:2]
    if max(height, width) <= MAX_SIDE:
        return image
    factor = MAX_SIDE / max(height, width)
    return cv2.resize(image, (int(width * factor), int(height * factor)), interpolation=cv2.INTER_AREA)


def _base(spec):
    if "file" in spec:
        image = cv2.imread(str(DATASET / "base" / spec["file"]))
        if image is None:
            raise FileNotFoundError(f"base photo missing or undecodable: {spec['file']}")
        return _downscale(image)
    if "foreign" in spec:
        return panels.foreign_panel()
    return panels.solar_panel(**spec.get("synthetic", {}))


def _to_bbox(region, shape):
    height, width = shape[:2]
    x, y, box_width, box_height = region
    return int(x * width), int(y * height), int(box_width * width), int(box_height * height)


def _altered_region(name, bbox):
    x, y, width, height = bbox
    if "faint" in name:
        fraction = panels.FAINT_SPOT_FRACTION
        return x, y, int(width * fraction), int(height * fraction)
    if "hotspot" in name:
        radius = int(width * panels.HOTSPOT_RADIUS_FRACTION)
        return x + width // 2 - radius, y + height // 2 - radius, 2 * radius, 2 * radius
    return bbox


def _apply(image, steps):
    truth = None
    for name, kwargs in steps:
        kwargs = dict(kwargs)
        if "region" in kwargs:
            kwargs["bbox"] = _to_bbox(kwargs.pop("region"), image.shape)
        if name in BBOX_LESIONS:
            truth = _altered_region(name, kwargs["bbox"])
        elif name in CELL_LESIONS:
            truth = _altered_region(name, panels.cell_bbox(kwargs["row"], kwargs["col"]))
        image = getattr(panels, name)(image, **kwargs)
    return image, truth


def materialise(scenario):
    baseline, _ = _apply(_base(scenario["base"]), scenario.get("baseline", ()))
    start = _base(scenario["capture_base"]) if "capture_base" in scenario else baseline
    capture, truth = _apply(start, scenario["capture"])
    return baseline, capture, truth
