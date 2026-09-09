import re
from datetime import datetime, timezone
from pathlib import Path

from services.memory import runs

EVENTS_FILE = "events.json"
RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")

AWAITING_APPROVAL = "awaiting_approval"
FAILED = "failed"

UNSTARTED = "unstarted"
RUNNING = "running"
DONE = "done"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def read_events(run_dir: Path) -> list[dict]:
    return runs.read(run_dir, EVENTS_FILE) or []


def run_state(events: list[dict]) -> str:
    if any(event["type"] == "run_finished" for event in events):
        return DONE
    return RUNNING if any(event["type"] != "run_started" for event in events) else UNSTARTED


def started_event(events: list[dict]) -> dict | None:
    return next((event for event in events if event["type"] == "run_started"), None)


def emit(run_dir: Path, event_type: str, **fields) -> dict:
    event = {"type": event_type, "ts": now(), **fields}
    runs.append(run_dir, EVENTS_FILE, event)
    return event
