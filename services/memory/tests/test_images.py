import uuid

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
