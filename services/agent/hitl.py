import time
from pathlib import Path

from services.agent import jev, policy
from services.memory import images, runs, store
from services.observability import trace

APPROVED = "approved"
REJECTED = "rejected"

PROMOTED = "promoted"
HISTORICAL = "historical"
MISSING = "missing"
JEV_REJECTION = "jev_rejection"


class AlreadyResolved(Exception):
    pass


def commit(
    asset_id: str,
    inspection_id: str,
    captured_at: str,
    metrics: dict,
    image_keys: dict,
    verdict: dict | None = None,
) -> bool:
    store.put_inspection(asset_id, inspection_id, captured_at, metrics, image_keys, verdict)
    return store.promote_baseline(
        asset_id,
        inspection_id,
        captured_at,
        image_keys["capture"],
        metrics["quality"]["blur_variance"],
    )


def reobserve(asset_id: str, inspection_id: str, promoted: bool) -> dict:
    stored = next(
        (
            item for item in store.history(asset_id)
            if item["sk"].startswith(store.BASELINE) and item.get("inspection_id") == inspection_id
        ),
        None,
    )
    current = store.current_baseline(asset_id)
    if stored is None or not images.exists(stored["image_key"]):
        observed = MISSING
    elif current is not None and current["inspection_id"] == inspection_id:
        observed = PROMOTED
    else:
        observed = HISTORICAL
    expected = PROMOTED if promoted else HISTORICAL
    return policy.evaluate(
        "reobserve",
        {
            policy.REOBSERVE_METRIC: 1.0 if observed == expected else 0.0,
            "extra": {"expected": expected, "observed": observed},
        },
        policy.Policy.from_env(),
    )


def _emit_once(run_dir: Path, record: dict) -> None:
    if not any(
        event["type"] == "decision" and event.get("input_metric") == record["input_metric"]
        for event in trace.read_events(run_dir)
    ):
        trace.emit(run_dir, "decision", **record)


def request_approval(run_dir: Path, payload: dict) -> None:
    runs.write(run_dir, runs.PENDING, payload)


def classify_rejection(run_dir: Path, reason: str) -> None:
    if not jev.configured() or any(
        event.get("tool") == JEV_REJECTION for event in trace.read_events(run_dir)
    ):
        return
    began = time.perf_counter()
    probability, error = jev.capture_artefact(reason)
    span = {
        "tool": JEV_REJECTION,
        "args": {"reason": reason},
        "duration_ms": round((time.perf_counter() - began) * 1000, 1),
    }
    if probability is None:
        trace.emit(run_dir, "tool_call", **span, error=error)
        return
    metrics = {policy.REJECTION_METRIC: probability}
    record = policy.evaluate("rejection", metrics, policy.Policy.from_env())
    trace.emit(run_dir, "tool_call", **span, metrics=metrics, policy=record)


def resolve(
    run_dir: Path, approved: bool, actor: str | None = None, reason: str | None = None
) -> dict:
    run_dir = Path(run_dir)
    payload = runs.read(run_dir, runs.PENDING)
    if payload is None:
        raise FileNotFoundError(run_dir / runs.PENDING)
    claimed, stored = runs.write_once(
        run_dir, runs.VERDICT, {"approved": approved, "actor": actor, "reason": reason}
    )
    if not claimed and stored.get("approved") != approved:
        raise AlreadyResolved(run_dir / runs.VERDICT)
    actor, reason = stored.get("actor"), stored.get("reason")
    extra = {"actor": actor} if actor else {}
    if reason:
        extra["reason"] = reason
    observation = None
    if approved:
        promoted = commit(
            payload["asset_id"],
            payload["run_id"],
            payload["captured_at"],
            payload["metrics"],
            payload["image_keys"],
            payload.get("verdict"),
        )
        extra["baseline"] = PROMOTED if promoted else HISTORICAL
        observation = reobserve(payload["asset_id"], payload["run_id"], promoted)
    record = policy.decision(
        policy.HUMAN_GATE_METRIC,
        1.0 if approved else 0.0,
        1.0,
        APPROVED if approved else REJECTED,
        **extra,
    )
    _emit_once(run_dir, record)
    if observation is not None:
        _emit_once(run_dir, observation)
    if not approved and reason:
        classify_rejection(run_dir, reason)
    state = runs.read(run_dir, "state.json") or {}
    state["status"] = record["branch"]
    runs.write(run_dir, "state.json", state)
    runs.delete(run_dir, runs.PENDING)
    return record
