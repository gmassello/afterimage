import json
import os
from decimal import Decimal
from functools import lru_cache

import boto3
from boto3.dynamodb.conditions import Attr, Key

TABLE = os.environ.get("AFTERIMAGE_TABLE", "afterimage")

META = "META"
INSPECTION = "INSPECTION#"
BASELINE = "BASELINE#"


def asset_key(asset_id: str) -> str:
    return f"ASSET#{asset_id}"


@lru_cache(maxsize=1)
def _table():
    return boto3.resource("dynamodb").Table(TABLE)


def ensure_table() -> None:
    client = boto3.client("dynamodb")
    try:
        client.create_table(
            TableName=TABLE,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
    except client.exceptions.ResourceInUseException:
        return
    client.get_waiter("table_exists").wait(TableName=TABLE)


def _stored(item: dict) -> dict:
    return json.loads(json.dumps(item), parse_float=Decimal)


def _plain(item: dict) -> dict:
    return json.loads(json.dumps(item, default=float))


def put_asset(asset_id: str, **attrs) -> None:
    values = _stored({"asset_id": asset_id, **attrs})
    _table().update_item(
        Key={"pk": asset_key(asset_id), "sk": META},
        UpdateExpression="SET " + ", ".join(f"#{name} = :{name}" for name in values),
        ExpressionAttributeNames={f"#{name}": name for name in values},
        ExpressionAttributeValues={f":{name}": value for name, value in values.items()},
    )


def _last_seen(captured_at: str, metrics: dict, verdict: dict | None) -> dict:
    severity = metrics.get("severity") or {}
    return {
        "last_captured_at": captured_at,
        "last_severity_label": str(severity.get("label") or ""),
        "last_branch": str((verdict or {}).get("branch") or ""),
    }


def put_inspection(
    asset_id: str,
    inspection_id: str,
    captured_at: str,
    metrics: dict,
    image_keys: dict,
    verdict: dict | None = None,
) -> None:
    _table().put_item(
        Item=_stored(
            {
                "pk": asset_key(asset_id),
                "sk": f"{INSPECTION}{captured_at}#{inspection_id}",
                "inspection_id": inspection_id,
                "captured_at": captured_at,
                "metrics": metrics,
                "image_keys": image_keys,
                "verdict": verdict or {},
            }
        )
    )
    # ponytail: the asset summary is a denormalised copy written right after the inspection, so a
    # crash between the two writes leaves the home card one inspection behind; a TransactWriteItems
    # is the upgrade if that ever matters
    put_asset(asset_id, last_capture_key=image_keys.get("capture", ""),
              **_last_seen(captured_at, metrics, verdict))


def promote_baseline(
    asset_id: str,
    inspection_id: str,
    captured_at: str,
    image_key: str,
    quality_score: float,
) -> bool:
    item = {
        "pk": asset_key(asset_id),
        "sk": f"{BASELINE}{captured_at}",
        "inspection_id": inspection_id,
        "captured_at": captured_at,
        "image_key": image_key,
        "quality_score": quality_score,
    }
    current = current_baseline(asset_id)
    promoted = current is None or current["sk"] <= item["sk"]
    if current is not None and not promoted:
        item["superseded_by"] = current["inspection_id"]

    _table().put_item(Item=_stored(item))

    if promoted and current is not None and current["sk"] < item["sk"]:
        _table().update_item(
            Key={"pk": current["pk"], "sk": current["sk"]},
            UpdateExpression="SET superseded_by = :inspection",
            ExpressionAttributeValues={":inspection": inspection_id},
        )
    return promoted


def current_baseline(asset_id: str) -> dict | None:
    items = _table().query(
        KeyConditionExpression=Key("pk").eq(asset_key(asset_id))
        & Key("sk").begins_with(BASELINE),
        ScanIndexForward=False,
        Limit=1,
    )["Items"]
    return _plain(items[0]) if items else None


def list_assets() -> list[dict]:
    # ponytail: full table scan; fine at demo scale, add an index if assets pass a few thousand
    items = _table().scan(FilterExpression=Attr("sk").eq(META))["Items"]
    return sorted((_plain(item) for item in items), key=lambda item: item["asset_id"])


def history(asset_id: str) -> list[dict]:
    # ponytail: single page, paginate when one asset passes 1 MB of history
    items = _table().query(
        KeyConditionExpression=Key("pk").eq(asset_key(asset_id)),
        ScanIndexForward=False,
    )["Items"]
    return [_plain(item) for item in items]
