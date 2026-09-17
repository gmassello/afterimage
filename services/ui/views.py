import hashlib
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from services.agent import policy as policy_module
from services.agent.loop import NEXT_TOOL, STAGE_OF
from services.agent.policy import HUMAN_GATE_METRIC, SEVERITY_METRIC, Policy
from services.memory import runs, store
from services.observability import trace
from services.observability.render import causal_line

HERE = Path(__file__).parent
STATIC = HERE / "static"
THUMB_WIDTH = 180

MEDIA = {
    "css": "text/css",
    "js": "text/javascript",
    "svg": "image/svg+xml",
    "woff2": "font/woff2",
}

_env = Environment(
    loader=FileSystemLoader(HERE / "templates"),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)

_NAV = (("/", "assets", "assets"), ("/queue", "approval queue", "queue"))


def when(value) -> str:
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc)
    return moment.strftime("%-d %b %Y \u00b7 %H:%M UTC")


_env.filters["when"] = when

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
_ORDER = tuple(STAGE_OF)

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
        media = MEDIA.get(path.suffix.lstrip(".")) if path.is_file() else None
        if media is None:
            continue
        body = path.read_bytes()
        digest = hashlib.sha256(body).hexdigest()[:8]
        built[f"{path.stem}.{digest}{path.suffix}"] = (body, media)
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
        font_url=_static_url(".woff2"),
        icon_url=_static_url(".svg"),
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
    bar["tone"] = _TONE.get(branch) if branch else None
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


def _asset_card(asset: dict) -> dict:
    key = str(asset.get("last_capture_key") or "")
    branch = asset.get("last_branch")
    label = asset.get("last_severity_label") or branch
    return {
        "asset_id": asset["asset_id"],
        "thumb": f"/images/{key}?w={THUMB_WIDTH}" if key else "",
        "captured_at": str(asset.get("last_captured_at") or ""),
        "pill": {"label": str(label), "tone": _TONE.get(str(branch))} if label else None,
    }


def index_page(assets: list[dict], error: str = "", asset_id: str = "") -> str:
    return _render(
        "index.html", "assets", "assets",
        narrow=True,
        assets=[_asset_card(asset) for asset in assets],
        error=error,
        asset_id=asset_id,
    )


def _baseline_entry(item: dict, entry: dict) -> dict:
    superseded = item.get("superseded_by")
    entry["pills"] = [{"label": "baseline", "on": True}]
    entry["current"] = not superseded
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
    entry["score"] = (metrics.get("severity") or {}).get("score")
    entry["stages"] = _stage_rows(metrics)
    entry["image_key"] = (item.get("image_keys") or {}).get("capture", "")
    return entry


def _timeline_entry(item: dict) -> dict:
    promoted = item["sk"].startswith(store.BASELINE)
    entry = {
        "promoted": promoted,
        "current": False,
        "captured_at": item.get("captured_at", ""),
        "trace_id": item.get("inspection_id", ""),
        "note": None,
        "bar": None,
        "score": None,
        "stages": [],
    }
    entry = _baseline_entry(item, entry) if promoted else _inspection_entry(item, entry)
    key = entry["image_key"]
    entry["thumb"] = f"/images/{key}?w={THUMB_WIDTH}" if key else ""
    return entry


def _plot_y(value: float, top: float) -> str:
    return f"{24.0 - _pct(value, top) * 0.2:.2f}"


def _sparkline(entries: list[dict], threshold: float) -> dict | None:
    scored = [entry for entry in reversed(entries) if entry["score"] is not None]
    if len(scored) < 2:
        return None
    top = max(max(float(entry["score"]) for entry in scored), threshold) * 1.25
    step = 100.0 / (len(scored) - 1)
    return {
        "mark": _plot_y(threshold, top),
        "points": [
            {
                "x": f"{index * step:.2f}",
                "y": _plot_y(float(entry["score"]), top),
                "tone": (entry.get("bar") or {}).get("tone") or "",
            }
            for index, entry in enumerate(scored)
        ],
    }


def asset_page(asset_id: str, items: list[dict]) -> str:
    ordered = sorted(
        (item for item in items if item["sk"] != store.META),
        key=lambda item: item.get("captured_at", ""),
        reverse=True,
    )
    entries = [_timeline_entry(item) for item in ordered]
    return _render(
        "asset.html", asset_id, "assets",
        asset_id=asset_id,
        entries=entries,
        sparkline=_sparkline(entries, Policy.from_env().severity_score_approve),
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
        "score": _fmt(_severity_score(item)) if severity.get("score") is not None else "",
        "stages": _stage_rows(metrics),
        "raw_url": f"/traces/{item['run_id']}?format=json",
    }


def _severity_score(item: dict) -> float:
    score = ((item.get("metrics") or {}).get("severity") or {}).get("score")
    return float(score) if score is not None else 0.0


def queue_page(items: list[dict], assets_in_memory: int = 0) -> str:
    threshold = Policy.from_env().severity_score_approve
    urgent = sorted(items, key=_severity_score, reverse=True)
    return _render(
        "queue.html", "approval queue", "queue",
        says=f"{len(items)} awaiting approval" if items else "nothing awaiting approval",
        threshold=f"{threshold:g}",
        entries=[_queue_entry(item) for item in urgent],
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
    finished = _finished(events) or {}
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


def _branch_of(event: dict) -> str | None:
    return (event.get("policy") or {}).get("branch")


def _finished(events: list[dict]) -> dict | None:
    return next((event for event in reversed(events) if event["type"] == "run_finished"), None)


def _calls_by_tool(events: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for event in events:
        if event["type"] == "tool_call" and event.get("tool") in STAGE_OF:
            grouped.setdefault(event["tool"], []).append(event)
    return grouped


def _expected_tool(events: list[dict]) -> str | None:
    expected: str | None = _ORDER[0]
    for event in events:
        if event["type"] != "tool_call" or event.get("tool") not in STAGE_OF:
            continue
        branch = _branch_of(event)
        if branch is None:
            continue
        expected = NEXT_TOOL.get(branch)
    return expected


def _ran_node(tool: str, attempts: list[dict]) -> dict:
    event = attempts[-1]
    branch = _branch_of(event)
    return {
        "name": tool,
        "state": "done",
        "outcome": str(branch or event.get("error") or "no verdict"),
        "tone": _TONE.get(branch) if branch else None,
        "ms": _fmt(sum(float(e.get("duration_ms", 0.0)) for e in attempts)),
        "failed": "error" in event,
        "tries": len(attempts),
    }


def _idle_node(tool: str, index: int, reach: int, reason: str | None) -> dict:
    if index > reach:
        state, outcome = "pending", "waiting"
    elif index == reach:
        state, outcome = "active", "working\u2026"
    else:
        state = "skipped"
        outcome = f"not run \u00b7 {reason}" if reason else "not run"
    return {"name": tool, "state": state, "outcome": outcome,
            "tone": None, "ms": None, "failed": False, "tries": 0}


def _path(events: list[dict], run_state: str) -> dict | None:
    calls = _calls_by_tool(events)
    done = run_state == trace.DONE
    if done and not calls:
        return None
    expected = _expected_tool(events)
    reach = len(_ORDER) if done or expected is None else _ORDER.index(expected)
    finished = _finished(events)
    last_ran = max((index for index, tool in enumerate(_ORDER) if tool in calls), default=-1)
    nodes: list[dict] = []
    last_branch: str | None = None
    for index, tool in enumerate(_ORDER):
        attempts = calls.get(tool)
        if attempts:
            nodes.append(_ran_node(tool, attempts))
            last_branch = _branch_of(attempts[-1]) or last_branch
        else:
            reason = finished.get("branch") if finished and index > last_ran else last_branch
            nodes.append(_idle_node(tool, index, reach, reason))
    return {
        "kicker": "the path this run took" if done else "the path so far",
        "steps": nodes,
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
        ends: list[dict] = [
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


def _says(events: list[dict], run_state: str, summary: dict) -> str:
    if run_state == trace.DONE:
        return f"done \u00b7 {summary.get('branch') or summary.get('status') or 'finished'}"
    calls = sum(1 for event in events if event["type"] == "tool_call")
    return f"working \u00b7 {calls} tool call{'' if calls == 1 else 's'}"


def _cta(summary: dict) -> dict | None:
    if summary.get("status") != trace.AWAITING_APPROVAL:
        return None
    return {
        "message": str(summary.get("message") or ""),
        "run_id": str(summary.get("run_id") or ""),
    }


def _chain_line(events: list[dict]) -> str:
    broken = trace.broken_at(events)
    if broken is None:
        return f"sha256 chain intact over {len(events)} events"
    return f"sha256 chain broken at event {broken + 1} of {len(events)}"


def render_html(state: dict, events: list[dict]) -> str:
    summary = _summary(state, events)
    run_state = trace.run_state(events)
    run_id = str(summary.get("run_id") or "")
    baseline, capture, aligned = _image_refs(summary, events)
    bbox, tag = _region(events)
    return _render(
        "trace.html", "inspection trace", "trace",
        meta=f"run {run_id}" if run_id else "",
        says=_says(events, run_state, summary),
        run_state=run_state,
        execute_url=f"/runs/{run_id}/execute" if run_id else "",
        hero=_hero(summary, events, _decisions(events)),
        path=_path(events, run_state),
        cards=[_card(e) for e in events if e["type"] == "tool_call"],
        comparison=_figures(baseline, capture, bbox, tag, aligned=aligned),
        cta=_cta(summary),
        footer={
            "run_id": run_id,
            "asset_id": str(summary.get("asset_id") or ""),
            "chain": _chain_line(events),
        },
    )
