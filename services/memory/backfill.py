import sys

from services.memory import store


def _newest_inspection(items: list[dict]) -> dict | None:
    inspections = [
        item for item in items
        if item["sk"].startswith(store.INSPECTION) and item.get("captured_at")
    ]
    if not inspections:
        return None
    return max(inspections, key=lambda item: item["captured_at"])


def summaries(dry_run: bool = False) -> list[tuple[str, str]]:
    filled = []
    for asset in store.list_assets():
        asset_id = asset["asset_id"]
        if asset.get("last_captured_at"):
            continue
        item = _newest_inspection(store.history(asset_id))
        if item is None:
            continue
        if not dry_run:
            store.record_summary(
                asset_id,
                item["captured_at"],
                item.get("metrics") or {},
                item.get("image_keys") or {},
                item.get("verdict") or None,
            )
        filled.append((asset_id, item["captured_at"]))
    return filled


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    filled = summaries(dry_run=dry_run)
    for asset_id, captured_at in filled:
        print(f"{'would fill' if dry_run else 'filled'} {asset_id} from {captured_at}")
    print(f"{len(filled)} asset summaries {'to fill' if dry_run else 'filled'}")


if __name__ == "__main__":
    main()
