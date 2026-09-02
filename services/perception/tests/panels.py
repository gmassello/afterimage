import cv2
import numpy as np


ROWS, COLS, CELL, BORDER = 6, 10, 60, 20
FAINT_SPOT_FRACTION = 0.35
HOTSPOT_RADIUS_FRACTION = 1 / 3


def solar_panel(seed: int = 0, rows: int = ROWS, cols: int = COLS, cell: int = CELL) -> np.ndarray:
    rng = np.random.default_rng(seed)
    height, width = rows * cell + 2 * BORDER, cols * cell + 2 * BORDER
    panel = np.full((height, width, 3), 90, np.uint8)
    for row in range(rows):
        for col in range(cols):
            y, x = BORDER + row * cell, BORDER + col * cell
            tone = int(rng.integers(55, 75))
            panel[y + 3 : y + cell - 3, x + 3 : x + cell - 3] = (tone + 30, tone + 10, tone - 20)
            panel[y + 3 : y + cell - 3, x + cell // 2 - 1 : x + cell // 2 + 1] = 200
    panel = cv2.GaussianBlur(panel, (3, 3), 0)
    noise = rng.integers(-8, 8, panel.shape, dtype=np.int16)
    return np.clip(panel.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def foreign_panel() -> np.ndarray:
    return solar_panel(seed=99, rows=4, cols=7, cell=80)


def cell_bbox(row: int, col: int, cell: int = CELL) -> tuple[int, int, int, int]:
    return BORDER + col * cell + 3, BORDER + row * cell + 3, cell - 6, cell - 6


def centre(bbox: tuple[int, int, int, int]) -> tuple[int, int]:
    x, y, width, height = bbox
    return x + width // 2, y + height // 2


def contains(bbox: tuple[int, int, int, int], point: tuple[int, int]) -> bool:
    x, y, width, height = bbox
    return x <= point[0] < x + width and y <= point[1] < y + height


def crack_at(image: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    damaged = image.copy()
    x, y, width, height = bbox
    damaged[y : y + height, x : x + width] //= 3
    cv2.line(damaged, (x + 2, y + 2), (x + width - 2, y + height - 2), (10, 10, 10), 2)
    return damaged


def hotspot_at(image: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    damaged = image.copy()
    x, y, width, height = bbox
    radius = int(width * HOTSPOT_RADIUS_FRACTION)
    cv2.circle(damaged, (x + width // 2, y + height // 2), radius, (200, 210, 235), -1)
    return damaged


def delamination_at(image: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    damaged = image.copy()
    x, y, width, height = bbox
    damaged[y : y + height, x : x + width] = (40, 170, 200)
    return damaged


def faint_spot_at(image: np.ndarray, bbox: tuple[int, int, int, int], delta: int = 22) -> np.ndarray:
    damaged = image.copy()
    x, y, width, height = bbox
    patch = damaged[y : y + int(height * FAINT_SPOT_FRACTION), x : x + int(width * FAINT_SPOT_FRACTION)]
    patch[:] = np.clip(patch.astype(np.int16) - delta, 0, 255).astype(np.uint8)
    return damaged


def with_crack(panel: np.ndarray, row: int, col: int) -> np.ndarray:
    return crack_at(panel, cell_bbox(row, col))


def with_hotspot(panel: np.ndarray, row: int, col: int) -> np.ndarray:
    return hotspot_at(panel, cell_bbox(row, col))


def with_delamination(panel: np.ndarray, row: int, col: int) -> np.ndarray:
    return delamination_at(panel, cell_bbox(row, col))


def with_faint_spot(panel: np.ndarray, row: int, col: int, delta: int = 22) -> np.ndarray:
    return faint_spot_at(panel, cell_bbox(row, col), delta)


def with_soiling(panel: np.ndarray) -> np.ndarray:
    height, width = panel.shape[:2]
    dust = np.zeros((height, width), np.uint8)
    cv2.ellipse(dust, (width // 2, height // 2), (width // 3, height // 4), 20, 0, 360, 70, -1)
    dust = cv2.GaussianBlur(dust, (61, 61), 0)
    return np.clip(panel.astype(np.int16) + dust[:, :, None], 0, 255).astype(np.uint8)


def blurred(panel: np.ndarray) -> np.ndarray:
    return cv2.GaussianBlur(panel, (21, 21), 0)


def overexposed(panel: np.ndarray) -> np.ndarray:
    return cv2.convertScaleAbs(panel, alpha=2.6, beta=90)


def partial_frame(panel: np.ndarray) -> np.ndarray:
    framed = np.full_like(panel, 90)
    height, width = panel.shape[:2]
    small = cv2.resize(panel, (width // 4, height // 4))
    framed[: height // 4, : width // 4] = small
    return framed


def shifted(panel: np.ndarray, dx: int = 12, dy: int = -7, angle: float = 6.0, scale: float = 1.03):
    height, width = panel.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, scale)
    matrix[0, 2] += dx
    matrix[1, 2] += dy
    return cv2.warpAffine(panel, matrix, (width, height), borderValue=(90, 90, 90))
