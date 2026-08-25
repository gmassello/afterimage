import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]


def test_every_module_imports_without_configuration():
    modules = sorted(
        ".".join(path.relative_to(ROOT).with_suffix("").parts)
        for path in (ROOT / "services").rglob("*.py")
        if "tests" not in path.parts
    )

    result = subprocess.run(
        [sys.executable, "-c", "".join(f"import {module}\n" for module in modules)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "PYTHONPATH": str(ROOT)},
    )

    assert result.returncode == 0, result.stderr
