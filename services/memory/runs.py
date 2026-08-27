import json
import os
from pathlib import Path

from services.memory import images

PENDING = "pending.json"

# ponytail: unbounded per-process cache of append targets; entries are small JSON arrays
_append_cache: dict[tuple[str, str], list] = {}


def _on_s3() -> bool:
    return os.environ.get("AFTERIMAGE_RUNS_S3") == "1"


def _key(run_dir: Path, name: str) -> str:
    return f"runs/{Path(run_dir).name}/{name}"


def read(run_dir: Path, name: str) -> dict | list | None:
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


def append(run_dir: Path, name: str, item) -> None:
    cache_key = (str(run_dir), name)
    items = _append_cache.get(cache_key)
    if items is None:
        items = _append_cache[cache_key] = read(run_dir, name) or []
    items.append(item)
    write(run_dir, name, items)


def delete(run_dir: Path, name: str) -> None:
    if _on_s3():
        images._s3().delete_object(Bucket=images.BUCKET, Key=_key(run_dir, name))
        return
    (Path(run_dir) / name).unlink(missing_ok=True)


def pending(runs_dir: str | Path = "runs") -> list[dict]:
    if _on_s3():
        # ponytail: single list page (1000 keys); paginate if the queue outgrows it
        listing = images._s3().list_objects_v2(Bucket=images.BUCKET, Prefix="runs/")
        run_ids = sorted(
            o["Key"].split("/")[1]
            for o in listing.get("Contents", [])
            if o["Key"].endswith(f"/{PENDING}")
        )
    else:
        run_ids = sorted(p.parent.name for p in Path(runs_dir).glob(f"*/{PENDING}"))
    return [
        payload
        for run_id in run_ids
        if (payload := read(Path(runs_dir) / run_id, PENDING)) is not None
    ]
