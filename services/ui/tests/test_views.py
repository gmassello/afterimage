import json
import re

import pytest

from services.memory import runs, store
from services.observability import trace
from services.observability.tests.sample_run import EVENTS, STATE
from services.ui import views
from services.ui.text import strings

CSS = (views.STATIC / "app.css").read_text()
JS = (views.STATIC / "app.js").read_text()

EN = strings("en")

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
        "landing": views.landing_page(),
        "index": views.index_page([{"asset_id": HOSTILE}]),
        "activity": views.activity_page([{
            "run_id": "abcdef123456", "asset_id": HOSTILE, "captured_at": HOSTILE,
            "status": HOSTILE, "branch": HOSTILE, "retryable": False,
        }]),
        "error": views.error_page(500, HOSTILE, HOSTILE),
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


@pytest.mark.parametrize("name", ["index", "asset", "queue", "trace", "activity", "error"])
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


def test_the_first_visit_follows_the_system_theme():
    head = views.index_page([]).split("</head>")[0]
    assert "<html lang='en' data-theme='light'>" in head
    assert "matchMedia('(prefers-color-scheme: dark)')" in head
    assert head.index("localStorage.getItem") < head.index("matchMedia")
    assert "paint(root.dataset.theme);" in JS


def test_trace_cards_shrink_to_the_mobile_container():
    assert "@media (max-width: 620px) { .cards { grid-template-columns: minmax(0, 1fr); } }" in CSS


def test_static_assets_are_content_addressed():
    names = list(views._assets())
    assert any(name.startswith("app.") and name.endswith(".css") for name in names)
    assert any(name.startswith("app.") and name.endswith(".js") for name in names)
    pages = views.index_page([]) + views.landing_page()
    for name in names:
        assert f"/static/{name}" in pages
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


def _timeline(item: dict, register: str = "plain") -> str:
    return views.asset_page("array-rooftop", [{
        "sk": f"{store.INSPECTION}7f2ac91b04de",
        "captured_at": "2026-08-26T12:04:11+00:00",
        "metrics": {"severity": {"label": "crack", "score": 0.6543}},
        **item,
    }], register=register)


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
    assert "<a href='/app' class='here' aria-current='page'>assets</a>" in page
    assert "<a href='/queue'>approval queue</a>" in page
    trace_page = views.render_html(STATE, EVENTS)
    assert "<span class='here'>trace</span>" in trace_page


def test_the_asset_card_is_one_link_to_its_history():
    page = views.index_page([{"asset_id": "panel-a7-north"}])
    assert "<a class='asset' href='/assets/panel-a7-north'" in page
    assert page.count("href='/assets/panel-a7-north'") == 1
    assert "no inspection summary yet" in page


def test_the_asset_card_shows_the_last_capture_and_the_branch_that_scored_it():
    page = views.index_page([{
        "asset_id": "panel-a7-north",
        "last_capture_key": "assets/panel-a7-north/insp1/capture.png",
        "last_captured_at": "2026-08-26T12:00:00+00:00",
        "last_severity_label": "crack",
        "last_branch": "human_approval",
    }])
    assert f"src='/images/assets/panel-a7-north/insp1/capture.png?w={views.THUMB_WIDTH}'" in page
    assert "<span class='pill warn'>crack</span>" in page
    assert "26 Aug 2026" in page


def test_the_empty_gallery_invites_the_first_capture():
    page = views.index_page([])
    assert "<div class='empty'>" in page
    assert "Nothing in memory yet." in page


def test_the_deciding_counts_read_as_english():
    one = views.render_html({}, [_call("assess_quality", "quality_ok"), _finished("first_baseline")])
    assert "1 tool call, 1 threshold," in one
    many = views.render_html({}, [
        _call("assess_quality", "quality_ok"),
        _call("align_to_baseline", "aligned"),
        _finished("aligned"),
    ])
    assert "2 tool calls, 2 thresholds," in many


def test_the_picked_file_hides_the_hint_that_asked_for_one():
    assert "zone.classList.toggle('picked', !preview.hidden);" in JS
    assert ".js .dropzone.picked .drop-hint { display: none; }" in CSS


def test_the_dropzone_mirrors_the_limits_the_server_enforces():
    assert "const MAX_UPLOAD_BYTES = 6 * 1024 * 1024;" in JS
    assert "'image larger than 6 MB'" in JS and "'not a decodable image'" in JS
    assert "input.setCustomValidity(problem);" in JS
    assert "<input class='input' id='capture' type='file'" in views.index_page([])


def test_the_bar_takes_its_tone_from_the_branch():
    approval = {"input_metric": "score", "value": 0.65, "threshold": 0.4,
                "branch": "human_approval"}
    assert views._decided_bar(approval, EN)["tone"] == "warn"
    assert views._decided_bar({**approval, "branch": "auto_write"}, EN)["tone"] == "ok"
    assert views._decided_bar({**approval, "branch": "unrecognized_asset"}, EN)["tone"] == "bad"
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
    item = {"inspection_id": "7f2ac91b04de", "verdict": {
        "input_metric": "score", "value": 0.6543, "threshold": 0.25,
        "branch": "human_approval"}, "metrics": {
        "severity": {"label": "crack", "score": 0.6543},
        "alignment": {"inlier_ratio": 0.9988}}}
    page = _timeline(item, register="tech")
    assert "data-tip='human_approval: Severe enough" in page
    assert "class='tip' data-tip='Share of matched keypoints" in page
    assert "class='tip' data-tip='How much of this photo lines up" in _timeline(item)
    assert "data-tip" not in page.split("class='ends'")[0]
    assert "tabindex='0'" in page


def test_the_warped_capture_says_so_in_the_caption_and_the_alt():
    queued = views.queue_page([{
        "run_id": "7f2ac91b04de", "asset_id": "panel-a7-north", "message": "",
        "image_keys": {"baseline": "a/b.png", "aligned": "a/al.png", "capture": "a/c.png"},
        "metrics": {},
    }], register="tech")
    assert "warped onto the baseline" in queued
    raw = views.queue_page([{
        "run_id": "7f2ac91b04de", "asset_id": "panel-a7-north", "message": "",
        "image_keys": {"baseline": "a/b.png", "capture": "a/c.png"},
        "metrics": {},
    }], register="tech")
    assert "warped onto the baseline" not in raw


def test_the_empty_queue_says_how_much_memory_holds():
    assert "5 assets in memory" in views.queue_page([], assets_in_memory=5)
    assert "1 asset in memory" in views.queue_page([], assets_in_memory=1)
    assert "in memory" not in views.queue_page([], assets_in_memory=0)
    assert "in memory" not in views.queue_page([])


def test_the_upload_form_states_what_it_accepts():
    for register, rule in (("tech", "lowercase letters, digits and hyphens"),
                           ("plain", "Lowercase letters, numbers and hyphens")):
        page = views.index_page([], register=register)
        assert "image/jpeg,image/png" in page
        assert "image/*" not in page
        assert "up to 6&nbsp;MB" in page
        assert rule in page
        assert "title=" not in page


def test_both_upload_fields_carry_a_label():
    page = views.index_page([])
    for field, label in (("asset-id", "asset id"), ("capture", "capture")):
        assert f"<label for='{field}'>{label}</label>" in page
        assert f"id='{field}'" in page
    assert "placeholder='e.g. panel-a7-north'" in page


def test_a_rejected_upload_keeps_the_asset_id_already_typed():
    page = views.index_page([], error="not a decodable image", asset_id="panel-a7-north")
    assert "value='panel-a7-north'" in page
    assert "value=''" in views.index_page([])


@pytest.mark.parametrize("name", ["landing", "index", "asset", "queue", "trace", "activity", "error"])
def test_every_view_opens_with_one_heading_inside_a_main_landmark(name):
    page = _hostile_pages()[name]
    assert page.count("<main id='main-content'>") == 1
    assert page.count("<h1") == 1
    assert page.index("<main id='main-content'>") < page.index("<h1")


def test_the_application_filters_assets_without_an_api_round_trip():
    page = views.index_page([{
        "asset_id": "panel-a7", "last_branch": "human_approval",
    }])
    assert "data-asset-filters" in page
    assert "data-asset-id='panel-a7'" in page
    assert "data-asset-result='human_approval'" in page
    assert "applyAssetFilters" in JS


def test_activity_exposes_failed_runs_and_retry_only_when_allowed():
    page = views.activity_page([{
        "run_id": "abcdef123456", "asset_id": "panel-a7",
        "captured_at": "2026-09-19T12:00:00+00:00", "status": "failed",
        "branch": "", "retryable": True,
    }])
    assert "action='/runs/abcdef123456/retry'" in page
    assert "href='/traces/abcdef123456'" in page


def test_error_page_keeps_actions_inside_the_application():
    page = views.error_page(409, "already_started", "run already started")
    assert "409" in page and "already_started" in page
    assert "href='/app'" in page and "href='/activity'" in page


def test_a_flat_history_at_zero_still_draws_a_sparkline():
    entries = [{"score": 0.0, "bar": None}, {"score": 0.0, "bar": None}]
    line = views._sparkline(entries, 0.0)
    assert [point["y"] for point in line["points"]] == ["24.00", "24.00"]
    assert line["mark"] == "24.00"


def test_a_rejected_start_stops_the_clock_instead_of_spinning():
    assert "if (!res.ok && res.status !== 409) failed();" in JS
    assert "say(T.runStartFailed);" in JS
    assert "stopPolling();" in JS


def test_trace_cards_use_a_neutral_threshold_label():
    card = views._card({"tool": "assess_quality", "policy": {
        "input_metric": "blur_variance", "value": 3.6, "threshold": 100.0,
        "branch": "recapture",
    }}, EN)
    assert card["bar"]["ends"][1]["text"] == "threshold 100"


def test_trace_cards_translate_the_threshold_label():
    card = views._card({"tool": "assess_quality", "policy": {
        "input_metric": "blur_variance", "value": 3.6, "threshold": 100.0,
        "branch": "recapture",
    }}, strings("es"))
    assert card["bar"]["ends"][1]["text"] == "umbral 100"


def test_activity_translates_human_gate_statuses():
    page = views.activity_page([{
        "run_id": "abcdef123456", "asset_id": "panel", "captured_at": "2026-09-19T12:00:00+00:00",
        "status": "approved", "branch": "", "retryable": False,
    }], lang="es")
    assert "aprobada" in page and "rechazada" in page


def test_entries_without_severity_do_not_read_a_trace(monkeypatch):
    calls = []
    monkeypatch.setattr(views, "_verdict_of", lambda item: calls.append(item) or None)

    views._inspection_entry({"metrics": {}}, {}, EN)
    views._queue_entry({"run_id": "abcdef123456", "metrics": {}}, EN)

    assert calls == []


def test_the_poller_defers_the_swap_while_the_block_is_in_use():
    assert "shown.contains(document.activeElement)" in JS
    assert "shown.querySelector('details[open]')" in JS
    assert "if (!pending || busy()) return;" in JS


def test_the_server_writes_the_state_the_live_region_announces():
    queue = views.queue_page([])
    assert ">nothing awaiting approval</span>" in queue
    assert "1 awaiting approval" in views.queue_page([{
        "run_id": "7f2ac91b04de", "asset_id": "a", "message": "",
        "image_keys": {}, "metrics": {},
    }])
    done = views.render_html(STATE, EVENTS)
    assert "done \u00b7 unrecognized_asset" in done
    assert "working \u00b7 1 tool call<" in views.render_html({}, EVENTS[:2])
    for page in (queue, done):
        assert "role='status' aria-live='polite'" in page
        assert page.index("class='runstate'") < page.index("data-poll")


def test_the_timestamp_is_readable_and_survives_a_string_that_is_not_one():
    assert views.when("2026-09-05T19:10:00+00:00") == "5 Sep 2026 \u00b7 19:10 UTC"
    assert views.when("2026-09-05T21:10:00+02:00") == "5 Sep 2026 \u00b7 19:10 UTC"
    assert views.when(HOSTILE) == HOSTILE
    assert views.when("") == ""


def test_the_history_asks_for_a_thumbnail_not_the_whole_capture():
    page = _timeline({"inspection_id": "7f2ac91b04de", "image_keys": {
        "capture": "assets/panel-a7-north/7f2ac91b04de/capture.png"}})
    assert f"capture.png?w={views.THUMB_WIDTH}" in page
    assert "loading='lazy'" in page
    assert "26 Aug 2026" in page


def test_a_rejected_upload_renders_inside_the_page():
    page = views.index_page([], error="not a decodable image")
    assert "role='alert'" in page
    assert "not a decodable image" in page
    assert "Pick the file again" in page
    assert "role='alert'" not in views.index_page([])


def _call(tool, branch=None, **extra):
    event = {"type": "tool_call", "ts": "2026-08-26T12:00:00.000+00:00",
             "tool": tool, "duration_ms": 12.0, **extra}
    if branch:
        event["policy"] = {"input_metric": "m", "value": 1.0, "threshold": 0.5, "branch": branch}
    return event


RAILS = {
    "stopped_early": (
        [_call("assess_quality", "recapture")], trace.DONE,
        ["done", "skipped", "skipped", "skipped", "skipped"],
    ),
    "mid_flight": (
        [_call("assess_quality", "quality_ok")], trace.RUNNING,
        ["done", "active", "pending", "pending", "pending"],
    ),
    "skipped_while_running": (
        [_call("assess_quality", "quality_ok"), _call("align_to_baseline", "aligned"),
         _call("diff_against_memory", "change_confirmed")], trace.RUNNING,
        ["done", "done", "done", "skipped", "active"],
    ),
    "recoverable_tool_error": (
        [_call("assess_quality", error="boom")], trace.RUNNING,
        ["done", "pending", "pending", "pending", "pending"],
    ),
}


@pytest.mark.parametrize("case", list(RAILS))
def test_the_rail_says_which_stages_never_ran_instead_of_promising_them(case):
    events, run_state, expected = RAILS[case]
    steps = views._path(events, run_state, EN)["steps"]
    assert [step["name"] for step in steps] == list(views._ORDER)
    assert [step["state"] for step in steps] == expected


def _finished(branch):
    return {"type": "run_finished", "ts": "2026-08-26T12:00:09.000+00:00",
            "status": "completed" if branch else "failed", "branch": branch, "message": ""}


def test_a_first_baseline_blames_the_missing_baseline_not_the_capture_quality():
    steps = views._path([
        {"type": "decision", "ts": "2026-08-26T12:00:00.000+00:00",
         "input_metric": "baseline_exists", "value": 0.0, "threshold": 1.0,
         "branch": "first_baseline"},
        _call("assess_quality", "quality_ok"),
        _finished("first_baseline"),
    ], trace.DONE, EN)["steps"]
    assert steps[0]["outcome"] == "quality_ok"
    assert [step["outcome"] for step in steps[1:]] == ["not run \u00b7 first_baseline"] * 4


def test_a_run_that_died_without_a_branch_does_not_blame_the_stage_before_it():
    steps = views._path([
        _call("assess_quality", "quality_ok"),
        _call("align_to_baseline", "aligned"),
        _call("diff_against_memory", error="boom"),
        _finished(None),
    ], trace.DONE, EN)["steps"]
    assert steps[2]["failed"] is True
    assert [step["outcome"] for step in steps[3:]] == ["not run", "not run"]


def test_a_stage_the_branch_skipped_names_the_branch_that_skipped_it():
    events, run_state, _ = RAILS["skipped_while_running"]
    steps = views._path(events, run_state, EN)["steps"]
    assert steps[3]["outcome"] == "not run \u00b7 change_confirmed"
    assert steps[0]["tone"] == "ok"


def test_a_retried_tool_is_one_node_that_counts_its_tries():
    steps = views._path(
        [_call("assess_quality", "quality_ok"), _call("align_to_baseline", "retry_classic"),
         _call("align_to_baseline", "aligned")],
        trace.RUNNING,
        EN,
    )["steps"]
    assert steps[1]["tries"] == 2
    assert steps[1]["ms"] == "24"
    assert steps[2]["state"] == "active"


def test_a_run_that_failed_before_any_tool_draws_no_rail():
    assert views._path([{"type": "run_finished", "status": "failed"}], trace.DONE, EN) is None


def test_the_rail_carries_the_stage_state_into_the_markup():
    events, _, _ = RAILS["skipped_while_running"]
    page = views.render_html({"run_id": "abcdef123456"}, events)
    assert "<div class='step done ok'>" in page
    assert "<div class='step skipped'>" in page
    assert "<div class='step active'>" in page
    assert "class='dot'" in page


def test_the_comparator_falls_back_to_the_two_figures_without_javascript():
    page = views.render_html(STATE, [
        {"type": "run_started", "ts": "2026-08-26T12:00:00.000+00:00", "run_id": "abcdef123456",
         "asset_id": "demo-asset", "capture_key": "a/c.png"},
        _call("align_to_baseline", "aligned", args={"baseline_key": "a/b.png"}),
    ])
    assert "<div class='compare' style='--split:50%'>" in page
    assert "alt='baseline in memory'" in page and "alt='capture under inspection'" in page
    assert ".compare .split { display: none; }" in CSS
    assert ".js .compare .shots > figure:first-child" in CSS


def test_the_live_swap_keeps_working_where_view_transitions_are_missing():
    assert "document.startViewTransition ? document.startViewTransition(swap) : swap();" in JS
    assert JS.index("pending = null;") < JS.index("document.startViewTransition ?")
    assert "::view-transition-group(*) { animation-duration: var(--dur-live); }" in CSS
    assert "--dur-live: 0ms" in CSS.split("prefers-reduced-motion")[1]


def _queued(run_id, score):
    return {"run_id": run_id, "asset_id": "panel-a7-north", "message": "",
            "image_keys": {"baseline": "a/b.png", "capture": "a/c.png"},
            "metrics": {"severity": {"label": "crack", "score": score},
                        "diff": {"regions": [{"bbox": [1, 2, 3, 4], "mean_delta": 41.88}]}},
            "verdict": {"input_metric": "score", "value": score, "threshold": 0.4,
                        "branch": "human_approval"}}


def test_the_queue_puts_the_worst_run_first():
    page = views.queue_page([_queued("aaaaaaaaaaaa", 0.41), _queued("bbbbbbbbbbbb", 0.92)])
    assert page.index("bbbbbbbbbbbb") < page.index("aaaaaaaaaaaa")
    assert "<div class='big warn'><span class='n'>0.92</span>" in page


def test_approving_asks_once_before_it_writes_to_memory():
    assert "e.target.closest?.('.acts button')" in JS
    assert "button.textContent = T.confirm;" in JS
    page = views.queue_page([_queued("7f2ac91b04de", 0.5)])
    assert "<form method='post' action='/queue/7f2ac91b04de/approve'>" in page
    assert "<span class='say' role='status' aria-live='polite'></span>" in page


def test_the_armed_confirmation_waits_for_the_operator_instead_of_a_timer():
    armed = JS.split("button.textContent = T.confirm;")[1]
    assert "setTimeout" not in armed.split("addEventListener('focusout'")[0]
    assert "button.focus();" in armed
    assert "if (button && button.dataset.armed) disarm(button);" in JS


def _history(*scores):
    return views.asset_page("array-rooftop", [
        {"sk": f"{store.INSPECTION}2026-09-0{index}#insp{index}",
         "inspection_id": f"insp{index}", "captured_at": f"2026-09-0{index}T12:00:00+00:00",
         "metrics": {"severity": {"label": "crack", "score": score}},
         "verdict": {"input_metric": "score", "value": score, "threshold": 0.4,
                     "branch": "human_approval" if score >= 0.4 else "auto_write"}}
        for index, score in enumerate(scores, start=1)
    ])


def test_the_history_plots_every_inspection_oldest_first():
    page = _history(0.2, 0.9)
    assert "<figure class='spark'>" in page
    assert "points='0.00,20.44 100.00,8.00 '" in page
    assert "class='ok' x1='0.00'" in page and "class='warn' x1='100.00'" in page
    assert "<line class='mark' vector-effect='non-scaling-stroke' x1='0' y1='16.89'" in page


def test_one_inspection_is_not_a_trend():
    assert "<figure class='spark'>" not in _history(0.2)


def test_a_failed_tool_call_leaves_the_rest_of_the_rail_pending():
    steps = views._path([_call("assess_quality", error="boom")], trace.RUNNING, EN)["steps"]
    assert steps[0]["failed"] is True
    assert steps[1]["outcome"] == "waiting"


def test_a_capture_the_dropzone_cannot_type_is_left_to_the_server():
    assert "file.type && !['image/jpeg', 'image/png'].includes(file.type)" in JS


def test_the_baseline_in_force_is_marked_apart_from_the_ones_it_superseded():
    page = views.asset_page("array-rooftop", [
        {"sk": f"{store.BASELINE}2026-09-02", "inspection_id": "insp2",
         "captured_at": "2026-09-02T12:00:00+00:00", "image_key": "a/b2.png"},
        {"sk": f"{store.BASELINE}2026-09-01", "inspection_id": "insp1",
         "captured_at": "2026-09-01T12:00:00+00:00", "image_key": "a/b1.png",
         "superseded_by": "insp2"},
    ])
    assert page.count("<div class='tl promoted now'>") == 1
    assert "<div class='tl promoted'>" in page
    assert ".tl.now .facts" in CSS


def test_the_deciding_number_counts_up_only_when_it_changes():
    assert "if (shown === counted) return;" in JS
    assert "document.querySelector('.hero .big .n')" in JS
    assert "parseFloat(getComputedStyle(root).getPropertyValue('--dur-live'))" in JS


def test_the_landing_renders_its_copy_instead_of_empty_slots():
    page = views.landing_page()
    keys = (
        "landing_hero_title",
        "landing_demo_kicker",
        "landing_demo_title",
        "landing_demo_hint",
        "landing_scenario_1_outcome",
        "landing_scenario_4_outcome",
    )
    for key in keys:
        assert EN[key].split(".")[0] in page, key


def test_a_renamed_copy_key_is_a_render_error_instead_of_a_blank():
    template = views._env.from_string("{{ t.landing_hero_titel }}")
    with pytest.raises(RuntimeError, match="landing_hero_titel"):
        template.render(t=EN)


def _landing_rails():
    panels = views.landing_page().split("landing-scenario-panel")[1:]
    assert len(panels) == 4
    return panels, [re.findall(r"landing-rail-(done|warn|bad|skipped)", p) for p in panels]


def test_the_landing_rail_paints_the_tone_the_application_uses():
    _, states = _landing_rails()
    assert states[0] == ["done", "skipped", "skipped", "skipped", "skipped"]
    assert states[1] == ["warn", "skipped", "skipped", "skipped", "skipped"]
    assert states[2] == ["done", "done", "done", "skipped", "warn"]
    assert states[3] == ["done", "bad", "skipped", "skipped", "skipped"]
    assert views._TONE["recapture"] == states[1][0]
    assert views._TONE["human_approval"] == states[2][4]
    assert views._TONE["unrecognized_asset"] == states[3][1]


def test_the_landing_rail_says_stopped_where_the_run_ended():
    panels, _ = _landing_rails()
    assert EN["landing_state_stopped"] in panels[1]
    assert EN["landing_state_waiting"] not in panels[1]
    assert EN["landing_state_waiting"] in panels[2]
    assert EN["landing_state_stopped"] in panels[3]


def test_the_demo_tabs_are_allowed_to_wrap():
    rule = CSS.split(".landing-scenario-tab {")[1].split("}")[0]
    assert "white-space: nowrap" not in rule
    assert "text-overflow: ellipsis" not in rule


def test_the_error_page_offers_no_unreachable_retry():
    page = views.error_page(409, "already_started", "run already started")
    assert "<form" not in page.split("error-actions")[1].split("</section>")[0]


def test_each_polled_block_carries_its_own_timeout_message():
    assert "block().dataset.pollTimeout" in JS
    assert f"data-poll-timeout='{EN['js_poll_timeout']}'" in views.render_html(STATE, EVENTS)
    assert f"data-poll-timeout='{EN['js_queue_timeout']}'" in views.queue_page([])


def test_a_trace_without_a_verdict_is_not_cached_as_one(tmp_path):
    run_dir = tmp_path / "abcdef123456"
    started = {"type": "run_started", "ts": "2026-09-19T12:00:00.000+00:00", "run_id": "abcdef123456"}
    decided = {
        "type": "decision", "ts": "2026-09-19T12:00:01.000+00:00",
        "input_metric": views.SEVERITY_METRIC, "value": 0.7,
        "threshold": 0.4, "branch": "human_approval",
    }
    runs.write(run_dir, runs.EVENTS, [started])
    assert views._verdict_from_trace(str(run_dir)) is None
    runs.write(run_dir, runs.EVENTS, [started, decided])
    assert views._verdict_from_trace(str(run_dir))["value"] == 0.7


@pytest.mark.parametrize("claimed,shown,hidden,note", [
    (True, "/approve", "/reject", "approve again to finish it"),
    (False, "/reject", "/approve", "reject again to finish it"),
])
def test_an_interrupted_verdict_offers_only_the_claimed_action(claimed, shown, hidden, note):
    page = views.queue_page([{"run_id": "abcdef123456", "asset_id": "panel", "claimed": claimed}])
    assert f"/queue/abcdef123456{shown}" in page
    assert f"/queue/abcdef123456{hidden}" not in page
    assert note in page


def test_an_unclaimed_verdict_offers_both_actions():
    page = views.queue_page([{"run_id": "abcdef123456", "asset_id": "panel"}])
    assert "/queue/abcdef123456/approve" in page and "/queue/abcdef123456/reject" in page
