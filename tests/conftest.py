import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "DealStack" / "sales-prospecting"))

import pytest
from server import security


@pytest.fixture(autouse=True)
def _isolated_security():
    security.request_counts = {}
    security.blocked_ips = set()
    security.login_attempts = {}
    yield
    security.request_counts = {}
    security.blocked_ips = set()
    security.login_attempts = {}
