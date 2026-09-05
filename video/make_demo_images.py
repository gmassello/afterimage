import json
from pathlib import Path

import cv2

from eval import scenarios
from services.perception.tests import panels

OUT = Path(__file__).parent / "img"
SCENARIO = "crack-real-closeup"


def main():
    spec = {s["id"]: s for s in scenarios.load()}[SCENARIO]
    baseline, capture, _ = scenarios.materialise(spec)
    OUT.mkdir(exist_ok=True)
    for name, image in (
        ("1-blurred.png", panels.blurred(baseline)),
        ("2-baseline.png", baseline),
        ("3-defect.png", capture),
    ):
        cv2.imwrite(str(OUT / name), image)
        print(name, image.shape)


if __name__ == "__main__":
    main()
