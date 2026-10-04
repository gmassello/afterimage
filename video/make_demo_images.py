from pathlib import Path

import cv2
import numpy as np

from eval import scenarios
from services.perception import panels

OUT = Path(__file__).parent / "img"
SAMPLES = Path(__file__).parents[1] / "services" / "ui" / "static"


def _soft_mask(shape, bbox, seed):
    height, width = shape[:2]
    x, y, box_width, box_height = bbox
    rng = np.random.default_rng(seed)
    mask = np.zeros((height, width), np.float32)
    centre = (x + box_width // 2, y + box_height // 2)
    for _ in range(5):
        offset = rng.normal(0, 0.1, 2) * (box_width, box_height)
        axes = (int(box_width * rng.uniform(0.22, 0.42)), int(box_height * rng.uniform(0.22, 0.42)))
        point = (int(centre[0] + offset[0]), int(centre[1] + offset[1]))
        cv2.ellipse(mask, point, axes, rng.uniform(0, 180), 0, 360, 1.0, -1)
    blur = max(3, (box_width // 4) | 1)
    return cv2.GaussianBlur(mask, (blur, blur), 0)[..., None]


def glow(image, bbox, seed=7):
    mask = _soft_mask(image.shape, bbox, seed)
    grain = np.random.default_rng(seed).normal(0, 10, image.shape[:2])[..., None]
    milky = np.clip(np.array([205, 225, 232], np.float32) + grain, 0, 255)
    blended = image.astype(np.float32) * (1 - 0.65 * mask) + milky * (0.65 * mask)
    return blended.astype(np.uint8)


def yellowing(image, bbox, seed=23):
    mask = _soft_mask(image.shape, bbox, seed)
    grain = np.random.default_rng(seed).normal(0, 8, image.shape[:2])[..., None]
    amber = np.clip(np.array([20, 170, 240], np.float32) + grain, 0, 255)
    blended = image.astype(np.float32) * (1 - 0.9 * mask) + amber * (0.9 * mask)
    return blended.astype(np.uint8)


def shatter(image, bbox, seed=99):
    rng = np.random.default_rng(seed)
    x, y, box_width, box_height = bbox
    centre = np.array([x + box_width / 2, y + box_height / 2])
    reach = max(box_width, box_height) * 0.85
    halo = np.zeros(image.shape[:2], np.float32)
    cv2.circle(halo, tuple(int(v) for v in centre), int(reach * 0.75), 1.0, -1)
    halo = cv2.GaussianBlur(halo, (0, 0), reach * 0.1)[..., None]
    lines = np.zeros(image.shape[:2], np.uint8)
    spokes = []
    for index in range(int(rng.integers(7, 10))):
        angle = index * 2 * np.pi / 8 + rng.normal(0, 0.25)
        length = reach * rng.uniform(0.6, 1.0)
        points = [centre.copy()]
        for _ in range(4):
            angle += rng.normal(0, 0.12)
            points.append(points[-1] + length / 4 * np.array([np.cos(angle), np.sin(angle)]))
        spokes.append(points)
        cv2.polylines(lines, [np.array(points, np.int32)], False, 255, 2, cv2.LINE_AA)
    for ring in (2, 3):
        for left, right in zip(spokes, spokes[1:] + spokes[:1]):
            if rng.random() < 0.75:
                a, b = left[ring], right[ring]
                bend = (a + b) / 2 + rng.normal(0, reach * 0.03, 2)
                cv2.polylines(lines, [np.array([a, bend, b], np.int32)], False, 255, 1, cv2.LINE_AA)
    strokes = (lines.astype(np.float32) / 255)[..., None]
    edge = np.roll(strokes, (1, 1), axis=(0, 1)) * (1 - strokes)
    grain = rng.normal(0, 12, image.shape[:2])[..., None]
    crushed = np.clip(np.array([10, 11, 14], np.float32) + grain, 0, 255)
    cracked = image.astype(np.float32)
    cracked = cracked * (1 - 0.95 * halo) + crushed * (0.95 * halo)
    cracked = cracked * (1 - 0.9 * strokes) + 12 * (0.9 * strokes)
    cracked = cracked * (1 - 0.4 * edge) + 200 * (0.4 * edge)
    return np.clip(cracked, 0, 255).astype(np.uint8)


def fissure(image, bbox, seed=41):
    rng = np.random.default_rng(seed)
    shape = image.shape[:2]
    x, y, box_width, box_height = bbox
    point = np.array([x + box_width * 0.4, y], np.float32)
    drift = 0.0
    trunk = [point.copy()]
    while point[1] < y + box_height:
        drift = 0.7 * drift + rng.normal(0, 0.35)
        point += (drift * box_width * 0.03, box_height / 60)
        trunk.append(point.copy())
    lines = np.zeros(shape, np.float32)
    for a, b in zip(trunk, trunk[1:]):
        width = int(rng.choice([2, 2, 3]))
        cv2.line(lines, tuple(int(v) for v in a), tuple(int(v) for v in b), 1.0, width, cv2.LINE_AA)
    for start in rng.choice(np.arange(8, len(trunk) - 8), 5, replace=False):
        branch, angle = [trunk[start].copy()], rng.choice([-1, 1]) * rng.uniform(0.5, 1.1)
        for _ in range(int(rng.integers(5, 12))):
            angle += rng.normal(0, 0.35)
            branch.append(branch[-1] + box_height / 70 * np.array([np.sin(angle), np.cos(angle)]))
        cv2.polylines(lines, [np.array(branch, np.int32)], False, 0.7, 1, cv2.LINE_AA)
    strokes = lines[..., None]
    damp = cv2.GaussianBlur(cv2.dilate(lines, np.ones((7, 7), np.uint8)), (0, 0), box_width * 0.1)
    damp = np.clip(damp / damp.max() * 1.3, 0, 1)[..., None]
    grain = rng.normal(0, 6, shape)[..., None]
    cracked = image.astype(np.float32) * (1 - 0.55 * damp) + grain * damp
    cracked = cracked * (1 - 0.85 * strokes) + 28 * (0.85 * strokes)
    edge = np.roll(strokes, (-1, -1), axis=(0, 1)) * (1 - strokes)
    cracked = cracked * (1 - 0.3 * edge) + 200 * (0.3 * edge)
    return np.clip(cracked, 0, 255).astype(np.uint8)


def rust(image, bbox, seed=31):
    rng = np.random.default_rng(seed)
    shape = image.shape[:2]
    x, y, box_width, box_height = bbox
    blotch = cv2.GaussianBlur(rng.normal(0, 1, shape).astype(np.float32), (0, 0), box_width / 10)
    blotch = (blotch - blotch.min()) / (blotch.max() - blotch.min())
    mask = _soft_mask(image.shape, bbox, seed)[..., 0] * np.clip(blotch * 2.4 - 0.3, 0, 1)
    streaks = np.zeros(shape, np.float32)
    for _ in range(9):
        top = (int(x + box_width * rng.uniform(0.2, 0.8)), int(y + box_height * rng.uniform(0.4, 0.7)))
        bottom = (top[0] + int(rng.normal(0, 2)), top[1] + int(box_height * rng.uniform(0.6, 1.4)))
        cv2.line(streaks, top, bottom, rng.uniform(0.4, 0.8), int(rng.integers(2, 5)), cv2.LINE_AA)
    fade = np.clip(1 - (np.arange(shape[0]) - y - box_height * 0.5) / (box_height * 1.6), 0, 1)[:, None]
    streaks = cv2.GaussianBlur(streaks, (0, 0), 1.5) * fade
    mask = np.clip(np.maximum(mask, streaks), 0, 1)[..., None]
    tone = blotch[..., None]
    dark, orange = np.array([18, 38, 85], np.float32), np.array([30, 95, 175], np.float32)
    grain = rng.normal(0, 12, shape)[..., None]
    oxide = np.clip(dark * tone + orange * (1 - tone) + grain, 0, 255)
    blended = image.astype(np.float32) * (1 - 0.85 * mask) + oxide * (0.85 * mask)
    return blended.astype(np.uint8)


GROUPS = (
    ("sample", "panel_front_closeup.jpg", (shatter, [0.42, 0.42, 0.12, 0.12]), 99),
    ("sample-b", "array_hannover_roof.jpg", (glow, [0.55, 0.75, 0.1, 0.1]), 7),
    ("sample-c", "array_rooftop.jpg", (yellowing, [0.55, 0.62, 0.12, 0.12]), 23),
    ("sample-d", "steel_fire_tank.jpg", (rust, [0.49, 0.4, 0.15, 0.16]), 31),
    ("sample-e", "concrete_wall.jpg", (fissure, [0.18, 0.2, 0.18, 0.55]), 41),
)


def group(base: str, defect: tuple, seed: int):
    step, region = defect
    if isinstance(step, str):
        spec = {"base": {"file": base}, "capture": [[step, {"region": region}], ["shifted", {}]]}
        baseline, capture, _ = scenarios.materialise(spec)
    else:
        baseline, _, _ = scenarios.materialise({"base": {"file": base}, "capture": []})
        height, width = baseline.shape[:2]
        x, y, box_width, box_height = region
        bbox = (int(x * width), int(y * height), int(box_width * width), int(box_height * height))
        capture = panels.shifted(step(baseline, bbox))
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
