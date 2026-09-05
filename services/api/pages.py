import html
import json

from services.memory import store
from services.observability import render

_STYLE = render._STYLE + """
h1 { font-size: 1.1rem; font-weight: 600; color: #e6edf3; }
nav { margin: .5rem 0 2rem; display: flex; gap: 1rem; font-size: .85rem; }
a { color: #79c0ff; text-decoration: none; }
table { width: 100%; border-collapse: collapse; margin-bottom: 2rem; }
th, td { text-align: left; padding: .45rem .6rem; border-bottom: 1px solid #30363d; font-size: .88rem; }
form.inline { display: inline; }
button { background: #21262d; color: #c9d1d9; border: 1px solid #30363d; border-radius: 6px;
         padding: .3rem .8rem; cursor: pointer; }
button.approve { border-color: #2ea04366; color: #7ee787; }
button.reject { border-color: #f8514966; color: #ffa198; }
input { background: #0d1117; color: #c9d1d9; border: 1px solid #30363d; border-radius: 6px; padding: .3rem .5rem; }
img.thumb { max-height: 60px; border-radius: 4px; }
.muted { color: #8b949e; font-size: .82rem; }
details pre { overflow-x: auto; font-size: .78rem; color: #8b949e; padding: .4rem 0; }
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


def _page(title: str, body: str, refresh: bool = False) -> str:
    script = f"<script>{_REFRESH}</script>" if refresh else ""
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>afterimage &mdash; {html.escape(title)}</title><style>{_STYLE}</style></head><body>"
        f"<h1>afterimage &mdash; {html.escape(title)}</h1>"
        "<nav><a href='/'>assets</a><a href='/queue'>approval queue</a></nav>"
        f"{body}{script}</body></html>"
    )


def _thumb(key: str) -> str:
    return f"<img class='thumb' src='/images/{html.escape(key)}' alt=''>" if key else ""


def _metrics_details(metrics: dict) -> str:
    return (
        "<details><summary class='muted'>metrics</summary>"
        f"<pre>{html.escape(json.dumps(metrics, indent=2))}</pre></details>"
    )


def index_page(assets: list[dict]) -> str:
    rows = "".join(
        f"<tr><td><a href='/assets/{html.escape(a['asset_id'])}'>{html.escape(a['asset_id'])}</a></td></tr>"
        for a in assets
    ) or "<tr><td class='muted'>no assets yet</td></tr>"
    form = (
        "<h1>new inspection</h1>"
        "<form method='post' action='/inspections' enctype='multipart/form-data' style='margin-top:1rem'>"
        "<input name='asset_id' placeholder='asset-id' required pattern='[a-z0-9-]{1,64}'> "
        "<input type='file' name='image' accept='image/*' required> "
        "<button>inspect</button>"
        "<p class='muted'>the agent runs live on upload; expect up to a minute before the trace appears</p>"
        "</form>"
    )
    return _page("assets", f"<table><tr><th>asset</th></tr>{rows}</table>{form}")


def _history_row(item: dict) -> str:
    sk = item["sk"]
    if sk == store.META:
        return ""
    kind = "baseline" if sk.startswith(store.BASELINE) else "inspection"
    inspection_id = html.escape(item.get("inspection_id", ""))
    captured_at = html.escape(item.get("captured_at", ""))
    trace_link = f"<a href='/traces/{inspection_id}'>{inspection_id}</a>"
    if kind == "baseline":
        image_key = item.get("image_key", "")
        superseded = item.get("superseded_by")
        extra = f"<span class='muted'>superseded by {html.escape(superseded)}</span>" if superseded else "current"
    else:
        image_key = item.get("image_keys", {}).get("capture", "")
        extra = _metrics_details(item.get("metrics", {}))
    return (
        f"<tr><td>{captured_at}</td><td>{kind}</td><td>{trace_link}</td>"
        f"<td>{_thumb(image_key)}</td><td>{extra}</td></tr>"
    )


def asset_page(asset_id: str, items: list[dict]) -> str:
    rows = "".join(_history_row(item) for item in items) or (
        "<tr><td colspan='5' class='muted'>no history yet</td></tr>"
    )
    body = (
        "<table><tr><th>captured</th><th>kind</th><th>trace</th><th>image</th><th></th></tr>"
        f"{rows}</table>"
    )
    return _page(asset_id, body)


def _queue_row(item: dict) -> str:
    run_id = html.escape(item["run_id"])
    capture_key = item.get("image_keys", {}).get("capture", "")
    return (
        f"<tr><td><a href='/traces/{run_id}'>{run_id}</a></td>"
        f"<td>{html.escape(item.get('asset_id', ''))}</td>"
        f"<td>{_thumb(capture_key)}</td>"
        f"<td>{html.escape(item.get('message', ''))}{_metrics_details(item.get('metrics', {}))}</td>"
        f"<td><form class='inline' method='post' action='/queue/{run_id}/approve'>"
        "<button class='approve'>approve</button></form> "
        f"<form class='inline' method='post' action='/queue/{run_id}/reject'>"
        "<button class='reject'>reject</button></form></td></tr>"
    )


def queue_page(items: list[dict]) -> str:
    rows = "".join(_queue_row(item) for item in items) or (
        "<tr><td colspan='5' class='muted'>nothing awaiting approval</td></tr>"
    )
    body = (
        "<table><tr><th>run</th><th>asset</th><th>capture</th><th>reason</th><th></th></tr>"
        f"{rows}</table>"
    )
    return _page("approval queue", body, refresh=True)
