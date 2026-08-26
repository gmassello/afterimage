from services.observability.render import render_html, render_text
from services.observability.tests.sample_run import EVENTS, STATE


def test_render_text_contains_the_causal_line():
    text = render_text(EVENTS)
    assert "inlier_ratio 0.259 < 0.5 -> unrecognized_asset" in text
    assert "align_to_baseline (500.0 ms)" in text
    assert "run finished: completed (unrecognized_asset)" in text


def test_render_html_contains_the_causal_values():
    page = render_html(STATE, EVENTS)
    for fragment in ("inlier_ratio", "0.259", "0.5", "unrecognized_asset"):
        assert fragment in page
    assert "align_to_baseline" in page
    assert page.startswith("<!doctype html>")


def test_render_html_escapes_untrusted_strings():
    events = [{
        "type": "run_finished",
        "ts": "2026-08-26T12:00:00.000+00:00",
        "status": "failed",
        "branch": None,
        "message": "<script>alert(1)</script>",
    }]
    page = render_html({}, events)
    assert "<script>" not in page
