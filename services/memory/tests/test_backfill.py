from services.conftest import localstack
from services.memory import backfill, store

LEGACY = "panel-legacy"
SUMMARISED = "panel-summarised"
BARE = "panel-bare"
FIRST = "2026-09-12T09:00:00.000+00:00"
SECOND = "2026-09-12T09:30:00.000+00:00"


def _meta(asset_id):
    return next(item for item in store.history(asset_id) if item["sk"] == store.META)


def _strip_summary(asset_id):
    item = _meta(asset_id)
    store._table().put_item(Item={"pk": item["pk"], "sk": store.META, "asset_id": asset_id})


@localstack
def test_an_asset_written_before_the_summary_existed_is_filled_from_its_newest_inspection():
    for captured_at, label in ((FIRST, "soiling"), (SECOND, "crack")):
        store.put_inspection(
            LEGACY, f"insp-{captured_at}", captured_at,
            {"severity": {"label": label}},
            {"capture": f"assets/panel-legacy/{label}/capture.png"},
            {"input_metric": "score", "value": 0.65, "threshold": 0.4, "branch": "human_approval"},
        )
    _strip_summary(LEGACY)

    assert (LEGACY, SECOND) in backfill.summaries()

    meta = _meta(LEGACY)
    assert meta["last_captured_at"] == SECOND
    assert meta["last_severity_label"] == "crack"
    assert meta["last_capture_key"] == "assets/panel-legacy/crack/capture.png"
    assert meta["last_branch"] == "human_approval"


@localstack
def test_an_asset_that_already_carries_a_summary_is_left_alone():
    store.put_inspection(
        SUMMARISED, "insp-1", FIRST, {"severity": {"label": "crack"}},
        {"capture": "assets/panel-summarised/insp-1/capture.png"},
    )

    assert not [row for row in backfill.summaries() if row[0] == SUMMARISED]


@localstack
def test_an_asset_with_no_inspection_stays_without_a_summary():
    store.put_asset(BARE)

    assert not [row for row in backfill.summaries() if row[0] == BARE]
    assert "last_captured_at" not in _meta(BARE)


@localstack
def test_a_dry_run_reports_without_writing():
    store.put_inspection(
        "panel-dry", "insp-1", FIRST, {"severity": {"label": "crack"}},
        {"capture": "assets/panel-dry/insp-1/capture.png"},
    )
    _strip_summary("panel-dry")

    assert ("panel-dry", FIRST) in backfill.summaries(dry_run=True)
    assert "last_captured_at" not in _meta("panel-dry")
