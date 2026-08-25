import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def memory_backends():
    if "AWS_ENDPOINT_URL" not in os.environ:
        return
    from services.memory import images, store

    store.ensure_table()
    images.ensure_bucket()
