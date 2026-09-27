import asyncio
import os
import sys

import numpy as np
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from services.mcp_server import server


def test_classify_severity_rejects_empty_bboxes(monkeypatch):
    monkeypatch.setattr(server.images, "get_image", lambda key: np.zeros((10, 10, 3), dtype=np.uint8))

    with pytest.raises(ValueError, match="positive"):
        server.classify_severity("aligned", "baseline", [0, 0, 0, 1], 0.01)
    with pytest.raises(ValueError, match="outside"):
        server.classify_severity("aligned", "baseline", [20, 20, 1, 1], 0.01)


def test_the_same_tools_are_served_over_stdio_for_outside_clients():
    async def listed():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "services.mcp_server.server"], env=dict(os.environ)
        )
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            return {tool.name for tool in (await session.list_tools()).tools}

    assert asyncio.run(listed()) == {
        "identify_asset", "assess_quality", "align_to_baseline",
        "diff_against_memory", "crop_and_rescan", "classify_severity",
    }
