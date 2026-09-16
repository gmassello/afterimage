import platform

import cv2


def test_opencv_is_version_5():
    print(f"OpenCV {cv2.__version__} on {platform.machine()}")
    assert cv2.__version__.startswith("5."), cv2.__version__


def test_the_runtime_is_arm64():
    assert platform.machine() == "aarch64", platform.machine()


def test_the_opencv5_only_features_are_in_the_binary():
    assert hasattr(cv2, "ALIKED")
    assert hasattr(cv2, "LightGlueMatcher")
