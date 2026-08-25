import json
import os
from decimal import Decimal
from functools import lru_cache

import boto3
from boto3.dynamodb.conditions import Key

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
    _table().put_item(
        Item=_stored({"pk": asset_key(asset_id), "sk": META, "asset_id": asset_id, **attrs})
    )


def put_inspection(
    asset_id: str,
    inspection_id: str,
    captured_at: str,
    metrics: dict,
    image_keys: dict,
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
            }
        )
    )


def promote_baseline(
    asset_id: str,
    inspection_id: str,
    captured_at: str,
    image_key: str,
    quality_score: float,
) -> None:
    superseded = current_baseline(asset_id)
    if superseded is not None:
        _table().update_item(
            Key={"pk": superseded["pk"], "sk": superseded["sk"]},
            UpdateExpression="SET superseded_by = :inspection",
            ExpressionAttributeValues={":inspection": inspection_id},
        )

    _table().put_item(
        Item=_stored(
            {
                "pk": asset_key(asset_id),
                "sk": f"{BASELINE}{captured_at}",
                "inspection_id": inspection_id,
                "captured_at": captured_at,
                "image_key": image_key,
                "quality_score": quality_score,
            }
        )
    )


def current_baseline(asset_id: str) -> dict | None:
    items = _table().query(
        KeyConditionExpression=Key("pk").eq(asset_key(asset_id))
        & Key("sk").begins_with(BASELINE),
        ScanIndexForward=False,
        Limit=1,
    )["Items"]
    return _plain(items[0]) if items else None


def history(asset_id: str) -> list[dict]:
    # ponytail: single page, paginate when one asset passes 1 MB of history
    items = _table().query(
        KeyConditionExpression=Key("pk").eq(asset_key(asset_id)),
        ScanIndexForward=False,
    )["Items"]
    return [_plain(item) for item in items]
