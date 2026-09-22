import os
from functools import lru_cache

import boto3
import cv2
import numpy as np
from botocore.exceptions import ClientError

BUCKET = os.environ.get("AFTERIMAGE_BUCKET", "afterimage")
MAX_IMAGE_PIXELS = 16_000_000

# ponytail: unbounded per-process cache; fine for per-run server processes, add eviction for a long-lived API
_cache: dict[str, np.ndarray] = {}


class ImageTooLarge(ValueError):
    pass


@lru_cache(maxsize=1)
def _s3():
    return boto3.client("s3")


def ensure_bucket() -> None:
    client = _s3()
    region = client.meta.region_name
    kwargs = {} if region in (None, "us-east-1") else {"CreateBucketConfiguration": {"LocationConstraint": region}}
    try:
        client.create_bucket(Bucket=BUCKET, **kwargs)
    except (client.exceptions.BucketAlreadyOwnedByYou, client.exceptions.BucketAlreadyExists):
        pass


def _png(image: np.ndarray, what: str) -> bytes:
    encoded, buffer = cv2.imencode(".png", image)
    if not encoded:
        raise ValueError(f"{what} could not be encoded as PNG")
    return buffer.tobytes()


def put_image(asset_id: str, inspection_id: str, name: str, image: np.ndarray) -> str:
    key = f"assets/{asset_id}/{inspection_id}/{name}.png"
    _s3().put_object(Bucket=BUCKET, Key=key, Body=_png(image, name))
    _cache[key] = image
    return key


# ponytail: decoded straight from S3 instead of through get_image, so a thumbnail request does
# not pin a full-resolution array in the process cache the agent needs for its own captures
def thumbnail_png(key: str, width: int) -> bytes:
    image = decode(get_png(key))
    height, full_width = image.shape[:2]
    width = min(width, full_width)
    scaled = cv2.resize(
        image, (width, max(1, round(height * width / full_width))), interpolation=cv2.INTER_AREA
    )
    return _png(scaled, key)


def ids_from_key(key: str) -> tuple[str, str]:
    parts = key.split("/")
    if len(parts) != 4 or parts[0] != "assets":
        raise ValueError(f"key {key!r} does not match assets/{{asset_id}}/{{inspection_id}}/{{name}}.png")
    return parts[1], parts[2]


def decode(data: bytes) -> np.ndarray:
    width, height = _dimensions(data)
    if width <= 0 or height <= 0:
        raise ValueError("not a decodable image")
    if width * height > MAX_IMAGE_PIXELS:
        raise ImageTooLarge(f"image exceeds {MAX_IMAGE_PIXELS} pixels")
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("not a decodable image")
    return image


def _dimensions(data: bytes) -> tuple[int, int]:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24 and data[12:16] == b"IHDR":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("not a supported PNG or JPEG image")
    index = 2
    while index + 3 < len(data):
        if data[index] != 0xFF:
            raise ValueError("not a decodable image")
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in (0x01, *range(0xD0, 0xD8)):
            continue
        if index + 2 > len(data):
            break
        length = int.from_bytes(data[index:index + 2], "big")
        if length < 2 or index + length > len(data):
            break
        if marker in (*range(0xC0, 0xC4), *range(0xC5, 0xC8), *range(0xC9, 0xCC), *range(0xCD, 0xD0)):
            if length < 8:
                break
            return (
                int.from_bytes(data[index + 5:index + 7], "big"),
                int.from_bytes(data[index + 3:index + 5], "big"),
            )
        index += length
    raise ValueError("not a supported PNG or JPEG image")


def get_png(key: str) -> bytes:
    try:
        return _s3().get_object(Bucket=BUCKET, Key=key)["Body"].read()
    except _s3().exceptions.NoSuchKey:
        raise ValueError(f"s3://{BUCKET}/{key} does not exist")


def exists(key: str) -> bool:
    try:
        _s3().head_object(Bucket=BUCKET, Key=key)
    except ClientError as rejected:
        if rejected.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise
    return True


def get_image(key: str) -> np.ndarray:
    if key in _cache:
        return _cache[key]
    image = _cache[key] = decode(get_png(key))
    return image
