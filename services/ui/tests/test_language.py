import pytest

from services.observability.tests.sample_run import EVENTS, STATE
from services.ui import views
from services.ui.text import DEFAULT_REGISTER, LANGS, REGISTERS, TEXT, counted, strings


def test_every_string_exists_in_every_language():
    assert set(TEXT) == set(LANGS)
    english = set(TEXT["en"])
    for lang, table in TEXT.items():
        assert set(table) == english, lang


def test_a_language_nobody_ships_falls_back_to_english():
    assert strings("de") == strings("en")
    assert strings("es")["inspect"] != strings("en")["inspect"]


PAGES = {
    "landing": lambda lang: views.landing_page(lang=lang),
    "index": lambda lang: views.index_page([], lang=lang),
    "activity": lambda lang: views.activity_page([], lang=lang),
    "error": lambda lang: views.error_page(404, "not_found", "missing", lang=lang),
    "asset": lambda lang: views.asset_page("panel-a7", [], lang=lang),
    "queue": lambda lang: views.queue_page([], lang=lang),
    "trace": lambda lang: views.render_html(STATE, EVENTS, lang=lang),
}


@pytest.mark.parametrize("name", list(PAGES))
def test_every_view_declares_the_language_it_was_rendered_in(name):
    assert "<html lang='es'" in PAGES[name]("es")
    assert "<html lang='en'" in PAGES[name]("en")


@pytest.mark.parametrize("name", list(PAGES))
def test_every_view_offers_the_other_language_without_leaving_the_page(name):
    page = PAGES[name]("es")
    assert "<a href='?lang=en'" in page
    assert "<a href='?lang=es' class='here' aria-current='true'" in page


def test_the_trace_translates_the_prose_and_leaves_the_measurement_alone():
    body = views.render_html(STATE, EVENTS, lang="es").split("</head>")[1]
    assert "el número que lo decidió" in body
    assert "the number that decided it" not in body
    for untouched in ("inlier_ratio", "unrecognized_asset", "0.259"):
        assert untouched in body


def test_the_agent_message_is_not_translated_because_the_trace_recorded_it():
    message = EVENTS[-1]["message"]
    assert message in views.render_html(STATE, EVENTS, lang="es")


def test_the_date_reads_in_the_language_of_the_page():
    stamp = "2026-09-05T19:10:00+00:00"
    assert views.when(stamp) == "5 Sep 2026 · 19:10 UTC"
    assert views.when(stamp, "es") == "5 sep 2026 · 19:10 UTC"


def test_each_language_counts_with_its_own_plural():
    english, spanish = strings("en"), strings("es")
    assert counted(english, "thresholds", 1) == "1 threshold"
    assert counted(english, "thresholds", 2) == "2 thresholds"
    assert counted(spanish, "thresholds", 1) == "1 umbral"
    assert counted(spanish, "thresholds", 2) == "2 umbrales"


def test_the_home_hands_a_capture_to_anyone_who_has_none():
    page = views.index_page([])
    assert page.count("data-sample=") == len(views.SAMPLES)
    for stem, _ in views.SAMPLES:
        assert (views.STATIC / f"{stem}.png").exists()
        assert f"data-name='{stem}.png'" in page
    assert f"data-asset='{views.SAMPLE_ASSET}'" in page
    assert "picked.items.add(new File(" in (views.STATIC / "app.js").read_text()


def test_the_landing_demo_uses_bundled_captures_without_submitting_them():
    page = views.landing_page()
    assert page.count("data-landing-tab=") == len(views.SAMPLES)
    assert "landing-demo" in page
    script = (views.STATIC / "landing.js").read_text()
    assert "fetch(" not in script and "submit(" not in script


def test_the_sample_captures_are_content_addressed_like_every_other_asset():
    served = {name: media for name, (_, media) in views._assets().items()
              if name.endswith(".png")}
    assert len(served) == len(views.SAMPLES)
    assert set(served.values()) == {"image/png"}


def test_the_primer_opens_itself_only_while_the_gallery_is_empty():
    empty = views.index_page([])
    assert "<details class='howto' open>" in empty
    assert "<details class='howto'>" in views.index_page([{"asset_id": "panel-a7"}])
    assert empty.index("<form class='field'") < empty.index("<details class='howto'")


def test_the_theme_button_uses_its_localized_visible_name():
    spanish = views.index_page([], lang="es")
    assert "<span id='theme-label'>Oscuro</span>" in spanish
    assert "toggle.setAttribute('aria-label'" not in (views.STATIC / "app.js").read_text()


def test_every_technical_wording_has_a_plain_one():
    for lang, table in TEXT.items():
        tech = {key[: -len("_tech")] for key in table if key.endswith("_tech")}
        plain = {key[: -len("_plain")] for key in table if key.endswith("_plain")}
        assert tech == plain, lang
        assert tech


def test_the_register_is_resolved_away_before_a_template_sees_it():
    for lang in LANGS:
        for register in REGISTERS:
            t = strings(lang, register)
            assert not [key for key in t if key.endswith(("_tech", "_plain"))]
            assert t["upload_hint"] == TEXT[lang][f"upload_hint_{register}"]


def test_resolving_the_register_leaves_the_other_suffixes_alone():
    t = strings("es", "tech")
    assert counted(t, "calls", 2) == "2 llamadas a herramientas"
    assert t["plain_name"] == "llano" and t["tech_name"] == "técnico"


def test_a_register_nobody_ships_falls_back_to_plain():
    assert strings("en", "cryptic") == strings("en", DEFAULT_REGISTER)
    assert strings("en", "tech") != strings("en", "plain")


def test_the_plain_register_is_what_a_first_visitor_gets():
    assert DEFAULT_REGISTER == "plain"
    assert "services/agent/policy.py" not in views.index_page([])
    assert "services/agent/policy.py" in views.render_html(STATE, EVENTS, register="tech")


def test_the_plain_register_explains_the_number_instead_of_hiding_it():
    plain = views.render_html(STATE, EVENTS, register="plain")
    tech = views.render_html(STATE, EVENTS, register="tech")
    for untouched in ("inlier_ratio", "0.259", "unrecognized_asset", "sha256"):
        assert untouched in tech
    for untouched in ("inlier_ratio", "0.259", "unrecognized_asset"):
        assert untouched in plain
    assert "How much of this photo lines up" in plain
    assert "Share of matched keypoints" in tech


@pytest.mark.parametrize("name", list(PAGES))
def test_every_view_offers_the_other_register(name):
    page = PAGES[name]("en")
    assert "<a href='?register=tech'" in page
    assert "<a href='?register=plain' class='here' aria-current='true'" in page
