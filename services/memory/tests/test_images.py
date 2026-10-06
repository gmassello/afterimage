import uuid
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from services.conftest import localstack
from services.memory import images


@pytest.mark.parametrize("data", [
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR" + (4001).to_bytes(4, "big") + (4000).to_bytes(4, "big"),
    b"\xff\xd8\xff\xc0\x00\x11\x08" + (4000).to_bytes(2, "big") + (4001).to_bytes(2, "big") + b"\x00" * 10,
])
def test_decode_rejects_a_header_above_the_pixel_limit(data):

    with pytest.raises(images.ImageTooLarge, match="exceeds"):
        images.decode(data)


def test_a_sibling_key_stays_in_the_same_inspection():
    assert images.sibling_key("assets/a/b/capture.png", "descriptors.npy") == (
        "assets/a/b/descriptors.npy"
    )
    with pytest.raises(ValueError):
        images.sibling_key("elsewhere/capture.png", "descriptors.npy")


@localstack
def test_an_array_round_trips_through_the_bucket():
    key = f"assets/arrays/{uuid.uuid4().hex[:12]}/descriptors.npy"
    stored = np.arange(12, dtype=np.float32).reshape(3, 4)

    assert images.get_array(key) is None
    images.put_array(key, stored)
    loaded = images.get_array(key)

    assert loaded.dtype == np.float32
    assert np.array_equal(loaded, stored)


def test_the_cache_survives_concurrent_readers_and_evictions(monkeypatch):
    monkeypatch.setattr(images, "get_png", lambda key: key.encode())
    monkeypatch.setattr(images, "decode", lambda data: np.zeros((1, 1), dtype=np.uint8))
    keys = [f"k{n}" for n in range(images.CACHE_MAX_IMAGES * 4)]

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(images.get_image, keys * 50))

    assert len(images._cache) <= images.CACHE_MAX_IMAGES
