from services.observability.render import render_text
from services.observability.tests.sample_run import EVENTS


def test_render_text_contains_the_causal_line():
    text = render_text(EVENTS)
    assert "inlier_ratio 0.259 < 0.5 -> unrecognized_asset" in text
    assert "align_to_baseline (500.0 ms)" in text
    assert "run finished: completed (unrecognized_asset)" in text
