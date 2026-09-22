import json
import os
import time
from decimal import Decimal
from functools import lru_cache

import boto3
from boto3.dynamodb.conditions import Attr, ConditionBase, Key
from botocore.exceptions import ClientError

TABLE = os.environ.get("AFTERIMAGE_TABLE", "afterimage")

META = "META"
INSPECTION = "INSPECTION#"
BASELINE = "BASELINE#"

RETENTION_DAYS = 180


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


def _expires_at() -> int:
    return int(time.time()) + RETENTION_DAYS * 24 * 3600


def _all_pages(operation, **kwargs) -> list[dict]:
    items: list[dict] = []
    while True:
        page = operation(**kwargs)
        items.extend(page["Items"])
        start = page.get("LastEvaluatedKey")
        if start is None:
            return items
        kwargs["ExclusiveStartKey"] = start


def _merge_meta(asset_id: str, attrs: dict, condition: ConditionBase | None = None) -> bool:
    values = _stored({**attrs, "ttl": _expires_at()})
    update = {
        "Key": {"pk": asset_key(asset_id), "sk": META},
        "UpdateExpression": "SET " + ", ".join(f"#{name} = :{name}" for name in values),
        "ExpressionAttributeNames": {f"#{name}": name for name in values},
        "ExpressionAttributeValues": {f":{name}": value for name, value in values.items()},
    }
    if condition is not None:
        update["ConditionExpression"] = condition
    try:
        _table().update_item(**update)
    except ClientError as rejected:
        if rejected.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        return False
    return True


def put_asset(asset_id: str, **attrs) -> None:
    _merge_meta(asset_id, {"asset_id": asset_id, **attrs})


def record_summary(asset_id: str, captured_at: str, metrics: dict, image_keys: dict,
                   verdict: dict | None = None) -> bool:
    severity = metrics.get("severity") or {}
    return _merge_meta(
        asset_id,
        {
            "asset_id": asset_id,
            "last_capture_key": image_keys.get("capture", ""),
            "last_captured_at": captured_at,
            "last_severity_label": str(severity.get("label") or ""),
            "last_branch": str((verdict or {}).get("branch") or ""),
        },
        Attr("last_captured_at").not_exists() | Attr("last_captured_at").lte(captured_at),
    )


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
                "ttl": _expires_at(),
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
    record_summary(asset_id, captured_at, metrics, image_keys, verdict)


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
        "ttl": _expires_at(),
        "inspection_id": inspection_id,
        "captured_at": captured_at,
        "image_key": image_key,
        "quality_score": quality_score,
    }
    latest = _table().query(
        KeyConditionExpression=Key("pk").eq(asset_key(asset_id)) & Key("sk").begins_with(BASELINE),
        ScanIndexForward=False,
        Limit=2,
    )["Items"]
    current = next((_plain(found) for found in latest if found["sk"] != item["sk"]), None)
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
    # ponytail: the scan reads every item of the table to keep the META ones; a GSI on sk is the
    # upgrade when the table passes a few thousand items
    items = _all_pages(_table().scan, FilterExpression=Attr("sk").eq(META))
    return sorted((_plain(item) for item in items), key=lambda item: item["asset_id"])


def history(asset_id: str) -> list[dict]:
    items = _all_pages(
        _table().query,
        KeyConditionExpression=Key("pk").eq(asset_key(asset_id)),
        ScanIndexForward=False,
    )
    return [_plain(item) for item in items]
