import argparse
import json
from pathlib import Path

from services.memory import runs
from services.observability import trace


def load_run(run_dir: Path) -> tuple[dict, list[dict]]:
    run_dir = Path(run_dir)
    events = trace.read_events(run_dir)
    finished = trace.run_state(events) == trace.DONE
    return (runs.read(run_dir, "state.json") or {}) if finished else {}, events


def causal_line(decision: dict) -> str:
    op = "<" if decision["value"] < decision["threshold"] else ">="
    return (
        f"{decision['input_metric']} {decision['value']} {op} "
        f"{decision['threshold']} -> {decision['branch']}"
    )


def _text_line(event: dict) -> str:
    kind = event["type"]
    if kind == "run_started":
        return f"run {event['run_id']} started  asset={event['asset_id']}  capture={event['capture_key']}"
    if kind == "tool_call":
        head = f"{event['tool']} ({event['duration_ms']} ms)"
        if "error" in event:
            return f"{head}  error: {event['error']}"
        if "policy" in event:
            return f"{head}  {causal_line(event['policy'])}"
        return head
    if kind == "decision":
        return causal_line(event)
    if kind == "approval_requested":
        return f"approval requested: {event['message']}"
    if kind == "run_finished":
        message = f"  {event['message']}" if event.get("message") else ""
        return f"run finished: {event['status']} ({event['branch']}){message}"
    return json.dumps(event)


def render_text(events: list[dict]) -> str:
    return "\n".join(f"[{e['ts']}] {_text_line(e)}" for e in events)


def main() -> None:
    parser = argparse.ArgumentParser(description="Print the trace of a run.")
    parser.add_argument("run_id")
    parser.add_argument("--runs-dir", default="runs")
    args = parser.parse_args()
    print(render_text(trace.read_events(Path(args.runs_dir) / args.run_id)))


if __name__ == "__main__":
    main()
