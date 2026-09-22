import uuid

import cv2
import numpy as np
import pytest

from services.conftest import localstack
from services.memory import images
from services.perception.quality import laplacian_variance


def make_checkerboard() -> np.ndarray:
    tile = np.array([[0, 255], [255, 0]], dtype=np.uint8)
    board = np.tile(tile, (64, 64))
    return cv2.cvtColor(board, cv2.COLOR_GRAY2BGR)


@localstack
def test_s3_roundtrip_returns_opencv_metric():
    image = make_checkerboard()
    key = images.put_image(f"panel-smoke-{uuid.uuid4().hex[:8]}", uuid.uuid4().hex[:12], "capture", image)
    images._cache.clear()

    metric = laplacian_variance(images.get_image(key))

    assert metric == pytest.approx(laplacian_variance(image))
    assert metric > 0
