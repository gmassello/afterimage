import json
from pathlib import Path

import cv2

from eval import scenarios
from services.perception.tests import panels

OUT = Path(__file__).parent / "img"
SAMPLES = Path(__file__).parents[1] / "services" / "ui" / "static"
SCENARIO = "crack-real-closeup"


def main():
    spec = {s["id"]: s for s in scenarios.load()}[SCENARIO]
    baseline, capture, _ = scenarios.materialise(spec)
    blurred = panels.blurred(baseline)
    OUT.mkdir(exist_ok=True)
    written = (
        (OUT / "1-blurred.png", blurred),
        (OUT / "2-baseline.png", baseline),
        (OUT / "3-defect.png", capture),
        (SAMPLES / "sample-baseline.png", baseline),
        (SAMPLES / "sample-blurred.png", blurred),
        (SAMPLES / "sample-defect.png", capture),
        (SAMPLES / "sample-foreign.png", panels.foreign_panel()),
    )
    for path, image in written:
        cv2.imwrite(str(path), image)
        print(path.name, image.shape)


if __name__ == "__main__":
    main()
