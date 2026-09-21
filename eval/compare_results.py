import json
import sys
from pathlib import Path

EXACT = ("scenarios", "real", "synthetic", "passed")
TOLERANCE = 0.01


def summary_of(directory: str | Path) -> dict:
    return json.loads((Path(directory) / "results.json").read_text())["summary"]


def figures(summary: dict) -> dict:
    return {
        "branch.accuracy": summary["branch"]["accuracy"],
        "branch.macro.f1": summary["branch"]["macro"]["f1"],
        "defect.accuracy": summary["defect"]["accuracy"],
        "defect.macro.f1": summary["defect"]["macro"]["f1"],
        "localisation.mean_iou": summary["localisation"]["mean_iou"],
    }


def differences(published: dict, measured: dict) -> list[str]:
    drift = [
        f"{name}: published {published[name]}, measured {measured[name]}"
        for name in EXACT
        if published[name] != measured[name]
    ]
    fresh = figures(measured)
    for name, value in figures(published).items():
        other = fresh[name]
        if value is None or other is None:
            if value != other:
                drift.append(f"{name}: published {value}, measured {other}")
        elif abs(value - other) > TOLERANCE:
            drift.append(f"{name}: published {value}, measured {other}, over {TOLERANCE}")
    return drift


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise SystemExit("usage: compare_results.py <published dir> <measured dir>")
    drift = differences(summary_of(argv[0]), summary_of(argv[1]))
    if drift:
        listed = "\n  ".join(drift)
        raise SystemExit(f"the published numbers no longer match a fresh run:\n  {listed}")
    print(f"the published numbers match a fresh run within {TOLERANCE}")


if __name__ == "__main__":
    main(sys.argv[1:])
