import json
import re
from datetime import datetime, timezone
from pathlib import Path

EVENTS_FILE = "events.json"
RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")


def write_json(path: Path, data) -> None:
    Path(path).write_text(json.dumps(data, indent=2))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def read_events(run_dir: Path) -> list[dict]:
    path = Path(run_dir) / EVENTS_FILE
    return json.loads(path.read_text()) if path.exists() else []


def emit(run_dir: Path, event_type: str, **fields) -> dict:
    events = read_events(run_dir)
    event = {"type": event_type, "ts": now(), **fields}
    events.append(event)
    write_json(Path(run_dir) / EVENTS_FILE, events)
    return event
