import os

import pytest

os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

localstack = pytest.mark.skipif(
    "AWS_ENDPOINT_URL" not in os.environ, reason="requires LocalStack"
)


@pytest.fixture(autouse=True)
def no_second_opinion(monkeypatch):
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)


@pytest.fixture(scope="session", autouse=True)
def memory_backends():
    if "AWS_ENDPOINT_URL" not in os.environ:
        return
    from services.memory import images, store

    store.ensure_table()
    images.ensure_bucket()
