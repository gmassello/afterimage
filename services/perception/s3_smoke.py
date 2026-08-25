from functools import lru_cache

import cv2
import numpy as np
import boto3

from services.perception.quality import laplacian_variance


@lru_cache(maxsize=1)
def _s3():
    return boto3.client("s3")


def blur_metric_from_s3(bucket: str, key: str) -> float:
    body = _s3().get_object(Bucket=bucket, Key=key)["Body"].read()
    image = cv2.imdecode(np.frombuffer(body, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"s3://{bucket}/{key} is not a decodable image")
    return laplacian_variance(image)
