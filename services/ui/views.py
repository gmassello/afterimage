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
from services.ui.text import (
    DEFAULT_LANG,
    DEFAULT_REGISTER,
    LANGS,
    REGISTERS,
    counted,
    months,
    strings,
)

HERE = Path(__file__).parent
STATIC = HERE / "static"
THUMB_WIDTH = 180

MEDIA = {
    "css": "text/css",
    "js": "text/javascript",
    "svg": "image/svg+xml",
    "woff2": "font/woff2",
    "png": "image/png",
}

_env = Environment(
    loader=FileSystemLoader(HERE / "templates"),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)

_NAV = (
    ("/app", "nav_assets", "assets"),
    ("/activity", "nav_activity", "activity"),
    ("/queue", "nav_queue", "queue"),
)

SAMPLE_ASSET = "demo-panel"
SAMPLES = (
    ("sample-baseline", "sample_1"),
    ("sample-blurred", "sample_2"),
    ("sample-defect", "sample_3"),
    ("sample-foreign", "sample_4"),
)


def when(value, lang: str = DEFAULT_LANG) -> str:
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc)
    month = months(lang)[moment.month - 1]
    return f"{moment.day} {month} {moment.year} \u00b7 {moment:%H:%M} UTC"


_env.filters["when"] = when


def _tip(t: dict, name) -> str | None:
    return t.get(f"tip_{name}") if name else None


# ponytail: the headline metric per stage is a copy of what policy branched on; the real numbers
# are in the run trace, but reading them costs one S3 GET per row against the item we already have
_HEADLINE = {
    "assess_quality": ("blur_variance",),
    "align_to_baseline": ("inlier_ratio",),
    "diff_against_memory": ("mean_delta", "changed_ratio"),
    "crop_and_rescan": ("zoom_area_ratio", "area_ratio"),
    "classify_severity": ("score",),
}

_STAGES = tuple((stage, f"q_{tool}", _HEADLINE[tool]) for tool, stage in STAGE_OF.items())
_ORDER = tuple(STAGE_OF)

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


def _static_url(suffix: str, stem: str | None = None) -> str:
    name = next(
        name for name in _assets()
        if name.endswith(suffix) and (stem is None or name.startswith(f"{stem}."))
    )
    return f"/static/{name}"


def _samples(t: dict, asset_id: str = SAMPLE_ASSET) -> list[dict]:
    return [
        {
            "url": f"/static/{next(n for n in _assets() if n.startswith(stem + '.'))}",
            "name": f"{stem}.png",
            "asset_id": asset_id,
            "label": t[f"{key}_label"],
            "note": t[f"{key}_note"],
        }
        for stem, key in SAMPLES
    ]


def _nav(current: str, t: dict) -> list[dict]:
    if current == "landing":
        return [
            {"href": "#how-it-works", "label": t["nav_how"], "here": False},
            {"href": "#memory", "label": t["nav_memory"], "here": False},
            {"href": "#system", "label": t["nav_system"], "here": False},
            {"href": "/app", "label": t["nav_open_app"], "here": False},
        ]
    links = [
        {"href": href, "label": t[label], "here": key == current}
        for href, label, key in _NAV
    ]
    if not any(key == current for _, _, key in _NAV):
        links.append({"label": t.get(f"nav_{current}", current)})
    return links


def _render(template: str, title: str, current: str, lang: str, register: str,
            **context) -> str:
    t = strings(lang, register)
    return _env.get_template(template).render(
        title=title,
        lang=lang,
        langs=LANGS,
        register=register,
        registers=REGISTERS,
        t=t,
        nav=_nav(current, t),
        css_url=_static_url(".css", "app"),
        js_url=_static_url(".js", "app"),
        font_url=_static_url(".woff2"),
        icon_url=_static_url(".svg"),
        **context,
    )


def landing_page(metrics: list[dict] | None = None, lang: str = DEFAULT_LANG,
                 register: str = DEFAULT_REGISTER) -> str:
    t = strings(lang, register)
    shown = metrics or [
        {"value": "18 / 29", "label": t["landing_metric_real"],
         "note": t["landing_metric_real_note"]},
        {"value": "0.8621", "label": t["landing_metric_branch"],
         "note": t["landing_metric_branch_note"]},
        {"value": "0.8542", "label": t["landing_metric_defect"],
         "note": t["landing_metric_defect_note"]},
        {"value": "0.7875", "label": t["landing_metric_iou"],
         "note": t["landing_metric_iou_note"]},
    ]
    return _render(
        "landing.html", "visual inspection with memory", "landing", lang, register,
        narrow=False,
        landing_metrics=shown,
        samples=_samples(t),
        landing_js_url=_static_url(".js", "landing"),
    )


def activity_page(items: list[dict], q: str = "", status: str = "",
                  lang: str = DEFAULT_LANG, register: str = DEFAULT_REGISTER) -> str:
    return _render(
        "activity.html", strings(lang, register)["nav_activity"], "activity", lang, register,
        items=items,
        query=q,
        selected_status=status,
        status_options=(
            "", "unstarted", "running", "completed", "failed", "awaiting_approval", "approved",
            "rejected",
        ),
    )


def error_page(status_code: int, code: str, detail: str, lang: str = DEFAULT_LANG,
               register: str = DEFAULT_REGISTER) -> str:
    return _render(
        "error.html", strings(lang, register)["error_title"], "error", lang, register,
        status_code=status_code,
        error_code=code,
        detail=detail,
    )


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def _scale(value: float, threshold: float) -> float:
    top = max(abs(value), abs(threshold))
    return 1.0 if top <= 1.0 else top * 1.5


def _pct(value: float, scale: float) -> float:
    if not scale:
        return 0.0
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


def _decided_bar(verdict: dict, t: dict, large: bool = False) -> dict:
    value, threshold, branch = verdict["value"], verdict.get("threshold"), verdict.get("branch")
    head = (
        f"{verdict['input_metric']} {_fmt(float(value))}" if threshold is None
        else f"{t['bar_threshold']} {_fmt(threshold)}"
    )
    bar = _bar(value, threshold, [{"text": "0"}, {"text": head, "lit": True}], large=large)
    bar["ends"].append({"text": _fmt(bar["scale"])})
    bar["tone"] = _TONE.get(branch) if branch else None
    bar["causal"] = causal_line(verdict) if threshold is not None and branch else None
    tip = _tip(t, branch)
    bar["causal_tip"] = f"{branch}: {tip}" if tip else None
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


# ponytail: unbounded per-process cache keyed by run directory, so a run is read once per container;
# a finished trace never changes, and the key carries the runs root so tests do not collide
_verdicts: dict[str, dict] = {}


def _verdict_from_trace(run_dir: str) -> dict | None:
    cached = _verdicts.get(run_dir)
    if cached is not None:
        return cached
    decisions = _decisions(trace.read_events(Path(run_dir)))
    found = next((d for d in reversed(decisions) if d["input_metric"] == SEVERITY_METRIC), None)
    if found is not None:
        _verdicts[run_dir] = found
    return found


def _verdict_of(item: dict) -> dict | None:
    persisted = item.get("verdict") or {}
    if persisted.get("threshold") is not None:
        return persisted
    run_id = item.get("inspection_id") or item.get("run_id") or ""
    recovered = _verdict_from_trace(str(runs.runs_dir() / run_id)) if run_id else None
    return dict(recovered) if recovered else None


def _severity_bar(metrics: dict, verdict: dict | None, t: dict) -> dict | None:
    score = (metrics.get("severity") or {}).get("score")
    if score is None:
        return None
    return _decided_bar(verdict or {"input_metric": SEVERITY_METRIC, "value": float(score)}, t)


def _headline(payload: dict, keys: tuple[str, ...], t: dict) -> dict | None:
    region = (payload.get("regions") or [{}])[0]
    for key in keys:
        for source in (payload, region):
            if source.get(key) is not None:
                return {"metric": key, "tip": _tip(t, key), "value": _fmt(source[key])}
    return None


def _stage_rows(metrics: dict, t: dict) -> list[dict]:
    rows = []
    for stage, question, keys in _STAGES:
        found = _headline(metrics.get(stage) or {}, keys, t)
        if found:
            rows.append({"question": t[question], **found})
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
        "branch": str(branch or ""),
    }


def index_page(assets: list[dict], error: str = "", asset_id: str = "",
               lang: str = DEFAULT_LANG, register: str = DEFAULT_REGISTER,
               sample_asset: str = SAMPLE_ASSET) -> str:
    t = strings(lang, register)
    return _render(
        "index.html", t["nav_assets"], "assets", lang, register,
        narrow=True,
        assets=[_asset_card(asset) for asset in assets],
        asset_branches=sorted({str(asset.get("last_branch")) for asset in assets
                               if asset.get("last_branch")}),
        samples=_samples(t, sample_asset),
        error=error,
        asset_id=asset_id,
    )


def _baseline_entry(item: dict, entry: dict, t: dict) -> dict:
    superseded = item.get("superseded_by")
    entry["pills"] = [{"label": t["pill_baseline"], "on": True}]
    entry["current"] = not superseded
    entry["note"] = {"link": superseded} if superseded else {"text": t["current_baseline"]}
    entry["image_key"] = item.get("image_key", "")
    return entry


def _inspection_entry(item: dict, entry: dict, t: dict) -> dict:
    metrics = item.get("metrics") or {}
    label = (metrics.get("severity") or {}).get("label")
    entry["pills"] = [{"label": t["pill_inspection"]}]
    if label:
        entry["pills"].append({"label": str(label)})
    entry["score"] = (metrics.get("severity") or {}).get("score")
    entry["bar"] = _severity_bar(metrics, _verdict_of(item) if entry["score"] is not None else None, t)
    entry["stages"] = _stage_rows(metrics, t)
    entry["image_key"] = (item.get("image_keys") or {}).get("capture", "")
    return entry


def _timeline_entry(item: dict, t: dict) -> dict:
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
    entry = _baseline_entry(item, entry, t) if promoted else _inspection_entry(item, entry, t)
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


def asset_page(asset_id: str, items: list[dict], lang: str = DEFAULT_LANG,
               register: str = DEFAULT_REGISTER) -> str:
    ordered = sorted(
        (item for item in items if item["sk"] != store.META),
        key=lambda item: item.get("captured_at", ""),
        reverse=True,
    )
    entries = [_timeline_entry(item, strings(lang, register)) for item in ordered]
    return _render(
        "asset.html", asset_id, "assets", lang, register,
        asset_id=asset_id,
        entries=entries,
        sparkline=_sparkline(entries, Policy.from_env().severity_score_approve),
    )


def _queue_entry(item: dict, t: dict) -> dict:
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
        "bar": _severity_bar(metrics, _verdict_of(item) if severity.get("score") is not None else None, t),
        "score": _fmt(_severity_score(item)) if severity.get("score") is not None else "",
        "stages": _stage_rows(metrics, t),
        "raw_url": f"/traces/{item['run_id']}?format=json",
        "claimed": item.get("claimed"),
    }


def _severity_score(item: dict) -> float:
    score = ((item.get("metrics") or {}).get("severity") or {}).get("score")
    return float(score) if score is not None else 0.0


def queue_page(items: list[dict], assets_in_memory: int = 0, lang: str = DEFAULT_LANG,
               register: str = DEFAULT_REGISTER) -> str:
    threshold = Policy.from_env().severity_score_approve
    urgent = sorted(items, key=_severity_score, reverse=True)
    t = strings(lang, register)
    return _render(
        "queue.html", t["nav_queue"], "queue", lang, register,
        says=counted(t, "awaiting", len(items)) if items else t["queue_empty"],
        threshold=f"{threshold:g}",
        entries=[_queue_entry(item, t) for item in urgent],
        assets_in_memory=assets_in_memory,
        in_memory=counted(t, "assets_in_memory", assets_in_memory),
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


def _pills(summary: dict, calls: list[dict], t: dict) -> list[dict]:
    pills = []
    if summary.get("branch"):
        branch = str(summary["branch"])
        pills.append({"label": branch, "on": True, "tip": _tip(t, branch)})
    if summary.get("status"):
        pills.append({"label": str(summary["status"])})
    detector = next(
        (c["metrics"]["detector"] for c in calls if c.get("metrics", {}).get("detector")), None
    )
    if detector:
        pills.append({"label": f"detector: {detector}"})
    return pills


def _decider(decisions: list[dict], t: dict) -> dict | None:
    if not decisions:
        return None
    final = decisions[-1]
    return {
        "value": _fmt(final["value"]),
        "metric": final["input_metric"],
        "metric_tip": _tip(t, final["input_metric"]),
        "bar": _decided_bar(final, t, large=True),
    }


def _hero(summary: dict, events: list[dict], decisions: list[dict], t: dict) -> dict:
    calls = [e for e in events if e["type"] == "tool_call"]
    seconds = sum(float(e.get("duration_ms", 0.0)) for e in calls) / 1000.0
    return {
        "asset_id": str(summary.get("asset_id") or t["unknown_asset"]),
        "captured_at": str(summary.get("captured_at") or ""),
        "headline": str(summary.get("message") or summary.get("branch") or t["trace_headline"]),
        "calls": counted(t, "calls", len(calls)),
        "thresholds": counted(t, "thresholds", len(decisions)),
        "seconds": f"{seconds:.2f}",
        "pills": _pills(summary, calls, t),
        "decider": _decider(decisions, t),
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


def _ran_node(tool: str, attempts: list[dict], t: dict) -> dict:
    event = attempts[-1]
    branch = _branch_of(event)
    return {
        "name": tool,
        "state": "done",
        "outcome": str(branch or event.get("error") or t["no_verdict"]),
        "tone": _TONE.get(branch) if branch else None,
        "ms": _fmt(sum(float(e.get("duration_ms", 0.0)) for e in attempts)),
        "failed": "error" in event,
        "tries": len(attempts),
    }


def _idle_node(tool: str, index: int, reach: int, reason: str | None, t: dict) -> dict:
    if index > reach:
        state, outcome = "pending", t["state_waiting"]
    elif index == reach:
        state, outcome = "active", t["state_in_progress"]
    else:
        state = "skipped"
        outcome = f"{t['state_not_run']} \u00b7 {reason}" if reason else t["state_not_run"]
    return {"name": tool, "state": state, "outcome": outcome,
            "tone": None, "ms": None, "failed": False, "tries": 0}


def _path(events: list[dict], run_state: str, t: dict) -> dict | None:
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
            nodes.append(_ran_node(tool, attempts, t))
            last_branch = _branch_of(attempts[-1]) or last_branch
        else:
            reason = finished.get("branch") if finished and index > last_ran else last_branch
            nodes.append(_idle_node(tool, index, reach, reason, t))
    return {
        "kicker": t["path_taken"] if done else t["path_so_far"],
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


def _card(event: dict, t: dict) -> dict:
    policy = event.get("policy")
    bar = None
    if policy:
        ends: list[dict] = [
            {"text": f"{policy['input_metric']} {_fmt(policy['value'])}", "lit": True},
            {"text": f"{t['bar_threshold']} {_fmt(policy['threshold'])}"},
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
        "question": t.get(f"q_{event['tool']}"),
        "bar": bar,
        "facts": _flatten(facts),
        "error": event.get("error"),
        "verdict": policy["branch"] if policy else None,
        "verdict_tip": _tip(t, policy["branch"]) if policy else None,
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


def _says(events: list[dict], run_state: str, summary: dict, t: dict) -> str:
    if run_state == trace.DONE:
        ended = summary.get("branch") or summary.get("status") or t["state_finished"]
        return f"{t['state_done']} \u00b7 {ended}"
    calls = sum(1 for event in events if event["type"] == "tool_call")
    return f"{t['state_working']} \u00b7 {counted(t, 'calls', calls)}"


def _cta(summary: dict, claimed: bool | None = None) -> dict | None:
    if summary.get("status") != trace.AWAITING_APPROVAL:
        return None
    return {
        "message": str(summary.get("message") or ""),
        "run_id": str(summary.get("run_id") or ""),
        "claimed": claimed,
    }


def _chain_line(events: list[dict], t: dict) -> str:
    broken = trace.broken_at(events)
    if broken is None:
        return t["chain_intact"].format(n=len(events))
    return t["chain_broken"].format(at=broken + 1, n=len(events))


def render_html(state: dict, events: list[dict], lang: str = DEFAULT_LANG,
                register: str = DEFAULT_REGISTER, claimed: bool | None = None) -> str:
    summary = _summary(state, events)
    run_state = trace.run_state(events)
    run_id = str(summary.get("run_id") or "")
    baseline, capture, aligned = _image_refs(summary, events)
    bbox, tag = _region(events)
    t = strings(lang, register)
    return _render(
        "trace.html", t["title_trace"], "trace", lang, register,
        meta=f"run {run_id}" if run_id else "",
        says=_says(events, run_state, summary, t),
        run_state=run_state,
        execute_url=f"/runs/{run_id}/execute" if run_id else "",
        hero=_hero(summary, events, _decisions(events), t),
        path=_path(events, run_state, t),
        cards=[_card(e, t) for e in events if e["type"] == "tool_call"],
        comparison=_figures(baseline, capture, bbox, tag, aligned=aligned),
        cta=_cta(summary, claimed),
        footer={
            "run_id": run_id,
            "asset_id": str(summary.get("asset_id") or ""),
            "chain": _chain_line(events, t),
        },
    )
