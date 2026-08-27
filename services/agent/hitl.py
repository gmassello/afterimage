from pathlib import Path

from services.agent import policy
from services.memory import runs, store
from services.observability import trace

APPROVED = "approved"
REJECTED = "rejected"


def commit(asset_id: str, inspection_id: str, captured_at: str, metrics: dict, image_keys: dict) -> None:
    store.put_inspection(asset_id, inspection_id, captured_at, metrics, image_keys)
    store.promote_baseline(
        asset_id,
        inspection_id,
        captured_at,
        image_keys["capture"],
        metrics["quality"]["blur_variance"],
    )


def request_approval(run_dir: Path, payload: dict) -> None:
    runs.write(run_dir, runs.PENDING, payload)


def resolve(run_dir: Path, approved: bool) -> dict:
    run_dir = Path(run_dir)
    payload = runs.read(run_dir, runs.PENDING)
    if payload is None:
        raise FileNotFoundError(run_dir / runs.PENDING)
    if approved:
        commit(
            payload["asset_id"],
            payload["run_id"],
            payload["captured_at"],
            payload["metrics"],
            payload["image_keys"],
        )
    record = policy.decision(
        "human_approved", 1.0 if approved else 0.0, 1.0, APPROVED if approved else REJECTED
    )
    trace.emit(run_dir, "decision", **record)
    runs.append(run_dir, "decisions.json", record)
    state = runs.read(run_dir, "state.json") or {}
    state["status"] = record["branch"]
    runs.write(run_dir, "state.json", state)
    runs.delete(run_dir, runs.PENDING)
    return record
