import pytest

from services.memory import store
from services.observability.tests.sample_run import EVENTS, STATE
from services.ui import views

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
    css = (views.STATIC / "app.css").read_text()
    assert ":root {" in css
    assert ":root[data-theme='light'] {" in css
    assert "color-scheme: dark;" in css and "color-scheme: light;" in css
    page = views.index_page([])
    assert "localStorage.getItem('afterimage-theme')" in page.split("</head>")[0]


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
