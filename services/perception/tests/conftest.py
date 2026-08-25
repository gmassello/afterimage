import os

os.environ.setdefault("AFTERIMAGE_WEIGHTS_DIR", "models")

import numpy as np
import pytest

from services.perception.tests.panels import solar_panel


@pytest.fixture(scope="session")
def panel() -> np.ndarray:
    return solar_panel(seed=0)
