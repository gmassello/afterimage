import numpy as np
import pytest

from services.mcp_server import server


def test_classify_severity_rejects_empty_bboxes(monkeypatch):
    monkeypatch.setattr(server.images, "get_image", lambda key: np.zeros((10, 10, 3), dtype=np.uint8))

    with pytest.raises(ValueError, match="positive"):
        server.classify_severity("aligned", "baseline", [0, 0, 0, 1], 0.01)
    with pytest.raises(ValueError, match="outside"):
        server.classify_severity("aligned", "baseline", [20, 20, 1, 1], 0.01)
