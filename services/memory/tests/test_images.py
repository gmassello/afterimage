import pytest

from services.memory import images


@pytest.mark.parametrize("data", [
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR" + (4001).to_bytes(4, "big") + (4000).to_bytes(4, "big"),
    b"\xff\xd8\xff\xc0\x00\x11\x08" + (4000).to_bytes(2, "big") + (4001).to_bytes(2, "big") + b"\x00" * 10,
])
def test_decode_rejects_a_header_above_the_pixel_limit(data):

    with pytest.raises(ValueError, match="exceeds"):
        images.decode(data)
