from services.conftest import localstack
from services.memory import store

ASSET = "panel-order"
FIRST = "2026-09-12T09:00:00.000+00:00"
SECOND = "2026-09-12T09:30:00.000+00:00"
THIRD = "2026-09-12T10:00:00.000+00:00"


def _baselines(asset_id):
    return {
        item["inspection_id"]: item
        for item in store.history(asset_id)
        if item["sk"].startswith(store.BASELINE)
    }


@localstack
def test_an_older_capture_is_filed_without_moving_the_pointer():
    assert store.promote_baseline(ASSET, "insp-1", FIRST, "k1", 300.0) is True
    assert store.promote_baseline(ASSET, "insp-3", THIRD, "k3", 300.0) is True
    assert store.promote_baseline(ASSET, "insp-2", SECOND, "k2", 300.0) is False

    assert store.current_baseline(ASSET)["inspection_id"] == "insp-3"

    baselines = _baselines(ASSET)
    assert baselines["insp-1"]["superseded_by"] == "insp-3"
    assert baselines["insp-2"]["superseded_by"] == "insp-3"
    assert "superseded_by" not in baselines["insp-3"]


@localstack
def test_repeating_a_promotion_still_supersedes_the_previous_baseline():
    asset = "panel-retry"
    assert store.promote_baseline(asset, "insp-1", FIRST, "k1", 300.0) is True
    assert store.promote_baseline(asset, "insp-2", SECOND, "k2", 300.0) is True
    store._table().update_item(
        Key={"pk": store.asset_key(asset), "sk": f"{store.BASELINE}{FIRST}"},
        UpdateExpression="REMOVE superseded_by",
    )
    assert store.promote_baseline(asset, "insp-2", SECOND, "k2", 300.0) is True

    assert _baselines(asset)["insp-1"]["superseded_by"] == "insp-2"
