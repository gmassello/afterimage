import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]


def _pins(path):
    return {
        name.strip().lower().replace("_", "-"): version.strip()
        for line in path.read_text().splitlines()
        if "==" in line and not line.startswith("#")
        for name, version in [line.split("==", 1)]
    }


def test_the_lock_pins_every_direct_dependency_at_its_declared_version():
    direct = _pins(ROOT / "requirements.txt")
    locked = _pins(ROOT / "requirements.lock")
    assert direct
    assert {name: locked.get(name) for name in direct} == direct
