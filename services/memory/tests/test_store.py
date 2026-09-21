import time

from services.memory import store


class FakeTable:
    def __init__(self, pages=()):
        self.pages = list(pages)
        self.reads = []
        self.puts = []
        self.updates = []

    def _page(self, kwargs):
        self.reads.append(kwargs)
        return self.pages.pop(0)

    def scan(self, **kwargs):
        return self._page(kwargs)

    def query(self, **kwargs):
        return self._page(kwargs)

    def put_item(self, Item):
        self.puts.append(Item)

    def update_item(self, **kwargs):
        self.updates.append(kwargs)


def _meta(asset_id):
    return {"pk": store.asset_key(asset_id), "sk": store.META, "asset_id": asset_id}


def test_the_gallery_reads_every_scan_page(monkeypatch):
    table = FakeTable([
        {"Items": [_meta("b")], "LastEvaluatedKey": {"pk": store.asset_key("b")}},
        {"Items": [_meta("a")]},
    ])
    monkeypatch.setattr(store, "_table", lambda: table)
    assert [item["asset_id"] for item in store.list_assets()] == ["a", "b"]
    assert table.reads[1]["ExclusiveStartKey"] == {"pk": store.asset_key("b")}


def test_the_history_reads_every_query_page(monkeypatch):
    table = FakeTable([
        {"Items": [{"sk": "INSPECTION#2"}], "LastEvaluatedKey": {"sk": "INSPECTION#2"}},
        {"Items": [{"sk": "INSPECTION#1"}]},
    ])
    monkeypatch.setattr(store, "_table", lambda: table)
    assert [item["sk"] for item in store.history("panel")] == ["INSPECTION#2", "INSPECTION#1"]
    assert table.reads[1]["ExclusiveStartKey"] == {"sk": "INSPECTION#2"}


def test_every_write_carries_the_retention_ttl(monkeypatch):
    table = FakeTable([{"Items": []}])
    monkeypatch.setattr(store, "_table", lambda: table)
    horizon = int(time.time()) + store.RETENTION_DAYS * 24 * 3600

    store.put_asset("panel")
    store.put_inspection("panel", "insp1", "2026-09-12T09:00:00+00:00", {}, {})
    store.promote_baseline("panel", "insp1", "2026-09-12T09:00:00+00:00", "k.png", 300.0)

    written = [item["ttl"] for item in table.puts]
    written += [update["ExpressionAttributeValues"][":ttl"] for update in table.updates]
    assert len(table.puts) == 2
    assert len(table.updates) == 2
    assert all(abs(int(value) - horizon) < 60 for value in written)
