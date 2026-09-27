import argparse
import json
from pathlib import Path

from services.agent import hitl, policy
from services.memory import runs
from services.observability import trace


# ponytail: walks a local runs directory, so runs kept in S3 (AFTERIMAGE_RUNS_S3=1) are copied down
# first; a paginated list over the runs/ prefix is the upgrade if this becomes routine
def harvest(root: Path) -> list[dict]:
    stubs = []
    for run_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        events = trace.read_events(run_dir)
        verdict = next(
            (
                event.get("policy") for event in events
                if event.get("tool") == hitl.JEV_REJECTION and event.get("policy")
            ),
            None,
        )
        if verdict is None or verdict["branch"] != policy.REJECTED_CAPTURE:
            continue
        started = trace.started_event(events) or {}
        stubs.append({
            "id": f"capture-artefact-{run_dir.name}",
            "source_run": run_dir.name,
            "capture_key": started.get("capture_key"),
            "reason": (runs.read(run_dir, runs.VERDICT) or {}).get("reason"),
            "capture_artefact": verdict["value"],
            "expect": {"branch": policy.NO_CHANGE},
        })
    return stubs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List rejections a reviewer blamed on the capture as candidate eval scenarios."
    )
    parser.add_argument("--runs", default=None, help="runs directory (defaults to the configured one)")
    args = parser.parse_args()
    root = Path(args.runs) if args.runs else runs.runs_dir()
    print(json.dumps(harvest(root), indent=2))


if __name__ == "__main__":
    main()
