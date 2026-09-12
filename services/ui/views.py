import hashlib
import json
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from services.agent import policy as policy_module
from services.agent.loop import STAGE_OF
from services.agent.policy import HUMAN_GATE_METRIC, SEVERITY_METRIC, Policy
from services.memory import runs, store
from services.observability import trace
from services.observability.render import causal_line

HERE = Path(__file__).parent
STATIC = HERE / "static"
MEDIA = {"css": "text/css", "js": "text/javascript"}

_env = Environment(
    loader=FileSystemLoader(HERE / "templates"),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)

_NAV = (("/", "assets", "assets"), ("/queue", "approval queue", "queue"))

_QUESTION = {
    "assess_quality": "Is this capture worth scoring at all?",
    "align_to_baseline": "Is this the same asset as the one in memory?",
    "diff_against_memory": "Has anything changed since the baseline — enough to be sure?",
    "crop_and_rescan": "Is the changed region large enough to be real?",
    "classify_severity": "What kind of defect, and can it be written unattended?",
}

# ponytail: the headline metric per stage is a copy of what policy branched on; the real numbers
# are in the run trace, but reading them costs one S3 GET per row against the item we already have
_HEADLINE = {
    "assess_quality": ("blur_variance",),
    "align_to_baseline": ("inlier_ratio",),
    "diff_against_memory": ("mean_delta", "changed_ratio"),
    "crop_and_rescan": ("area_ratio", "changed_ratio"),
    "classify_severity": ("score",),
}

_STAGES = tuple((stage, _QUESTION[tool], _HEADLINE[tool]) for tool, stage in STAGE_OF.items())

_TIP = {
    "blur_variance": "How sharp the capture is. Low means the photo is too soft to score.",
    "inlier_ratio": "Share of matched keypoints that agree on one geometry. Low means this is "
                    "not the asset memory holds.",
    "mean_delta": "Average pixel difference against the baseline, inside the changed region.",
    "area_ratio": "How much of the frame the changed region covers.",
    "changed_ratio": "Share of the aligned frame whose pixels moved at all since the baseline.",
    "score": "Severity of the change, 0 to 1. Above the threshold nothing is written without a "
             "human.",
    policy_module.RECAPTURE: "The capture was not good enough to score. The agent asked for "
                             "another photo.",
    policy_module.QUALITY_OK: "The capture was sharp and well exposed enough to score.",
    policy_module.RETRY_CLASSIC: "Modern features failed to match, so the agent retried with the "
                                 "classic detector.",
    policy_module.UNRECOGNIZED_ASSET: "Too few matches to believe this is the same asset. The "
                                      "agent refused rather than guess.",
    policy_module.ALIGNED: "The capture was anchored to the stored baseline of the same asset.",
    policy_module.NO_CHANGE: "Nothing changed enough since the baseline to be worth reporting.",
    policy_module.CROP_AND_RESCAN: "The change was borderline, so the agent zoomed in and "
                                   "measured again.",
    policy_module.CHANGE_CONFIRMED: "The change survived a closer look and is real.",
    policy_module.HUMAN_APPROVAL: "Severe enough that nothing is written to memory until a person "
                                  "approves it.",
    policy_module.AUTO_WRITE: "Mild enough for the agent to write to memory on its own.",
    policy_module.FIRST_BASELINE: "The first capture of this asset. There was nothing to compare "
                                  "it against.",
}

_TONE = {
    policy_module.QUALITY_OK: "ok",
    policy_module.ALIGNED: "ok",
    policy_module.NO_CHANGE: "ok",
    policy_module.CHANGE_CONFIRMED: "ok",
    policy_module.AUTO_WRITE: "ok",
    policy_module.FIRST_BASELINE: "ok",
    policy_module.RECAPTURE: "warn",
    policy_module.RETRY_CLASSIC: "warn",
    policy_module.CROP_AND_RESCAN: "warn",
    policy_module.HUMAN_APPROVAL: "warn",
    policy_module.UNRECOGNIZED_ASSET: "bad",
}


@lru_cache(maxsize=1)
def _assets() -> dict[str, tuple[bytes, str]]:
    built = {}
    for path in sorted(STATIC.iterdir()):
        body = path.read_bytes()
        digest = hashlib.sha256(body).hexdigest()[:8]
        built[f"{path.stem}.{digest}{path.suffix}"] = (body, MEDIA[path.suffix.lstrip(".")])
    return built


def static_asset(name: str) -> tuple[bytes, str] | None:
    return _assets().get(name)


def _static_url(suffix: str) -> str:
    return f"/static/{next(name for name in _assets() if name.endswith(suffix))}"


def _nav(current: str) -> list[dict]:
    links = [
        {"href": href, "label": label, "here": key == current}
        for href, label, key in _NAV
    ]
    if not any(key == current for _, _, key in _NAV):
        links.append({"label": current})
    return links


def _render(template: str, title: str, current: str, **context) -> str:
    return _env.get_template(template).render(
        title=title,
        nav=_nav(current),
        css_url=_static_url(".css"),
        js_url=_static_url(".js"),
        **context,
    )


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def _scale(value: float, threshold: float) -> float:
    top = max(abs(value), abs(threshold))
    if top == 0.0:
        return 1.0
    return 1.0 if top <= 1.0 else top * 1.5


def _pct(value: float, scale: float) -> float:
    return max(0.0, min(100.0, value / scale * 100.0))


def _bar(value: float, threshold: float | None, ends: list[dict], large: bool = False) -> dict:
    value = float(value)
    scale = _scale(value, float(threshold) if threshold is not None else value)
    return {
        "at": f"{_pct(value, scale):.2f}",
        "mark": None if threshold is None else f"{_pct(float(threshold), scale):.2f}",
        "ends": ends,
        "large": large,
        "scale": scale,
    }


def _decided_bar(verdict: dict, large: bool = False) -> dict:
    value, threshold, branch = verdict["value"], verdict.get("threshold"), verdict.get("branch")
    head = (
        f"{verdict['input_metric']} {_fmt(float(value))}" if threshold is None
        else f"threshold {_fmt(threshold)}"
    )
    bar = _bar(value, threshold, [{"text": "0"}, {"text": head, "lit": True}], large=large)
    bar["ends"].append({"text": _fmt(bar["scale"])})
    bar["tone"] = _TONE.get(branch)
    bar["causal"] = causal_line(verdict) if threshold is not None and branch else None
    bar["causal_tip"] = f"{branch}: {_TIP[branch]}" if branch in _TIP else None
    return bar


def _tag(label, delta) -> dict:
    return {
        "label": str(label) if label else None,
        "delta": _fmt(float(delta)) if delta is not None else None,
    }


def _figures(baseline_key: str, capture_key: str, bbox=None, tag: dict | None = None,
             aligned: bool = False) -> dict | None:
    if not (baseline_key and capture_key):
        return None
    return {
        "baseline_key": baseline_key,
        "capture_key": capture_key,
        "bbox": list(bbox) if bbox else None,
        "tag": tag or {},
        "aligned": aligned,
    }


# ponytail: per-process cache keyed by run directory, so a run is read once per container;
# a finished trace never changes, and the key carries the runs root so tests do not collide
@lru_cache(maxsize=128)
def _verdict_from_trace(run_dir: str) -> dict | None:
    decisions = _decisions(trace.read_events(Path(run_dir)))
    return next((d for d in reversed(decisions) if d["input_metric"] == SEVERITY_METRIC), None)


def _verdict_of(item: dict) -> dict | None:
    persisted = item.get("verdict") or {}
    if persisted.get("threshold") is not None:
        return persisted
    run_id = item.get("inspection_id") or item.get("run_id") or ""
    recovered = _verdict_from_trace(str(runs.runs_dir() / run_id)) if run_id else None
    return dict(recovered) if recovered else None


def _severity_bar(metrics: dict, verdict: dict | None) -> dict | None:
    score = (metrics.get("severity") or {}).get("score")
    if score is None:
        return None
    return _decided_bar(verdict or {"input_metric": SEVERITY_METRIC, "value": float(score)})


def _headline(payload: dict, keys: tuple[str, ...]) -> dict | None:
    region = (payload.get("regions") or [{}])[0]
    for key in keys:
        for source in (payload, region):
            if source.get(key) is not None:
                return {"metric": key, "tip": _TIP.get(key), "value": _fmt(source[key])}
    return None


def _stage_rows(metrics: dict) -> list[dict]:
    rows = []
    for stage, question, keys in _STAGES:
        found = _headline(metrics.get(stage) or {}, keys)
        if found:
            rows.append({"question": question, **found})
    return rows


def index_page(assets: list[dict], error: str = "") -> str:
    return _render(
        "index.html", "assets", "assets",
        narrow=True,
        assets=[asset["asset_id"] for asset in assets],
        error=error,
    )


def _baseline_entry(item: dict, entry: dict) -> dict:
    superseded = item.get("superseded_by")
    entry["pills"] = [{"label": "baseline", "on": True}]
    entry["note"] = {"link": superseded} if superseded else {"text": "current baseline"}
    entry["image_key"] = item.get("image_key", "")
    return entry


def _inspection_entry(item: dict, entry: dict) -> dict:
    metrics = item.get("metrics") or {}
    label = (metrics.get("severity") or {}).get("label")
    entry["pills"] = [{"label": "inspection"}]
    if label:
        entry["pills"].append({"label": str(label)})
    entry["bar"] = _severity_bar(metrics, _verdict_of(item))
    entry["stages"] = _stage_rows(metrics)
    entry["image_key"] = (item.get("image_keys") or {}).get("capture", "")
    return entry


def _timeline_entry(item: dict) -> dict:
    promoted = item["sk"].startswith(store.BASELINE)
    entry = {
        "promoted": promoted,
        "captured_at": item.get("captured_at", ""),
        "trace_id": item.get("inspection_id", ""),
        "note": None,
        "bar": None,
        "stages": [],
    }
    if promoted:
        return _baseline_entry(item, entry)
    return _inspection_entry(item, entry)


def asset_page(asset_id: str, items: list[dict]) -> str:
    ordered = sorted(
        (item for item in items if item["sk"] != store.META),
        key=lambda item: item.get("captured_at", ""),
        reverse=True,
    )
    return _render(
        "asset.html", asset_id, "assets",
        asset_id=asset_id,
        entries=[_timeline_entry(item) for item in ordered],
    )


def _queue_entry(item: dict) -> dict:
    metrics = item.get("metrics") or {}
    diff, severity = metrics.get("diff") or {}, metrics.get("severity") or {}
    region = (diff.get("regions") or [{}])[0]
    image_keys = item.get("image_keys") or {}
    warped = image_keys.get("aligned")
    return {
        "run_id": item["run_id"],
        "asset_id": item.get("asset_id", ""),
        "message": item.get("message", ""),
        "figures": _figures(
            image_keys.get("baseline", ""),
            warped or image_keys.get("capture", ""),
            region.get("bbox"),
            _tag(severity.get("label"), region.get("mean_delta")),
            aligned=bool(warped),
        ),
        "bar": _severity_bar(metrics, _verdict_of(item)),
        "stages": _stage_rows(metrics),
        "raw_url": f"/traces/{item['run_id']}?format=json",
    }


def queue_page(items: list[dict], assets_in_memory: int = 0) -> str:
    threshold = Policy.from_env().severity_score_approve
    return _render(
        "queue.html", "approval queue", "queue",
        threshold=f"{threshold:g}",
        entries=[_queue_entry(item) for item in items],
        assets_in_memory=assets_in_memory,
    )


def _policy_of(event: dict) -> dict | None:
    if event["type"] == "tool_call":
        return event.get("policy")
    if event["type"] != "decision" or event["input_metric"] == HUMAN_GATE_METRIC:
        return None
    return event


def _decisions(events: list[dict]) -> list[dict]:
    return [d for d in (_policy_of(e) for e in events) if d]


def _summary(state: dict, events: list[dict]) -> dict:
    started = trace.started_event(events) or {}
    finished = next((e for e in reversed(events) if e["type"] == "run_finished"), {})
    merged = {
        "run_id": started.get("run_id"),
        "asset_id": started.get("asset_id"),
        "capture_key": started.get("capture_key"),
        "captured_at": started.get("ts"),
        "status": finished.get("status"),
        "branch": finished.get("branch"),
        "message": finished.get("message"),
    }
    merged.update({key: value for key, value in state.items() if value is not None})
    return merged


def _pills(summary: dict, calls: list[dict]) -> list[dict]:
    pills = []
    if summary.get("branch"):
        branch = str(summary["branch"])
        pills.append({"label": branch, "on": True, "tip": _TIP.get(branch)})
    if summary.get("status"):
        pills.append({"label": str(summary["status"])})
    detector = next(
        (c["metrics"]["detector"] for c in calls if c.get("metrics", {}).get("detector")), None
    )
    if detector:
        pills.append({"label": f"detector: {detector}"})
    return pills


def _decider(decisions: list[dict]) -> dict | None:
    if not decisions:
        return None
    final = decisions[-1]
    return {
        "value": _fmt(final["value"]),
        "metric": final["input_metric"],
        "metric_tip": _TIP.get(final["input_metric"]),
        "bar": _decided_bar(final, large=True),
    }


def _hero(summary: dict, events: list[dict], decisions: list[dict]) -> dict:
    calls = [e for e in events if e["type"] == "tool_call"]
    seconds = sum(float(e.get("duration_ms", 0.0)) for e in calls) / 1000.0
    return {
        "asset_id": str(summary.get("asset_id") or "unknown asset"),
        "captured_at": str(summary.get("captured_at") or ""),
        "headline": str(summary.get("message") or summary.get("branch") or "Inspection trace"),
        "calls": len(calls),
        "thresholds": len(decisions),
        "seconds": f"{seconds:.2f}",
        "pills": _pills(summary, calls),
        "decider": _decider(decisions),
    }


def _not_taken(events: list[dict]) -> list[dict]:
    ghosts = []
    for event in events:
        policy = _policy_of(event)
        if not policy:
            continue
        ghosts.append({
            "tool": event.get("tool", "decision"),
            "metric": policy["input_metric"],
            "value": _fmt(policy["value"]),
            "threshold": _fmt(policy["threshold"]),
            "above": policy["value"] < policy["threshold"],
        })
    return ghosts


def _path(events: list[dict], run_state: str) -> dict | None:
    steps = [
        {
            "name": event["tool"],
            "outcome": str(
                event["policy"]["branch"] if event.get("policy")
                else event.get("error", "no verdict")
            ),
            "ms": _fmt(event.get("duration_ms", 0.0)),
            "failed": "error" in event,
        }
        for event in events if event["type"] == "tool_call"
    ]
    pending = run_state != trace.DONE
    if not (steps or pending):
        return None
    return {
        "kicker": "the path this run took" if run_state == trace.DONE else "the path so far",
        "steps": steps,
        "pending": pending,
        "not_taken": _not_taken(events),
    }


def _flatten(data: dict) -> list[dict]:
    rows = []
    for key, value in data.items():
        if isinstance(value, dict):
            rows.extend(_flatten(value))
        else:
            rows.append({"key": str(key), "value": _fmt(value)})
    return rows


def _card(event: dict) -> dict:
    policy = event.get("policy")
    bar = None
    if policy:
        word = "max" if policy["value"] < policy["threshold"] else "min"
        ends = [
            {"text": f"{policy['input_metric']} {_fmt(policy['value'])}", "lit": True},
            {"text": f"{word} {_fmt(policy['threshold'])}"},
        ]
        bar = _bar(policy["value"], policy["threshold"], ends)
        bar["tone"] = _TONE.get(policy["branch"])
    facts = {
        key: value
        for key, value in event.get("metrics", {}).items()
        if not str(key).endswith("_key") and not isinstance(value, list)
    }
    facts.update(policy.get("extra", {}) if policy else {})
    return {
        "name": event["tool"],
        "ms": _fmt(event.get("duration_ms", 0.0)),
        "question": _QUESTION.get(event["tool"]),
        "bar": bar,
        "facts": _flatten(facts),
        "error": event.get("error"),
        "verdict": policy["branch"] if policy else None,
        "verdict_tip": _TIP.get(policy["branch"]) if policy else None,
    }


def _image_refs(summary: dict, events: list[dict]) -> tuple[str, str, bool]:
    baseline, warped = "", ""
    for event in events:
        if event.get("tool") != "align_to_baseline":
            continue
        baseline = event.get("args", {}).get("baseline_key") or baseline
        warped = event.get("metrics", {}).get("aligned_key") or warped
    return baseline, warped or str(summary.get("capture_key") or ""), bool(warped)


def _region(events: list[dict]) -> tuple[list | None, dict]:
    bbox, delta, label = None, None, ""
    for event in events:
        policy = event.get("policy") or {}
        if "bbox" in policy.get("extra", {}):
            bbox = policy["extra"]["bbox"]
            if policy["input_metric"] == "mean_delta":
                delta = policy["value"]
        if event.get("tool") == "classify_severity":
            label = event.get("metrics", {}).get("label") or label
    return bbox, _tag(label, delta)


def _cta(summary: dict) -> dict | None:
    if summary.get("status") != trace.AWAITING_APPROVAL:
        return None
    return {
        "message": str(summary.get("message") or ""),
        "run_id": str(summary.get("run_id") or ""),
    }


def render_html(state: dict, events: list[dict]) -> str:
    summary = _summary(state, events)
    run_state = trace.run_state(events)
    run_id = str(summary.get("run_id") or "")
    baseline, capture, aligned = _image_refs(summary, events)
    bbox, tag = _region(events)
    return _render(
        "trace.html", "inspection trace", "trace",
        meta=f"run {run_id}" if run_id else "",
        run_state=run_state,
        execute_url=f"/runs/{run_id}/execute" if run_id else "",
        hero=_hero(summary, events, _decisions(events)),
        path=_path(events, run_state),
        cards=[_card(e) for e in events if e["type"] == "tool_call"],
        comparison=_figures(baseline, capture, bbox, tag, aligned=aligned),
        cta=_cta(summary),
        footer={"run_id": run_id, "asset_id": str(summary.get("asset_id") or "")},
    )
