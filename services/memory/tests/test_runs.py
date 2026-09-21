import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.conftest import localstack
from services.memory import runs


def exercise_backend(run_dir):
    assert runs.read(run_dir, "state.json") is None
    runs.write(run_dir, "state.json", {"status": "completed"})
    assert runs.read(run_dir, "state.json") == {"status": "completed"}
    runs.write(run_dir, "pending.json", {"run_id": run_dir.name})
    runs.write(run_dir.parent / "other0runab", "state.json", {"status": "completed"})
    assert runs.pending(run_dir.parent) == [{"run_id": run_dir.name}]
    runs.append(run_dir, "events.json", {"type": "run_started"})
    runs.append(run_dir, "events.json", {"type": "run_finished"})
    assert [e["type"] for e in runs.read(run_dir, "events.json")] == ["run_started", "run_finished"]
    runs.delete(run_dir, "pending.json")
    assert runs.pending(run_dir.parent) == []
    assert runs.read(run_dir, "pending.json") is None
    runs.delete(run_dir, "pending.json")


def test_disk_backend(tmp_path):
    exercise_backend(tmp_path / uuid.uuid4().hex[:12])


def test_append_reads_the_stored_file_on_every_call(tmp_path):
    run_dir = tmp_path / "abcdef123456"
    runs.append(run_dir, runs.EVENTS, {"n": 1})
    runs.write(run_dir, runs.EVENTS, [{"n": 1}, {"n": 2}])
    runs.append(run_dir, runs.EVENTS, {"n": 3})
    assert runs.read(run_dir, runs.EVENTS) == [{"n": 1}, {"n": 2}, {"n": 3}]
    assert runs.last(run_dir, runs.EVENTS) == {"n": 3}


def test_the_queue_comes_back_oldest_first(tmp_path):
    older = {"run_id": "ffffffffffff", "captured_at": "2026-09-12T09:00:00.000+00:00"}
    newer = {"run_id": "000000000000", "captured_at": "2026-09-12T10:00:00.000+00:00"}
    for payload in (older, newer):
        runs.write(tmp_path / payload["run_id"], runs.PENDING, payload)
    assert runs.pending(tmp_path) == [older, newer]


@localstack
def test_s3_backend(tmp_path, monkeypatch):
    from services.memory import images

    images.ensure_bucket()
    monkeypatch.setenv("AFTERIMAGE_RUNS_S3", "1")
    exercise_backend(tmp_path / uuid.uuid4().hex[:12])


def test_disk_marker_is_exclusive_and_returns_the_winner(tmp_path):
    run_dir = tmp_path / "abcdef123456"

    def claim(index):
        return runs.write_once(run_dir, runs.RETRY, {"run_id": f"{index:012x}"})

    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(claim, range(8)))
    winners = [payload for created, payload in results if created]
    assert len(winners) == 1
    assert all(payload == winners[0] for _, payload in results)
    assert runs.read(run_dir, runs.RETRY) == winners[0]


def test_recent_runs_are_filtered_sorted_and_limited(tmp_path):
    for index in range(55):
        run_id = f"{index:012x}"
        status = "failed" if index % 2 else "completed"
        runs.write(tmp_path / run_id, runs.EVENTS, [
            {
                "type": "run_started",
                "ts": f"2026-09-12T09:{index:02d}:00.000+00:00",
                "run_id": run_id,
                "asset_id": f"panel-{index}",
                "capture_key": f"assets/panel-{index}/capture/capture.png",
            },
            {
                "type": "run_finished",
                "ts": f"2026-09-12T09:{index:02d}:01.000+00:00",
                "status": status,
                "branch": None,
                "message": "",
            },
        ])
    assert len(runs.recent(tmp_path)) == 50
    failed = runs.recent(tmp_path, q="panel-53", status="failed")
    assert [item["asset_id"] for item in failed] == ["panel-53"]
    assert failed[0]["retryable"] is True
    assert runs.recent(tmp_path, status="unknown") == []


@localstack
def test_s3_marker_is_conditional(tmp_path, monkeypatch):
    from services.memory import images

    images.ensure_bucket()
    monkeypatch.setenv("AFTERIMAGE_RUNS_S3", "1")
    run_dir = tmp_path / uuid.uuid4().hex[:12]
    first = runs.write_once(run_dir, runs.RETRY, {"run_id": "111111111111"})
    second = runs.write_once(run_dir, runs.RETRY, {"run_id": "222222222222"})
    assert first == (True, {"run_id": "111111111111"})
    assert second == (False, {"run_id": "111111111111"})


def test_the_s3_queue_pages_through_every_listing_page(monkeypatch):
    from services.memory import images

    pages = [
        {"Contents": [
            {"Key": "runs/aaaaaaaaaaaa/pending.json", "LastModified": 2},
            {"Key": "runs/aaaaaaaaaaaa/events.json", "LastModified": 2},
        ]},
        {"Contents": [{"Key": "runs/bbbbbbbbbbbb/pending.json", "LastModified": 1}]},
    ]

    class FakeS3:
        def get_paginator(self, operation):
            assert operation == "list_objects_v2"
            return self

        def paginate(self, **kwargs):
            return iter(pages)

    monkeypatch.setenv("AFTERIMAGE_RUNS_S3", "1")
    monkeypatch.setattr(images, "_s3", FakeS3)
    monkeypatch.setattr(runs, "read", lambda run_dir, name: {"run_id": Path(run_dir).name})
    assert [payload["run_id"] for payload in runs.pending("runs")] == [
        "aaaaaaaaaaaa",
        "bbbbbbbbbbbb",
    ]


def test_the_s3_listing_keeps_only_the_newest_runs(monkeypatch):
    from services.memory import images

    pages = [{"Contents": [
        {"Key": f"runs/{run_id}/events.json", "LastModified": stamp}
        for run_id, stamp in (("aaaaaaaaaaaa", 1), ("bbbbbbbbbbbb", 3), ("cccccccccccc", 2))
    ]}]

    class FakeS3:
        def get_paginator(self, operation):
            return self

        def paginate(self, **kwargs):
            return iter(pages)

    monkeypatch.setenv("AFTERIMAGE_RUNS_S3", "1")
    monkeypatch.setattr(images, "_s3", FakeS3)
    assert runs._run_ids("runs", limit=2) == ["bbbbbbbbbbbb", "cccccccccccc"]


def test_recent_widens_the_window_only_when_it_filters(tmp_path, monkeypatch):
    windows = []
    monkeypatch.setattr(runs, "_run_ids", lambda root, limit=None: windows.append(limit) or [])
    runs.recent(tmp_path, limit=50)
    runs.recent(tmp_path, limit=50, q="panel-3")
    runs.recent(tmp_path, limit=50, status="failed")
    assert windows == [50, runs.SCAN_LIMIT, runs.SCAN_LIMIT]


def _interrupted(minutes_ago, finished=False):
    moment = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat(
        timespec="milliseconds"
    )
    events = [
        {"type": "run_started", "ts": moment, "run_id": "aaaaaaaaaaaa",
         "asset_id": "panel-stuck", "capture_key": "assets/panel-stuck/capture/capture.png"},
        {"type": "tool_call", "ts": moment, "tool": "assess_quality"},
    ]
    if finished:
        events.append({"type": "run_finished", "ts": moment, "status": "failed",
                       "branch": None, "message": "RuntimeError: unavailable"})
    return events


def test_a_run_goes_stale_only_when_it_is_old_and_unfinished():
    assert runs.stale(_interrupted(30)) is True
    assert runs.stale(_interrupted(1)) is False
    assert runs.stale(_interrupted(30, finished=True)) is False
    assert runs.stale([]) is False


def test_an_interrupted_run_is_retryable_while_it_still_reads_as_running(tmp_path):
    runs.write(tmp_path / "aaaaaaaaaaaa", runs.EVENTS, _interrupted(30))
    runs.write(tmp_path / "bbbbbbbbbbbb", runs.EVENTS, _interrupted(1))
    items = {item["run_id"]: item for item in runs.recent(tmp_path)}
    assert items["aaaaaaaaaaaa"]["status"] == "running"
    assert items["aaaaaaaaaaaa"]["retryable"] is True
    assert items["bbbbbbbbbbbb"]["retryable"] is False
