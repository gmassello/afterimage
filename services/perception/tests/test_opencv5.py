import cv2


def test_opencv_is_version_5():
    assert cv2.__version__.startswith("5.")
