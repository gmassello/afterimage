from pathlib import Path

import cv2

from eval import scenarios
from services.perception import panels

OUT = Path(__file__).parent / "img"
SAMPLES = Path(__file__).parents[1] / "services" / "ui" / "static"
GROUPS = (
    ("sample", "panel_front_closeup.jpg", ("crack_at", [0.42, 0.42, 0.12, 0.12]), 99),
    ("sample-b", "array_hannover_roof.jpg", ("hotspot_at", [0.55, 0.75, 0.1, 0.1]), 7),
    ("sample-c", "array_rooftop.jpg", ("delamination_at", [0.55, 0.62, 0.12, 0.12]), 23),
)


def group(base: str, defect: tuple, seed: int):
    step, region = defect
    spec = {"base": {"file": base}, "capture": [[step, {"region": region}], ["shifted", {}]]}
    baseline, capture, _ = scenarios.materialise(spec)
    foreign = panels.solar_panel(seed=seed, rows=4, cols=7, cell=80)
    return baseline, panels.blurred(baseline), capture, foreign


def main():
    OUT.mkdir(exist_ok=True)
    written = []
    for prefix, base, defect, seed in GROUPS:
        baseline, blurred, capture, foreign = group(base, defect, seed)
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
