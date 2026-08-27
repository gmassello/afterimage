import re
from datetime import datetime, timezone
from pathlib import Path

from services.memory import runs

EVENTS_FILE = "events.json"
RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def read_events(run_dir: Path) -> list[dict]:
    return runs.read(run_dir, EVENTS_FILE) or []


def emit(run_dir: Path, event_type: str, **fields) -> dict:
    event = {"type": event_type, "ts": now(), **fields}
    runs.append(run_dir, EVENTS_FILE, event)
    return event
