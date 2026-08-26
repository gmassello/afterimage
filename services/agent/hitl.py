import json
from pathlib import Path

from services.agent import policy
from services.memory import store
from services.observability import trace
from services.observability.trace import write_json

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


def request_approval(run_dir: Path, payload: dict) -> Path:
    path = Path(run_dir) / "pending.json"
    write_json(path, payload)
    return path


def resolve(run_dir: Path, approved: bool) -> dict:
    run_dir = Path(run_dir)
    pending_path = run_dir / "pending.json"
    payload = json.loads(pending_path.read_text())
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
    decisions_path = run_dir / "decisions.json"
    decisions = json.loads(decisions_path.read_text())
    decisions.append(record)
    write_json(decisions_path, decisions)
    state_path = run_dir / "state.json"
    state = json.loads(state_path.read_text())
    state["status"] = record["branch"]
    write_json(state_path, state)
    pending_path.unlink()
    return record
