import json

import pytest

from services.memory import store
from services.observability.tests.sample_run import EVENTS, STATE
from services.ui import views

CSS = (views.STATIC / "app.css").read_text()

HOSTILE = "<script>alert(1)</script>"
ESCAPED = "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_render_html_contains_the_causal_values():
    page = views.render_html(STATE, EVENTS)
    for fragment in ("inlier_ratio", "0.259", "0.5", "unrecognized_asset"):
        assert fragment in page
    assert "align_to_baseline" in page
    assert page.startswith("<!doctype html>")


def _hostile_pages() -> dict[str, str]:
    return {
        "index": views.index_page([{"asset_id": HOSTILE}]),
        "asset": views.asset_page(HOSTILE, [{
            "sk": f"{store.INSPECTION}7f2ac91b04de", "inspection_id": HOSTILE,
            "captured_at": HOSTILE,
            "image_keys": {"capture": HOSTILE},
            "metrics": {"severity": {"label": HOSTILE, "score": 0.6543}},
        }]),
        "queue": views.queue_page([{
            "run_id": HOSTILE, "asset_id": HOSTILE, "message": HOSTILE,
            "image_keys": {"baseline": HOSTILE, "capture": HOSTILE},
            "metrics": {"diff": {"regions": [{"bbox": [1, 2, 3, 4], "mean_delta": 41.88}]},
                        "severity": {"label": HOSTILE, "score": 0.6543}},
        }]),
        "trace": views.render_html({}, [{
            "type": "run_finished", "ts": "2026-08-26T12:00:00.000+00:00",
            "status": "failed", "branch": None, "message": HOSTILE,
        }]),
    }


@pytest.mark.parametrize("name", ["index", "asset", "queue", "trace"])
def test_every_view_escapes_untrusted_strings(name):
    page = _hostile_pages()[name]
    assert HOSTILE not in page
    assert ESCAPED in page


def test_both_themes_ship_in_the_stylesheet():
    dark, light = CSS.split(":root[data-theme='light']")
    assert ":root {" in dark
    assert "color-scheme: dark;" in dark and "color-scheme: light;" in light
    for token in ("--ok:", "--warn:", "--bad:"):
        assert token in dark and token in light
    page = views.index_page([])
    assert "localStorage.getItem('afterimage-theme')" in page.split("</head>")[0]


def test_the_first_visit_opens_in_the_light_theme():
    assert "<html lang='en' data-theme='light'>" in views.index_page([])
    assert "paint(root.dataset.theme);" in (views.STATIC / "app.js").read_text()


def test_static_assets_are_content_addressed():
    names = list(views._assets())
    assert any(name.startswith("app.") and name.endswith(".css") for name in names)
    assert any(name.startswith("app.") and name.endswith(".js") for name in names)
    for name in names:
        assert f"/static/{name}" in views.index_page([])
        assert views.static_asset(name)[0]
    assert views.static_asset("app.css") is None


def test_the_swapped_container_keeps_its_selector_once_the_run_is_done():
    assert "data-poll='5000'" in views.queue_page([])
    assert "data-poll" not in views.index_page([])
    running = views.render_html({}, EVENTS[:2])
    assert "data-poll='1500'" in running
    assert "data-run-state='running'" in running
    done = views.render_html(STATE, EVENTS)
    assert "data-poll='1500'" in done
    assert "data-run-state='done'" in done


APPROVAL = {
    "type": "decision", "ts": "2026-08-26T12:05:00.000+00:00",
    "input_metric": "human_approved", "value": 1.0, "threshold": 1.0, "branch": "approved",
}


def test_the_human_gate_does_not_steal_the_deciding_number():
    page = views.render_html(STATE, EVENTS + [APPROVAL])
    assert "human_approved" not in page
    assert "inlier_ratio 0.259 &lt; 0.5 -&gt; unrecognized_asset" in page


def _timeline(item: dict) -> str:
    return views.asset_page("array-rooftop", [{
        "sk": f"{store.INSPECTION}7f2ac91b04de",
        "captured_at": "2026-08-26T12:04:11+00:00",
        "metrics": {"severity": {"label": "crack", "score": 0.6543}},
        **item,
    }])


def test_a_persisted_verdict_is_what_the_timeline_scores_against():
    page = _timeline({"inspection_id": "7f2ac91b04de", "verdict": {
        "input_metric": "score", "value": 0.6543, "threshold": 0.25,
        "branch": "human_approval"}})
    assert "threshold 0.25" in page
    assert "score 0.6543 &gt;= 0.25 -&gt; human_approval" in page
    assert "class='mark'" in page


def test_an_inspection_without_a_verdict_recovers_it_from_its_own_trace(tmp_path, monkeypatch):
    monkeypatch.setenv("AFTERIMAGE_RUNS_DIR", str(tmp_path))
    run_id = "7f2ac91b04de"
    (tmp_path / run_id).mkdir()
    (tmp_path / run_id / "events.json").write_text(json.dumps([
        {"type": "tool_call", "ts": "2026-08-26T12:04:13+00:00", "tool": "classify_severity",
         "duration_ms": 4.0, "metrics": {"label": "crack", "score": 0.6543},
         "policy": {"input_metric": "score", "value": 0.6543, "threshold": 0.31,
                    "branch": "human_approval"}},
    ]))
    page = _timeline({"inspection_id": run_id})
    assert "threshold 0.31" in page
    assert "score 0.6543 &gt;= 0.31 -&gt; human_approval" in page


def test_an_inspection_with_neither_shows_the_score_without_a_threshold(tmp_path, monkeypatch):
    monkeypatch.setenv("AFTERIMAGE_RUNS_DIR", str(tmp_path))
    page = _timeline({"inspection_id": "ffffffffffff"})
    assert "score 0.6543" in page
    assert "-&gt;" not in page
    assert "class='mark'" not in page


def test_the_nav_stays_clickable_on_the_page_it_points_at():
    page = views.asset_page("array-rooftop", [])
    assert "<a href='/' class='here' aria-current='page'>assets</a>" in page
    assert "<a href='/queue'>approval queue</a>" in page
    trace_page = views.render_html(STATE, EVENTS)
    assert "<span class='here'>trace</span>" in trace_page


def test_the_asset_row_is_clickable_past_the_link_text():
    page = views.index_page([{"asset_id": "panel-a7-north"}])
    assert "<td><a href='/assets/panel-a7-north'>" in page
    assert ".table td > a::after" in CSS


def test_the_bar_takes_its_tone_from_the_branch():
    approval = {"input_metric": "score", "value": 0.65, "threshold": 0.4,
                "branch": "human_approval"}
    assert views._decided_bar(approval)["tone"] == "warn"
    assert views._decided_bar({**approval, "branch": "auto_write"})["tone"] == "ok"
    assert views._decided_bar({**approval, "branch": "unrecognized_asset"})["tone"] == "bad"
    for tone in ("ok", "warn", "bad"):
        assert f".bar.{tone} {{" in CSS


def test_the_timeline_explains_the_stages_instead_of_dumping_json():
    page = _timeline({"inspection_id": "7f2ac91b04de", "metrics": {
        "quality": {"blur_variance": 173.1789},
        "diff": {"regions": [{"mean_delta": 41.88}]},
        "severity": {"label": "crack", "score": 0.6543},
    }})
    assert "Is this capture worth scoring at all?" in page
    assert "173.179" in page
    assert "41.88" in page
    assert "blur_variance" not in page.split("<details>")[0]
    assert '"blur_variance": 173.1789' not in page
    assert "<details>" in page


def test_the_vocabulary_carries_its_own_definition():
    page = _timeline({"inspection_id": "7f2ac91b04de", "verdict": {
        "input_metric": "score", "value": 0.6543, "threshold": 0.25,
        "branch": "human_approval"}, "metrics": {
        "severity": {"label": "crack", "score": 0.6543},
        "alignment": {"inlier_ratio": 0.9988}}})
    assert "data-tip='human_approval: Severe enough" in page
    assert "class='tip' tabindex='0' data-tip='Share of matched keypoints" in page
    assert "data-tip" not in page.split("class='ends'")[0]


def test_the_warped_capture_says_so_in_the_caption_and_the_alt():
    queued = views.queue_page([{
        "run_id": "7f2ac91b04de", "asset_id": "panel-a7-north", "message": "",
        "image_keys": {"baseline": "a/b.png", "aligned": "a/al.png", "capture": "a/c.png"},
        "metrics": {},
    }])
    assert "warped onto the baseline" in queued
    raw = views.queue_page([{
        "run_id": "7f2ac91b04de", "asset_id": "panel-a7-north", "message": "",
        "image_keys": {"baseline": "a/b.png", "capture": "a/c.png"},
        "metrics": {},
    }])
    assert "warped onto the baseline" not in raw


def test_the_empty_queue_says_how_much_memory_holds():
    assert "5 assets in memory" in views.queue_page([], assets_in_memory=5)
    assert "1 asset in memory" in views.queue_page([], assets_in_memory=1)
    assert "in memory" not in views.queue_page([], assets_in_memory=0)
    assert "in memory" not in views.queue_page([])


def test_the_upload_form_states_what_it_accepts():
    page = views.index_page([])
    assert "image/jpeg,image/png,image/webp,image/tiff,image/bmp" in page
    assert "image/*" not in page
    assert "up to 6&nbsp;MB" in page
    assert "title='Lowercase letters" in page


def test_a_rejected_upload_renders_inside_the_page():
    page = views.index_page([], error="not a decodable image")
    assert "role='alert'" in page
    assert "not a decodable image" in page
    assert "Pick the file again" in page
    assert "role='alert'" not in views.index_page([])
