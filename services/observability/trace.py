import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from services.memory import runs

EVENTS_FILE = "events.json"
RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")
GENESIS = "0" * 64

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


def digest(event: dict) -> str:
    body = {key: value for key, value in event.items() if key != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _link(event: dict, previous: str) -> dict:
    linked = {key: value for key, value in event.items() if key not in ("prev", "hash")}
    linked["prev"] = previous
    linked["hash"] = digest(linked)
    return linked


def chain(events: list[dict]) -> list[dict]:
    chained: list[dict] = []
    previous = GENESIS
    for event in events:
        linked = _link(event, previous)
        previous = linked["hash"]
        chained.append(linked)
    return chained


def broken_at(events: list[dict]) -> int | None:
    # ponytail: a chain cut short at the end still verifies; anchoring the length needs a
    # signed head kept outside the run, which is the upgrade path if that matters
    previous = GENESIS
    for index, event in enumerate(events):
        if event.get("prev") != previous or event.get("hash") != digest(event):
            return index
        previous = event["hash"]
    return None


def emit(run_dir: Path, event_type: str, **fields) -> dict:
    previous = runs.last(run_dir, EVENTS_FILE)
    event = _link({"type": event_type, "ts": now(), **fields}, previous["hash"] if previous else GENESIS)
    runs.append(run_dir, EVENTS_FILE, event)
    return event
