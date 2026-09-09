import argparse
import html
import json
from pathlib import Path

from services.memory import runs
from services.observability import trace


def load_run(run_dir: Path) -> tuple[dict, list[dict]]:
    run_dir = Path(run_dir)
    events = trace.read_events(run_dir)
    finished = trace.run_state(events) == trace.DONE
    return (runs.read(run_dir, "state.json") or {}) if finished else {}, events


def causal_line(decision: dict) -> str:
    op = "<" if decision["value"] < decision["threshold"] else ">="
    return (
        f"{decision['input_metric']} {decision['value']} {op} "
        f"{decision['threshold']} -> {decision['branch']}"
    )


def _text_line(event: dict) -> str:
    kind = event["type"]
    if kind == "run_started":
        return f"run {event['run_id']} started  asset={event['asset_id']}  capture={event['capture_key']}"
    if kind == "tool_call":
        head = f"{event['tool']} ({event['duration_ms']} ms)"
        if "error" in event:
            return f"{head}  error: {event['error']}"
        if "policy" in event:
            return f"{head}  {causal_line(event['policy'])}"
        return head
    if kind == "decision":
        return causal_line(event)
    if kind == "approval_requested":
        return f"approval requested: {event['message']}"
    if kind == "run_finished":
        message = f"  {event['message']}" if event.get("message") else ""
        return f"run finished: {event['status']} ({event['branch']}){message}"
    return json.dumps(event)


def render_text(events: list[dict]) -> str:
    return "\n".join(f"[{e['ts']}] {_text_line(e)}" for e in events)


BASE_STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root {
  --color-bg: #161826; --color-surface: #232532; --color-text: #e9e9ed;
  --color-accent: #9184d9; --accent-hover: #b5abfc;
  --color-divider: color-mix(in srgb, #e9e9ed 16%, transparent);
  --shadow-sm: 0 0 0 1px #3f424d;
  --shadow-md: 0 0 0 1px #595d6c, 0 6px 18px rgba(0,0,0,0.55);
  --track: #292b31; --dim: #75798c; --lit: #b5abfc; --lit-soft: #423a6a;
  --scrim: rgba(22,24,38,0.45); --bad: #ffa198;
  --font-heading: "Inter", system-ui, sans-serif;
  --font-body: "Inter", system-ui, sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, monospace;
  color-scheme: dark;
}
:root[data-theme='light'] {
  --color-bg: #e4e7f5; --color-surface: #f3f5fe; --color-text: #292b31;
  --color-accent: #5d5294; --accent-hover: #423a6a;
  --color-divider: color-mix(in srgb, #292b31 16%, transparent);
  --shadow-sm: 0 0 0 1px #cfd3e5;
  --shadow-md: 0 0 0 1px #cfd3e5, 0 6px 18px rgba(41,43,49,0.10);
  --track: #cfd3e5; --dim: #75798c; --lit: #5d5294; --lit-soft: #d2cefd;
  --scrim: rgba(228,231,245,0.45); --bad: #a03028;
  color-scheme: light;
}
*, *::before, *::after { box-sizing: border-box; }
body { margin: 0; background: var(--color-bg); color: var(--color-text);
       font: 15px/1.55 var(--font-body); }
a { color: var(--color-accent); text-decoration: none; }
a:hover { color: var(--accent-hover); text-decoration: underline; }
.page { min-height: 100vh; padding: 22.4px 22.4px 67.2px; }
.wrap { max-width: 1120px; margin: 0 auto; display: flex; flex-direction: column; gap: 33.6px; }
.wrap.narrow { max-width: 760px; }
.live { display: flex; flex-direction: column; gap: 33.6px; }
.col { display: flex; flex-direction: column; gap: 11.2px; min-width: 0; }
.col.tight { gap: 2.8px; }
.row { display: flex; align-items: center; gap: 16.8px; flex-wrap: wrap; }
.mono { font-family: var(--mono); }
.dim { color: var(--dim); }
.kicker { font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--dim); }
.hint { margin: 0; font-size: 13px; color: var(--dim); text-wrap: pretty; }

header.top { display: flex; align-items: center; justify-content: space-between; gap: 16.8px;
             flex-wrap: wrap; padding-bottom: 11.2px; border-bottom: 1px solid var(--color-divider); }
.brand { font-family: var(--font-heading); font-weight: 500; font-size: 18px; letter-spacing: -0.015em; }
nav.top { display: flex; gap: 16.8px; font-size: 13px; }
nav.top a { color: var(--dim); }
nav.top .here { color: var(--color-accent); }
.runid { font-family: var(--mono); font-size: 12px; color: var(--dim); }
.toggle { display: inline-flex; align-items: center; gap: 6px; background: transparent;
          color: var(--color-text); border: 1px solid var(--color-divider); border-radius: 8px;
          padding: 5.6px 11.2px; font: inherit; font-size: 12px; cursor: pointer; }
.toggle:hover { border-color: var(--color-accent); color: var(--color-accent); }

.pill { font-size: 12px; padding: 2.8px 11.2px; border-radius: 999px;
        border: 1px solid var(--color-divider); color: var(--dim); white-space: nowrap; }
.pill.on { border-color: var(--color-accent); color: var(--color-accent); }

.bar { display: flex; flex-direction: column; gap: 5.6px; }
.bar .rail { position: relative; height: 6px; border-radius: 999px; background: var(--track); }
.bar.lg .rail { height: 8px; }
.bar .fill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 999px;
             background: var(--lit-soft); }
.bar .now { position: absolute; top: -4px; bottom: -4px; width: 2px;
            background: var(--lit); border-radius: 2px; }
.bar.lg .now { top: -5px; bottom: -5px; }
.bar .mark { position: absolute; top: -7px; bottom: -7px; width: 1px;
             background: var(--color-text); opacity: .55; }
.bar.lg .mark { top: -9px; bottom: -9px; }
.bar .ends { display: flex; justify-content: space-between; gap: 11.2px;
             font-family: var(--mono); font-size: 11px; color: var(--dim); }
.bar .ends .lit { color: var(--color-text); }

.kv { display: grid; grid-template-columns: max-content 1fr; gap: 1px 16.8px; font-size: 12px;
      color: var(--dim); font-family: var(--mono); overflow-x: auto; }
.kv .v { color: var(--color-text); }

.shots { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px,1fr)); gap: 16.8px; }
figure { margin: 0; display: flex; flex-direction: column; gap: 5.6px; }
figure img { width: 100%; display: block; border-radius: 8px; box-shadow: var(--shadow-sm); }
figcaption { font-size: 11px; color: var(--dim); font-family: var(--mono); overflow-wrap: anywhere; }
.frame { position: relative; border-radius: 8px; overflow: hidden; box-shadow: var(--shadow-sm); }
.frame img { border-radius: 0; box-shadow: none; }
.box { position: absolute; border: 2px solid var(--lit); border-radius: 2px;
       box-shadow: 0 0 0 9999px var(--scrim); }
.box .tag { position: absolute; left: 0; top: -24px; white-space: nowrap;
            background: var(--color-bg); border: 1px solid var(--lit); border-radius: 4px;
            padding: 1px 6px; font-family: var(--mono); font-size: 11px; color: var(--color-text); }

.panel { background: var(--color-surface); border-radius: 14px; box-shadow: var(--shadow-md);
         padding: 22.4px; display: flex; flex-direction: column; gap: 16.8px; }
.acts { display: flex; gap: 8.4px; flex-wrap: wrap; }
.acts form { display: inline; }
.btn { background: transparent; border-radius: 8px; padding: 8.4px 22.4px; font: inherit;
       font-family: var(--font-heading); font-weight: 500; font-size: 14px; cursor: pointer;
       color: var(--dim); border: 1px solid var(--color-divider); }
.btn:hover { color: var(--color-text); border-color: var(--color-text); }
.btn.ok { color: var(--color-accent); border-color: var(--color-accent); }
.btn.ok:hover { background: color-mix(in srgb, var(--color-accent) 14%, transparent);
                color: var(--color-accent); border-color: var(--color-accent); }
.btn.sm { padding: 5.6px 14px; font-size: 13px; }

footer.bot { display: flex; gap: 16.8px; flex-wrap: wrap; font-family: var(--mono); font-size: 11px;
             color: var(--dim); padding-top: 11.2px; border-top: 1px solid var(--color-divider); }
:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
"""

_TRACE_STYLE = """
.hero { display: grid; grid-template-columns: minmax(0,1.35fr) minmax(0,1fr);
        gap: 33.6px; align-items: start; }
@media (max-width: 820px) { .hero { grid-template-columns: minmax(0,1fr); } }
.hero h2 { margin: 0; font-family: var(--font-heading); font-weight: 500; font-size: 32px;
           line-height: 1.12; letter-spacing: -0.015em; text-wrap: pretty; }
.lede { margin: 0; max-width: 52ch; color: var(--dim); font-size: 14px; text-wrap: pretty; }
.lede .mono { color: var(--color-text); }
.pills { display: flex; gap: 8.4px; flex-wrap: wrap; margin-top: 5.6px; }

.big { display: flex; align-items: flex-end; gap: 11.2px; flex-wrap: wrap; }
.big .n { font-family: var(--mono); font-size: 58px; line-height: 1;
          letter-spacing: -0.02em; color: var(--lit); }
.big .u { font-family: var(--mono); font-size: 14px; color: var(--dim); padding-bottom: 8px; }

.flow { display: flex; align-items: stretch; gap: 8.4px; flex-wrap: wrap; }
.step { flex: 1 1 150px; min-width: 0; background: var(--color-surface); border-radius: 8px;
        box-shadow: var(--shadow-sm); border-left: 2px solid var(--lit);
        padding: 11.2px 16.8px; display: flex; flex-direction: column; gap: 2.8px; }
.step.err { border-left-color: var(--bad); }
.step .name { font-size: 13px; font-family: var(--font-heading); font-weight: 500;
              overflow-wrap: anywhere; }
.step .br { font-family: var(--mono); font-size: 12px; color: var(--lit); overflow-wrap: anywhere; }
.step.err .br { color: var(--bad); }
.step .ms { font-family: var(--mono); font-size: 11px; color: var(--dim); }
.arrow { align-self: center; color: var(--dim); font-size: 16px; }
.pending { flex: 1 1 150px; min-width: 0; border: 1px dashed var(--color-divider); border-radius: 8px;
           padding: 11.2px 16.8px; display: flex; align-items: center; gap: 8.4px;
           font-family: var(--mono); font-size: 12px; color: var(--dim); }
.dot { width: 7px; height: 7px; border-radius: 50%; background: var(--lit);
       animation: pulse 1.1s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { opacity: .25 } 50% { opacity: 1 } }

.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px,1fr)); gap: 8.4px; }
.ghost { border: 1px dashed var(--color-divider); border-radius: 8px; padding: 8.4px 11.2px;
         display: flex; flex-direction: column; gap: 1px; font-family: var(--mono); }
.ghost .t { font-size: 12px; color: var(--dim); }
.ghost .r { font-size: 11px; color: var(--dim); opacity: .75; overflow-wrap: anywhere; }

.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px,1fr)); gap: 16.8px; }
.card { background: var(--color-surface); border-radius: 8px; box-shadow: var(--shadow-sm);
        padding: 16.8px; display: flex; flex-direction: column; gap: 11.2px; }
.card .head { display: flex; justify-content: space-between; align-items: baseline; gap: 11.2px; }
.card .head .name { font-family: var(--font-heading); font-weight: 500; font-size: 16px;
                    overflow-wrap: anywhere; }
.card .head .ms { font-family: var(--mono); font-size: 11px; color: var(--dim); white-space: nowrap; }
.verdict, .err { font-family: var(--mono); font-size: 12px;
                 border-top: 1px solid var(--color-divider); padding-top: 8.4px;
                 overflow-wrap: anywhere; }
.verdict { color: var(--lit); }
.err { color: var(--bad); }

.cta { background: var(--color-surface); border-radius: 14px; box-shadow: var(--shadow-md);
       padding: 22.4px; display: flex; flex-wrap: wrap; align-items: center;
       justify-content: space-between; gap: 16.8px; }
.cta .t { font-family: var(--font-heading); font-weight: 500; font-size: 20px; }
.cta .s { font-size: 13px; color: var(--dim); text-wrap: pretty; }
"""

THEME_BOOTSTRAP = """
try {
  var stored = localStorage.getItem('afterimage-theme');
  document.documentElement.dataset.theme = stored === 'light' ? 'light' : 'dark';
} catch (e) { document.documentElement.dataset.theme = 'dark'; }
"""

COMMON_SCRIPT = """
const root = document.documentElement;
const label = document.getElementById('theme-label');
const paint = (theme) => {
  root.dataset.theme = theme;
  label.textContent = theme === 'dark' ? 'Light' : 'Dark';
};
paint(root.dataset.theme === 'light' ? 'light' : 'dark');
document.getElementById('theme').addEventListener('click', () => {
  const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
  paint(next);
  try { localStorage.setItem('afterimage-theme', next); } catch (e) {}
});
function placeBoxes() {
  document.querySelectorAll('.box[data-bbox]').forEach((box) => {
    const img = box.parentElement.querySelector('img');
    const place = () => {
      if (!img.naturalWidth || !img.naturalHeight) return;
      const [x, y, w, h] = JSON.parse(box.dataset.bbox);
      box.style.left = (x / img.naturalWidth * 100) + '%';
      box.style.top = (y / img.naturalHeight * 100) + '%';
      box.style.width = (w / img.naturalWidth * 100) + '%';
      box.style.height = (h / img.naturalHeight * 100) + '%';
      box.hidden = false;
    };
    img.complete ? place() : img.addEventListener('load', place);
  });
}
placeBoxes();
"""

_LIVE_SCRIPT = """
const page = document.querySelector('.page');
if (page.dataset.runState === 'unstarted' && page.dataset.executeUrl) {
  fetch(page.dataset.executeUrl, { method: 'POST' }).catch(() => {});
}
let attempts = 0;
const poll = async () => {
  if (document.hidden) { setTimeout(poll, 5000); return; }
  let next = 1500;
  try {
    const res = await fetch(location.pathname, { headers: { accept: 'text/html' } });
    const doc = new DOMParser().parseFromString(await res.text(), 'text/html');
    const fresh = doc.querySelector('.live');
    const current = document.querySelector('.live');
    if (fresh && current) {
      current.replaceWith(fresh);
      placeBoxes();
    }
    page.dataset.runState = doc.querySelector('.page').dataset.runState;
  } catch (e) { next = 3000; }
  if (page.dataset.runState !== 'done' && ++attempts < 400) setTimeout(poll, next);
};
setTimeout(poll, 1500);
"""


_QUESTION = {
    "assess_quality": "Is this capture worth scoring at all?",
    "align_to_baseline": "Is this the same asset as the one in memory?",
    "diff_against_memory": "Has anything changed since the baseline — enough to be sure?",
    "crop_and_rescan": "Is the changed region large enough to be real?",
    "classify_severity": "What kind of defect, and can it be written unattended?",
}

def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, (dict, list)):
        return html.escape(json.dumps(value))
    return html.escape(str(value))


def _scale(value: float, threshold: float) -> float:
    top = max(abs(value), abs(threshold))
    if top == 0.0:
        return 1.0
    return 1.0 if top <= 1.0 else top * 1.5


def _pct(value: float, scale: float) -> float:
    return max(0.0, min(100.0, value / scale * 100.0))


def threshold_bar(value: float, threshold: float, ends: str, large: bool = False) -> str:
    value, threshold = float(value), float(threshold)
    scale = _scale(value, threshold)
    at, mark = _pct(value, scale), _pct(threshold, scale)
    size = " lg" if large else ""
    return (
        f"<div class='bar{size}'><div class='rail'>"
        f"<div class='fill' style='width:{at:.2f}%'></div>"
        f"<div class='now' style='left:{at:.2f}%'></div>"
        f"<div class='mark' style='left:{mark:.2f}%'></div></div>"
        f"<div class='ends'>{ends}</div></div>"
    )


def _kv_rows(data: dict) -> str:
    rows = []
    for key, value in data.items():
        if isinstance(value, dict):
            rows.append(_kv_rows(value))
        else:
            rows.append(
                f"<span>{html.escape(str(key))}</span><span class='v'>{_fmt(value)}</span>"
            )
    return "".join(rows)


def _policy_of(event: dict) -> dict | None:
    if event["type"] == "tool_call":
        return event.get("policy")
    return event if event["type"] == "decision" else None


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


_NAV = (("/", "assets", "assets"), ("/queue", "approval queue", "queue"))


def _chrome(current: str, meta: str) -> str:
    links = [
        f"<span class='here'>{label}</span>" if key == current else f"<a href='{href}'>{label}</a>"
        for href, label, key in _NAV
    ]
    if not any(key == current for _, _, key in _NAV):
        links.append(f"<span class='here'>{html.escape(current)}</span>")
    return (
        "<header class='top'>"
        "<div class='row'><span class='brand'>afterimage</span>"
        f"<nav class='top'>{''.join(links)}</nav></div>"
        f"<div class='row'><span class='runid'>{html.escape(meta)}</span>"
        "<button class='toggle' id='theme' type='button'>&#9680;"
        "<span id='theme-label'>Light</span></button></div>"
        "</header>"
    )


def shell(
    title: str,
    current: str,
    body: str,
    meta: str = "",
    style: str = "",
    script: str = "",
    page_attrs: str = "",
    narrow: bool = False,
) -> str:
    wrap = "wrap narrow" if narrow else "wrap"
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>afterimage &mdash; {html.escape(title)}</title>"
        f"<style>{BASE_STYLE}{style}</style>"
        f"<script>{THEME_BOOTSTRAP}</script></head><body>"
        f"<div class='page'{page_attrs}><div class='{wrap}'>"
        f"{_chrome(current, meta)}{body}</div></div>"
        f"<script>{COMMON_SCRIPT}{script}</script></body></html>"
    )


def _decider(decisions: list[dict]) -> str:
    if not decisions:
        return ""
    final = decisions[-1]
    scale = _scale(float(final["value"]), float(final["threshold"]))
    ends = (
        "<span>0</span>"
        f"<span class='lit'>threshold {_fmt(final['threshold'])}</span>"
        f"<span>{_fmt(scale)}</span>"
    )
    return (
        "<div class='panel'><div class='kicker'>the number that decided it</div>"
        f"<div class='big'><span class='n'>{_fmt(final['value'])}</span>"
        f"<span class='u'>{html.escape(final['input_metric'])}</span></div>"
        f"{threshold_bar(final['value'], final['threshold'], ends, large=True)}"
        f"<p class='hint'>{html.escape(causal_line(final))}</p></div>"
    )


def _pills(summary: dict, calls: list[dict]) -> str:
    pills = []
    if summary.get("branch"):
        pills.append(f"<span class='pill on'>{html.escape(str(summary['branch']))}</span>")
    if summary.get("status"):
        pills.append(f"<span class='pill'>{html.escape(str(summary['status']))}</span>")
    detector = next(
        (c["metrics"]["detector"] for c in calls if c.get("metrics", {}).get("detector")), None
    )
    if detector:
        pills.append(f"<span class='pill'>detector: {html.escape(str(detector))}</span>")
    return "".join(pills)


def _hero(summary: dict, events: list[dict], decisions: list[dict]) -> str:
    calls = [e for e in events if e["type"] == "tool_call"]
    seconds = sum(float(e.get("duration_ms", 0.0)) for e in calls) / 1000.0
    headline = summary.get("message") or summary.get("branch") or "Inspection trace"
    left = (
        "<div class='col'>"
        f"<div class='kicker'>{html.escape(str(summary.get('asset_id') or 'unknown asset'))}"
        f" &middot; inspected {html.escape(str(summary.get('captured_at') or ''))}</div>"
        f"<h2>{html.escape(str(headline))}</h2>"
        f"<p class='lede'>{len(calls)} tool calls, {len(decisions)} thresholds, "
        f"{seconds:.2f} s. Every branch below was decided in "
        "<span class='mono'>services/agent/policy.py</span> from the number beside it.</p>"
        f"<div class='pills'>{_pills(summary, calls)}</div></div>"
    )
    return f"<section class='hero'>{left}{_decider(decisions)}</section>"


def _step(event: dict) -> str:
    policy = event.get("policy")
    outcome = policy["branch"] if policy else event.get("error", "no verdict")
    failed = " err" if "error" in event else ""
    return (
        f"<div class='step{failed}'>"
        f"<span class='name'>{html.escape(event['tool'])}</span>"
        f"<span class='br'>{html.escape(str(outcome))}</span>"
        f"<span class='ms'>{_fmt(event.get('duration_ms', 0.0))} ms</span></div>"
    )


def _not_taken(events: list[dict]) -> str:
    cards = []
    for event in events:
        policy = _policy_of(event)
        if not policy:
            continue
        untaken = "&ge;" if policy["value"] < policy["threshold"] else "&lt;"
        cards.append(
            f"<div class='ghost'><span class='t'>{html.escape(event.get('tool', 'decision'))}</span>"
            f"<span class='r'>{html.escape(policy['input_metric'])} {_fmt(policy['value'])} "
            f"not {untaken} {_fmt(policy['threshold'])}</span></div>"
        )
    if not cards:
        return ""
    joined = "".join(cards)
    return (
        "<div class='col' style='padding-top:5.6px'>"
        "<div class='kicker'>branches not taken</div>"
        f"<div class='grid'>{joined}</div></div>"
    )


def _path(events: list[dict], run_state: str = trace.DONE) -> str:
    steps = [_step(e) for e in events if e["type"] == "tool_call"]
    if run_state != trace.DONE:
        steps.append("<div class='pending'><span class='dot'></span>working&hellip;</div>")
    if not steps:
        return ""
    flow = "<div class='arrow'>&rarr;</div>".join(steps)
    kicker = "the path this run took" if run_state == trace.DONE else "the path so far"
    return (
        f"<section class='col'><div class='kicker'>{kicker}</div>"
        f"<div class='flow'>{flow}</div>{_not_taken(events)}</section>"
    )


def _detail_card(event: dict) -> str:
    policy = event.get("policy")
    body = (
        f"<div class='head'><span class='name'>{html.escape(event['tool'])}</span>"
        f"<span class='ms'>{_fmt(event.get('duration_ms', 0.0))} ms</span></div>"
    )
    question = _QUESTION.get(event["tool"])
    if question:
        body += f"<p class='hint'>{html.escape(question)}</p>"
    if policy:
        word = "max" if policy["value"] < policy["threshold"] else "min"
        ends = (
            f"<span class='lit'>{html.escape(policy['input_metric'])} "
            f"{_fmt(policy['value'])}</span>"
            f"<span>{word} {_fmt(policy['threshold'])}</span>"
        )
        body += threshold_bar(policy["value"], policy["threshold"], ends)
    facts = {
        key: value
        for key, value in event.get("metrics", {}).items()
        if not str(key).endswith("_key") and not isinstance(value, list)
    }
    facts.update(policy.get("extra", {}) if policy else {})
    if facts:
        body += f"<div class='kv'>{_kv_rows(facts)}</div>"
    if "error" in event:
        body += f"<div class='err'>{html.escape(event['error'])}</div>"
    elif policy:
        body += f"<div class='verdict'>&rarr; {html.escape(policy['branch'])}</div>"
    return f"<div class='card'>{body}</div>"


def _details(events: list[dict]) -> str:
    cards = "".join(_detail_card(e) for e in events if e["type"] == "tool_call")
    return f"<section class='cards'>{cards}</section>" if cards else ""


def _image_refs(summary: dict, events: list[dict]) -> tuple[str, str]:
    baseline, capture = "", str(summary.get("capture_key") or "")
    for event in events:
        if event.get("tool") != "align_to_baseline":
            continue
        baseline = event.get("args", {}).get("baseline_key") or baseline
        capture = event.get("metrics", {}).get("aligned_key") or capture
    return baseline, capture


def region_tag(label: str | None, delta: float | None) -> str:
    parts = [html.escape(str(label))] if label else []
    if delta is not None:
        parts.append(f"&Delta;{_fmt(float(delta))}")
    return " &middot; ".join(parts)


def approval_forms(run_id: str) -> str:
    safe = html.escape(str(run_id))
    return (
        "<div class='acts'>"
        f"<form method='post' action='/queue/{safe}/approve'>"
        "<button class='btn ok'>Approve write</button></form>"
        f"<form method='post' action='/queue/{safe}/reject'>"
        "<button class='btn'>Reject</button></form></div>"
    )


def _region(events: list[dict]) -> tuple[list | None, str]:
    bbox, delta, label = None, None, ""
    for event in events:
        policy = event.get("policy") or {}
        if "bbox" in policy.get("extra", {}):
            bbox = policy["extra"]["bbox"]
            if policy["input_metric"] == "mean_delta":
                delta = policy["value"]
        if event.get("tool") == "classify_severity":
            label = event.get("metrics", {}).get("label") or label
    return bbox, region_tag(label, delta)


def comparison_figures(baseline_key: str, capture_key: str, bbox=None, tag: str = "") -> str:
    if not (baseline_key and capture_key):
        return ""
    overlay = ""
    if bbox:
        chip = f"<span class='tag'>{tag}</span>" if tag else ""
        marks = html.escape(json.dumps(list(bbox)))
        overlay = f"<div class='box' hidden data-bbox='{marks}'>{chip}</div>"
    return (
        "<div class='shots'>"
        f"<figure><img src='/images/{html.escape(baseline_key)}' alt='baseline in memory'>"
        f"<figcaption>baseline &middot; {html.escape(baseline_key)}</figcaption></figure>"
        f"<figure><div class='frame'>"
        f"<img src='/images/{html.escape(capture_key)}' alt='capture under inspection'>{overlay}</div>"
        f"<figcaption>capture &middot; {html.escape(capture_key)}</figcaption></figure>"
        "</div>"
    )


def _comparison(summary: dict, events: list[dict]) -> str:
    baseline, capture = _image_refs(summary, events)
    bbox, tag = _region(events)
    figures = comparison_figures(baseline, capture, bbox, tag)
    if not figures:
        return ""
    return f"<section class='col'><div class='kicker'>what it compared</div>{figures}</section>"


def _cta(summary: dict) -> str:
    if summary.get("status") != trace.AWAITING_APPROVAL:
        return ""
    run_id = str(summary.get("run_id") or "")
    message = html.escape(str(summary.get("message") or ""))
    return (
        "<section class='cta'><div class='col tight'>"
        "<span class='t'>Waiting on a human</span>"
        f"<span class='s'>{message} Nothing has been written to memory.</span></div>"
        f"{approval_forms(run_id)}</section>"
    )


def _footer(summary: dict) -> str:
    run_id = html.escape(str(summary.get("run_id") or ""))
    asset_id = html.escape(str(summary.get("asset_id") or ""))
    links = [f"<span>GET /traces/{run_id}</span>"]
    if run_id:
        links.append(f"<a href='/traces/{run_id}?format=json'>raw json</a>")
    if asset_id:
        links.append(f"<a href='/assets/{asset_id}'>asset history</a>")
    links.append("<span>thresholds from services/agent/policy.py</span>")
    return f"<footer class='bot'>{''.join(links)}</footer>"


def render_html(state: dict, events: list[dict]) -> str:
    summary = _summary(state, events)
    run_state = trace.run_state(events)
    run_id = str(summary.get("run_id") or "")
    live = "".join((
        _hero(summary, events, _decisions(events)),
        _path(events, run_state),
        _details(events),
        _comparison(summary, events),
        _cta(summary),
    ))
    page_attrs = f" data-run-state='{run_state}'"
    if run_id:
        page_attrs += f" data-execute-url='/runs/{html.escape(run_id)}/execute'"
    return shell(
        "inspection trace",
        "trace",
        f"<div class='live'>{live}</div>{_footer(summary)}",
        meta=f"run {run_id}" if run_id else "",
        style=_TRACE_STYLE,
        script="" if run_state == trace.DONE else _LIVE_SCRIPT,
        page_attrs=page_attrs,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Print the trace of a run.")
    parser.add_argument("run_id")
    parser.add_argument("--runs-dir", default="runs")
    args = parser.parse_args()
    print(render_text(trace.read_events(Path(args.runs_dir) / args.run_id)))


if __name__ == "__main__":
    main()
