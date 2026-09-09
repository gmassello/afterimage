import html
import json

from services.agent.policy import Policy
from services.memory import store
from services.observability import render

_PAGES_STYLE = """
.table { width: 100%; border-collapse: collapse; font-size: 14px; }
.table th { text-align: left; font-weight: 400; font-size: 11px; letter-spacing: 0.14em;
            text-transform: uppercase; color: var(--dim); padding: 5.6px 11.2px;
            border-bottom: 1px solid var(--color-divider); }
.table td { padding: 11.2px; border-bottom: 1px solid var(--color-divider); vertical-align: top; }
.table tbody tr:hover { background: color-mix(in srgb, var(--color-text) 4%, transparent); }
.thumb { max-height: 60px; width: auto; border-radius: 4px; box-shadow: var(--shadow-sm); }
.field { display: flex; gap: 8.4px; flex-wrap: wrap; align-items: center; }
.input { min-height: 36px; padding: 6px 10px; font: inherit; font-size: 14px;
         color: var(--color-text); caret-color: var(--color-accent); background: var(--color-bg);
         border: 1px solid var(--color-divider); border-radius: 8px; }
.input:hover { border-color: color-mix(in srgb, var(--color-text) 45%, transparent); }
.input::file-selector-button { margin-right: 8.4px; padding: 4px 11.2px; font: inherit;
                               font-size: 13px; color: var(--dim); background: transparent;
                               border: 1px solid var(--color-divider); border-radius: 6px;
                               cursor: pointer; }
.input::file-selector-button:hover { color: var(--color-accent); border-color: var(--color-accent); }
details > summary { cursor: pointer; font-family: var(--mono); font-size: 11px; color: var(--dim);
                    letter-spacing: 0.06em; }
details > summary:hover { color: var(--color-accent); }
details pre { margin: 8.4px 0 0; padding: 11.2px; border-radius: 8px; background: var(--color-bg);
              box-shadow: var(--shadow-sm); font-family: var(--mono); font-size: 11px;
              color: var(--color-text); overflow-x: auto; }

.timeline { display: flex; flex-direction: column; }
.tl { display: grid; grid-template-columns: 18px minmax(0, 1fr); gap: 16.8px; }
.tl .rail { position: relative; display: flex; justify-content: center; }
.tl .rail::before { content: ''; position: absolute; top: 0; bottom: 0; width: 1px;
                    background: color-mix(in srgb, var(--color-text) 30%, transparent); }
.tl:first-child .rail::before { top: 16px; }
.tl:last-child .rail::before { bottom: calc(100% - 16px); }
.tl .node { position: relative; margin-top: 12px; width: 9px; height: 9px; border-radius: 50%;
            background: var(--track); box-shadow: 0 0 0 3px var(--color-bg); }
.tl.promoted .node { background: var(--color-accent); }
.tl .entry { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 16.8px;
             align-items: start; padding: 5.6px 0 22.4px; min-width: 0; }
@media (max-width: 620px) { .tl .entry { grid-template-columns: minmax(0, 1fr); } }
.tl .facts { display: flex; flex-direction: column; gap: 8.4px; min-width: 0; }

.queue { display: flex; flex-direction: column; gap: 16.8px; }
.tl .top, .queue .top { display: flex; align-items: center; gap: 11.2px; flex-wrap: wrap;
                        font-family: var(--mono); font-size: 12px; color: var(--dim); }
.queue .foot { display: flex; align-items: center; justify-content: space-between; gap: 16.8px;
               flex-wrap: wrap; }
"""

_REFRESH = """
let live = true;
const halt = () => { live = false; };
addEventListener("submit", halt, true);
addEventListener("click", (e) => e.target.closest?.("a") && halt(), true);
setInterval(() => {
  if (live && ![...document.querySelectorAll("details")].some(d => d.open)) location.reload();
}, 5000);
"""


def _page(title: str, current: str, body: str, refresh: bool = False, narrow: bool = False) -> str:
    return render.shell(
        title,
        current,
        body,
        style=_PAGES_STYLE,
        script=_REFRESH if refresh else "",
        narrow=narrow,
    )


def _thumb(key: str) -> str:
    return f"<img class='thumb' src='/images/{html.escape(key)}' alt=''>" if key else ""


def _metrics_details(metrics: dict) -> str:
    if not metrics:
        return ""
    return (
        "<details><summary>metrics</summary>"
        f"<pre>{html.escape(json.dumps(metrics, indent=2))}</pre></details>"
    )


def _trace_link(run_id: str) -> str:
    safe = html.escape(run_id)
    return f"<a href='/traces/{safe}'>{safe}</a>" if run_id else ""


def index_page(assets: list[dict]) -> str:
    rows = "".join(
        f"<tr><td><a href='/assets/{html.escape(a['asset_id'])}'>"
        f"{html.escape(a['asset_id'])}</a></td></tr>"
        for a in assets
    ) or "<tr><td class='dim'>no assets yet</td></tr>"
    body = (
        "<section class='col'><div class='kicker'>assets in memory</div>"
        "<table class='table'><thead><tr><th>asset</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></section>"
        "<section class='panel'><div class='kicker'>new inspection</div>"
        "<form class='field' method='post' action='/inspections' enctype='multipart/form-data'>"
        "<input class='input' name='asset_id' placeholder='asset-id' required "
        "pattern='[a-z0-9-]{1,64}'>"
        "<input class='input' type='file' name='image' accept='image/*' required>"
        "<button class='btn ok sm'>inspect</button></form>"
        "<p class='hint'>The trace opens immediately and fills in as the agent works.</p>"
        "</section>"
    )
    return _page("assets", "assets", body, narrow=True)


def _severity_bar(metrics: dict, threshold: float) -> str:
    severity = metrics.get("severity") or {}
    score = severity.get("score")
    if score is None:
        return ""
    ends = (
        f"<span class='lit'>score {float(score):g}</span>"
        f"<span>approve {threshold:g}</span>"
    )
    return render.threshold_bar(score, threshold, ends)


def _baseline_entry(item: dict) -> tuple[str, str, str]:
    superseded = item.get("superseded_by")
    note = f"superseded by {_trace_link(superseded)}" if superseded else "current baseline"
    return (
        "<span class='pill on'>baseline</span>",
        f"<span class='hint'>{note}</span>",
        item.get("image_key", ""),
    )


def _inspection_entry(item: dict, threshold: float) -> tuple[str, str, str]:
    metrics = item.get("metrics") or {}
    label = (metrics.get("severity") or {}).get("label")
    kind = "<span class='pill'>inspection</span>"
    if label:
        kind += f"<span class='pill'>{html.escape(str(label))}</span>"
    detail = _severity_bar(metrics, threshold) + _metrics_details(metrics)
    return kind, detail, (item.get("image_keys") or {}).get("capture", "")


def _timeline_entry(item: dict, threshold: float) -> str:
    promoted = item["sk"].startswith(store.BASELINE)
    if promoted:
        kind, detail, image_key = _baseline_entry(item)
    else:
        kind, detail, image_key = _inspection_entry(item, threshold)
    row = "tl promoted" if promoted else "tl"
    return (
        f"<div class='{row}'><div class='rail'><span class='node'></span></div>"
        "<div class='entry'><div class='facts'>"
        f"<div class='top'>{html.escape(item.get('captured_at', ''))}{kind}"
        f"{_trace_link(item.get('inspection_id', ''))}</div>"
        f"{detail}</div>{_thumb(image_key)}</div></div>"
    )


def asset_page(asset_id: str, items: list[dict]) -> str:
    threshold = Policy.from_env().severity_score_approve
    entries = sorted(
        (item for item in items if item["sk"] != store.META),
        key=lambda item: item.get("captured_at", ""),
        reverse=True,
    )
    timeline = "".join(_timeline_entry(item, threshold) for item in entries) or (
        "<p class='hint'>no history yet</p>"
    )
    body = (
        f"<section class='col'><div class='kicker'>{html.escape(asset_id)} &middot; "
        "everything memory holds about this asset</div>"
        f"<div class='timeline'>{timeline}</div></section>"
    )
    return _page(asset_id, "assets", body)


def _queue_entry(item: dict, threshold: float) -> str:
    metrics = item.get("metrics") or {}
    diff, severity = metrics.get("diff") or {}, metrics.get("severity") or {}
    region = (diff.get("regions") or [{}])[0]
    image_keys = item.get("image_keys") or {}
    figures = render.comparison_figures(
        image_keys.get("baseline", ""),
        image_keys.get("aligned") or image_keys.get("capture", ""),
        region.get("bbox"),
        render.region_tag(severity.get("label"), region.get("mean_delta")),
    )
    return (
        "<section class='panel'>"
        f"<div class='top'>{_trace_link(item['run_id'])}"
        f"<span class='pill'>{html.escape(item.get('asset_id', ''))}</span></div>"
        f"{figures}"
        f"{_severity_bar(metrics, threshold)}"
        f"<p class='hint'>{html.escape(item.get('message', ''))}</p>"
        f"<div class='foot'>{_metrics_details(metrics)}"
        f"{render.approval_forms(item['run_id'])}</div>"
        "</section>"
    )


def queue_page(items: list[dict]) -> str:
    threshold = Policy.from_env().severity_score_approve
    entries = "".join(
        _queue_entry(item, threshold) for item in items
    ) or "<p class='hint'>nothing awaiting approval</p>"
    body = (
        "<section class='col'><div class='kicker'>runs the policy would not write unattended"
        f" &middot; approval threshold {threshold:g}</div>"
        f"<div class='queue'>{entries}</div></section>"
    )
    return _page("approval queue", "queue", body, refresh=True)
