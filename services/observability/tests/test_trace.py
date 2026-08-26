import json
from datetime import datetime

from services.observability import trace


def events_on_disk(run_dir):
    return json.loads((run_dir / "events.json").read_text())


def test_emit_appends_in_order_with_server_timestamps(tmp_path):
    first = trace.emit(tmp_path, "run_started", run_id="abcdef123456")
    second = trace.emit(tmp_path, "tool_call", tool="assess_quality")
    events = events_on_disk(tmp_path)
    assert [e["type"] for e in events] == ["run_started", "tool_call"]
    assert events == [first, second]
    for event in events:
        datetime.fromisoformat(event["ts"])
    assert events[0]["ts"] <= events[1]["ts"]


def test_emit_survives_across_readers(tmp_path):
    trace.emit(tmp_path, "run_started", run_id="abcdef123456")
    assert trace.read_events(tmp_path) == events_on_disk(tmp_path)
    trace.emit(tmp_path, "run_finished", status="completed", branch="no_change")
    assert [e["type"] for e in events_on_disk(tmp_path)] == ["run_started", "run_finished"]
