import os
from pathlib import Path

ALIKED_FILE = "aliked-n16rot-top1k-640.onnx"
LIGHTGLUE_FILE = "aliked_lightglue.onnx"

WEIGHTS = {
    ALIKED_FILE: "41faa7bf5d7eb68a2851471ba03aa20c9db30e4c",
    LIGHTGLUE_FILE: "02723aa521990e57fe33d90b67977590c460e351",
}

BASE_URL = "https://raw.githubusercontent.com/YangGuanyuhan/lightglue_opencv_project/main/model"


def weights_dir() -> Path:
    return Path(os.environ.get("AFTERIMAGE_WEIGHTS_DIR", "/opt/models"))


def aliked_path() -> Path:
    return weights_dir() / ALIKED_FILE


def lightglue_path() -> Path:
    return weights_dir() / LIGHTGLUE_FILE


def neural_weights_available() -> bool:
    return aliked_path().is_file() and lightglue_path().is_file()


def _download(name: str, expected_sha1: str) -> None:
    import hashlib
    import urllib.request

    target = weights_dir() / name
    if target.is_file() and hashlib.sha1(target.read_bytes()).hexdigest() == expected_sha1:
        print(f"{name}: already present")
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"{name}: downloading")
    with urllib.request.urlopen(f"{BASE_URL}/{name}") as response:
        payload = response.read()

    digest = hashlib.sha1(payload).hexdigest()
    if digest != expected_sha1:
        raise SystemExit(f"{name}: sha1 mismatch, expected {expected_sha1}, got {digest}")

    target.write_bytes(payload)
    print(f"{name}: ok ({len(payload)} bytes)")


if __name__ == "__main__":
    for filename, sha1 in WEIGHTS.items():
        _download(filename, sha1)
