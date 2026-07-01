import os, shutil, pathlib

os.environ["STORAGE_MODE"] = "json"
os.environ["JWT_SECRET"] = "test-jwt-secret-for-integration-tests-only-32chars"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "AdminTest123"
os.environ["SHARED_DATA_DIR"] = "/tmp/opencode/shared_test_data"

_shared = pathlib.Path("/tmp/opencode/shared_test_data")
_shared.mkdir(parents=True, exist_ok=True)

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
