import argparse
import html
import json
from pathlib import Path

from services.memory import runs
from services.observability import trace


def load_run(run_dir: Path) -> tuple[dict, list[dict]]:
    run_dir = Path(run_dir)
    state = runs.read(run_dir, "state.json") or {}
    return state, trace.read_events(run_dir)


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


_STYLE = """
:root { color-scheme: dark; }
* { margin: 0; box-sizing: border-box; }
body { background: #0d1117; color: #c9d1d9; font: 15px/1.5 system-ui, sans-serif;
       max-width: 760px; margin: 0 auto; padding: 2.5rem 1rem 4rem; }
code, .num { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
header { margin-bottom: 2rem; }
header h1 { font-size: 1.1rem; font-weight: 600; color: #e6edf3; }
header .meta { margin-top: .5rem; display: flex; flex-wrap: wrap; gap: .4rem; }
.badge { font-size: .78rem; padding: .15rem .55rem; border-radius: 999px;
         border: 1px solid #30363d; background: #161b22; }
.badge.status { border-color: #1f6feb; color: #79c0ff; }
.event { border: 1px solid #30363d; border-radius: 8px; background: #161b22;
         padding: .8rem 1rem; margin-bottom: .75rem; }
.event .head { display: flex; justify-content: space-between; gap: 1rem; }
.event .head .name { font-weight: 600; color: #e6edf3; }
.event .head .when { font-size: .78rem; color: #8b949e; white-space: nowrap; }
.kv { margin-top: .5rem; font-size: .82rem; color: #8b949e;
      display: grid; grid-template-columns: max-content 1fr; gap: .1rem .8rem;
      overflow-x: auto; }
.kv .num { color: #c9d1d9; }
.verdict { margin-top: .6rem; padding: .45rem .7rem; border-radius: 6px;
           background: #1c2a1c; border: 1px solid #2ea04366; color: #7ee787;
           font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
           font-size: .85rem; font-weight: 600; }
.error { margin-top: .6rem; padding: .45rem .7rem; border-radius: 6px;
         background: #2a1c1c; border: 1px solid #f8514966; color: #ffa198;
         font-size: .85rem; }
"""


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, (dict, list)):
        return html.escape(json.dumps(value))
    return html.escape(str(value))


def _kv_rows(data: dict) -> str:
    return "".join(
        f"<span>{html.escape(str(k))}</span><span class='num'>{_fmt(v)}</span>"
        for k, v in data.items()
    )


def _verdict_html(decision: dict) -> str:
    return f"<div class='verdict'>{html.escape(causal_line(decision))}</div>"


def _event_html(event: dict) -> str:
    kind = event["type"]
    when = html.escape(event["ts"])
    if kind == "run_started":
        name, when_extra, body = "run started", "", f"<div class='kv'>{_kv_rows({k: event[k] for k in ('run_id', 'asset_id', 'capture_key')})}</div>"
    elif kind == "tool_call":
        name = html.escape(event["tool"])
        when_extra = f"{event['duration_ms']} ms &middot; "
        body = f"<div class='kv'>{_kv_rows(event.get('args', {}))}</div>"
        if "metrics" in event:
            body += f"<div class='kv'>{_kv_rows(event['metrics'])}</div>"
        if "error" in event:
            body += f"<div class='error'>{html.escape(event['error'])}</div>"
        if "policy" in event:
            body += _verdict_html(event["policy"])
    elif kind == "decision":
        name, when_extra, body = "decision", "", _verdict_html(event)
    elif kind == "approval_requested":
        name, when_extra = "human approval requested", ""
        body = f"<div class='error'>{html.escape(event['message'])}</div>"
    elif kind == "run_finished":
        name, when_extra = "run finished", ""
        detail = {"status": event["status"], "branch": event["branch"]}
        if event.get("message"):
            detail["message"] = event["message"]
        body = f"<div class='kv'>{_kv_rows(detail)}</div>"
    else:
        name, when_extra, body = html.escape(kind), "", f"<div class='kv'>{_kv_rows(event)}</div>"
    return (
        f"<div class='event'><div class='head'><span class='name'>{name}</span>"
        f"<span class='when'>{when_extra}{when}</span></div>{body}</div>"
    )


def render_html(state: dict, events: list[dict]) -> str:
    badges = "".join(
        f"<span class='badge{' status' if k in ('status', 'branch') else ''}'>"
        f"{html.escape(str(k))}: {html.escape(str(v))}</span>"
        for k, v in state.items()
        if v is not None
    )
    cards = "".join(_event_html(e) for e in events)
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>afterimage trace</title><style>{_STYLE}</style></head><body>"
        f"<header><h1>afterimage &mdash; inspection trace</h1>"
        f"<div class='meta'>{badges}</div></header>{cards}</body></html>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Print the trace of a run.")
    parser.add_argument("run_id")
    parser.add_argument("--runs-dir", default="runs")
    args = parser.parse_args()
    print(render_text(trace.read_events(Path(args.runs_dir) / args.run_id)))


if __name__ == "__main__":
    main()
