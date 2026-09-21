import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from botocore.exceptions import ClientError

from services.memory import images

PENDING = "pending.json"
EVENTS = "events.json"
STATE = "state.json"
RETRY = "retry.json"
VERDICT = "verdict.json"

STALE_AFTER_SECONDS = 900
SCAN_LIMIT = 200


def _on_s3() -> bool:
    return os.environ.get("AFTERIMAGE_RUNS_S3") == "1"


def runs_dir() -> Path:
    return Path(os.environ.get("AFTERIMAGE_RUNS_DIR", "runs"))


def _key(run_dir: Path, name: str) -> str:
    return f"runs/{Path(run_dir).name}/{name}"


def read(run_dir: Path, name: str) -> Any:
    if _on_s3():
        client = images._s3()
        try:
            body = client.get_object(Bucket=images.BUCKET, Key=_key(run_dir, name))["Body"].read()
        except client.exceptions.NoSuchKey:
            return None
        return json.loads(body)
    path = Path(run_dir) / name
    return json.loads(path.read_text()) if path.exists() else None


def write(run_dir: Path, name: str, data) -> None:
    if _on_s3():
        images._s3().put_object(Bucket=images.BUCKET, Key=_key(run_dir, name), Body=json.dumps(data, indent=2))
        return
    path = Path(run_dir) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def write_once(run_dir: Path, name: str, data) -> tuple[bool, Any]:
    if _on_s3():
        try:
            images._s3().put_object(
                Bucket=images.BUCKET,
                Key=_key(run_dir, name),
                Body=json.dumps(data, indent=2),
                IfNoneMatch="*",
            )
        except ClientError as rejected:
            code = rejected.response.get("Error", {}).get("Code")
            if code not in ("PreconditionFailed", "ConditionalRequestConflict"):
                raise
            return False, read(run_dir, name)
        return True, data
    path = Path(run_dir) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{name}.")
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump(data, output, indent=2)
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            return False, read(run_dir, name)
        return True, data
    finally:
        Path(temporary).unlink(missing_ok=True)


def append(run_dir: Path, name: str, item) -> None:
    items = read(run_dir, name) or []
    items.append(item)
    write(run_dir, name, items)


def last(run_dir: Path, name: str) -> Any:
    items = read(run_dir, name) or []
    return items[-1] if items else None


def delete(run_dir: Path, name: str) -> None:
    if _on_s3():
        images._s3().delete_object(Bucket=images.BUCKET, Key=_key(run_dir, name))
        return
    (Path(run_dir) / name).unlink(missing_ok=True)


def pending(runs_dir: str | Path = "runs") -> list[dict]:
    payloads = [
        payload
        for run_id in _run_ids(runs_dir, PENDING)
        if (payload := read(Path(runs_dir) / run_id, PENDING)) is not None
    ]
    return sorted(payloads, key=lambda payload: payload.get("captured_at", ""))



def _run_ids(root: str | Path, name: str = EVENTS, limit: int | None = None) -> list[str]:
    if not _on_s3():
        return [path.parent.name for path in Path(root).glob(f"*/{name}")]
    paginator = images._s3().get_paginator("list_objects_v2")
    found = [
        item
        for page in paginator.paginate(Bucket=images.BUCKET, Prefix="runs/")
        for item in page.get("Contents", [])
        if item["Key"].endswith(f"/{name}")
    ]
    found.sort(key=lambda item: item["LastModified"], reverse=True)
    return [item["Key"].split("/")[1] for item in (found[:limit] if limit else found)]


def stale(events: list[dict], now: datetime | None = None) -> bool:
    if not events or any(event.get("type") == "run_finished" for event in events):
        return False
    last = datetime.fromisoformat(events[-1]["ts"])
    moment = now or datetime.now(timezone.utc)
    return moment - last > timedelta(seconds=STALE_AFTER_SECONDS)


def _summary(root: str | Path, run_id: str) -> dict | None:
    run_dir = Path(root) / run_id
    events = read(run_dir, EVENTS) or []
    started = next((event for event in events if event.get("type") == "run_started"), None)
    if started is None:
        return None
    finished = next(
        (event for event in reversed(events) if event.get("type") == "run_finished"),
        None,
    )
    state = read(run_dir, STATE) or {}
    status = state.get("status") or (finished or {}).get("status")
    if status is None:
        status = "running" if len(events) > 1 else "unstarted"
    return {
        "run_id": run_id,
        "asset_id": started.get("asset_id", ""),
        "capture_key": started.get("capture_key", ""),
        "captured_at": started.get("ts", ""),
        "updated_at": events[-1].get("ts", ""),
        "status": status,
        "branch": state.get("branch") or (finished or {}).get("branch"),
        "message": state.get("message") or (finished or {}).get("message") or "",
        "retryable": status == "failed" or (status == "running" and stale(events)),
    }


def recent(root: str | Path = "runs", limit: int = 50, q: str = "",
           status: str = "") -> list[dict]:
    query = q.strip().lower()
    wanted_status = status.strip().lower()
    # ponytail: filters reach the most recent SCAN_LIMIT runs, not the whole history; a run index
    # is the upgrade if the archive ever needs to be searchable in full
    window = SCAN_LIMIT if (query or wanted_status) else limit
    items = [item for run_id in _run_ids(root, limit=window) if (item := _summary(root, run_id))]
    if query:
        items = [
            item for item in items
            if query in " ".join(str(value).lower() for value in item.values())
        ]
    if wanted_status:
        items = [item for item in items if str(item["status"]).lower() == wanted_status]
    return sorted(items, key=lambda item: item["updated_at"], reverse=True)[:limit]
