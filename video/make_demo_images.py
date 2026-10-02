from pathlib import Path

import cv2

from eval import scenarios
from services.perception import panels

OUT = Path(__file__).parent / "img"
SAMPLES = Path(__file__).parents[1] / "services" / "ui" / "static"
GROUPS = (
    ("sample", "crack-real-closeup", 99),
    ("sample-b", "hotspot-real-ogiinuur", 7),
    ("sample-c", "delamination-real-jetion", 23),
)


def group(prefix: str, scenario: str, seed: int):
    spec = {s["id"]: s for s in scenarios.load()}[scenario]
    baseline, capture, _ = scenarios.materialise(spec)
    foreign = panels.solar_panel(seed=seed, rows=4, cols=7, cell=80)
    return baseline, panels.blurred(baseline), capture, foreign


def main():
    OUT.mkdir(exist_ok=True)
    written = []
    for prefix, scenario, seed in GROUPS:
        baseline, blurred, capture, foreign = group(prefix, scenario, seed)
        written += [
            (SAMPLES / f"{prefix}-baseline.png", baseline),
            (SAMPLES / f"{prefix}-blurred.png", blurred),
            (SAMPLES / f"{prefix}-defect.png", capture),
            (SAMPLES / f"{prefix}-foreign.png", foreign),
        ]
        if prefix == "sample":
            written += [
                (OUT / "1-blurred.png", blurred),
                (OUT / "2-baseline.png", baseline),
                (OUT / "3-defect.png", capture),
            ]
    for path, image in written:
        cv2.imwrite(str(path), image)
        print(path.name, image.shape)


if __name__ == "__main__":
    main()
