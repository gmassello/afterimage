from services.conftest import localstack
from services.memory import store

ASSET = "panel-summary"
REGISTERED = "panel-registered"
LATE = "panel-late-approval"
FIRST = "2026-09-12T09:00:00.000+00:00"
SECOND = "2026-09-12T09:30:00.000+00:00"


def _meta(asset_id):
    return next(item for item in store.history(asset_id) if item["sk"] == store.META)


@localstack
def test_an_inspection_leaves_the_asset_summary_the_home_reads():
    store.put_asset(ASSET)
    store.put_inspection(
        ASSET, "insp-1", FIRST,
        {"severity": {"score": 0.65, "label": "crack"}},
        {"capture": "assets/panel-summary/insp-1/capture.png"},
        {"input_metric": "score", "value": 0.65, "threshold": 0.4, "branch": "human_approval"},
    )

    meta = _meta(ASSET)
    assert meta["last_capture_key"] == "assets/panel-summary/insp-1/capture.png"
    assert meta["last_captured_at"] == FIRST
    assert meta["last_severity_label"] == "crack"
    assert meta["last_branch"] == "human_approval"


@localstack
def test_registering_the_asset_again_does_not_wipe_its_summary():
    store.put_asset(REGISTERED)
    store.put_inspection(
        REGISTERED, "insp-2", SECOND, {}, {"capture": "assets/panel-registered/insp-2/capture.png"},
    )
    store.put_asset(REGISTERED)

    meta = _meta(REGISTERED)
    assert meta["last_capture_key"] == "assets/panel-registered/insp-2/capture.png"
    assert meta["last_captured_at"] == SECOND
    assert meta["last_severity_label"] == ""


@localstack
def test_an_approval_resolved_late_does_not_walk_the_summary_backwards():
    store.put_inspection(
        LATE, "insp-new", SECOND, {"severity": {"label": "crack"}},
        {"capture": "assets/panel-late-approval/insp-new/capture.png"},
    )
    store.put_inspection(
        LATE, "insp-old", FIRST, {"severity": {"label": "soiling"}},
        {"capture": "assets/panel-late-approval/insp-old/capture.png"},
    )

    meta = _meta(LATE)
    assert meta["last_captured_at"] == SECOND
    assert meta["last_severity_label"] == "crack"
    assert len([item for item in store.history(LATE) if item["sk"].startswith(store.INSPECTION)]) == 2
