import os

import boto3
import cv2
import numpy as np
import pytest

from services.perception.s3_smoke import blur_metric_from_s3, laplacian_variance

BUCKET = "afterimage-test"


def make_checkerboard() -> np.ndarray:
    tile = np.array([[0, 255], [255, 0]], dtype=np.uint8)
    board = np.tile(tile, (64, 64))
    return cv2.cvtColor(board, cv2.COLOR_GRAY2BGR)


@pytest.mark.skipif("AWS_ENDPOINT_URL" not in os.environ, reason="requires LocalStack")
def test_s3_roundtrip_returns_opencv_metric():
    image = make_checkerboard()
    ok, encoded = cv2.imencode(".png", image)
    assert ok

    s3 = boto3.client("s3")
    s3.create_bucket(Bucket=BUCKET)
    s3.put_object(Bucket=BUCKET, Key="checkerboard.png", Body=encoded.tobytes())

    metric = blur_metric_from_s3(BUCKET, "checkerboard.png")

    assert metric == pytest.approx(laplacian_variance(image))
    assert metric > 0


def test_blur_lowers_the_metric():
    sharp = make_checkerboard()
    blurred = cv2.GaussianBlur(sharp, (21, 21), 0)
    assert laplacian_variance(blurred) < laplacian_variance(sharp)
