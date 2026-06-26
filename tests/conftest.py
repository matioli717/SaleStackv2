import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "DealStack" / "sales-prospecting"))

import pytest
from server import security, Settings  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_security():
    security.request_counts = {}
    security.blocked_ips = set()
    security.login_attempts = {}
    yield
    security.request_counts = {}
    security.blocked_ips = set()
    security.login_attempts = {}


def test_cors_allows_configured_origin():
    security.allowed_origins = ["http://localhost:8765"]
    headers = security.get_cors_headers("http://localhost:8765")
    assert headers["Access-Control-Allow-Origin"] == "http://localhost:8765"
    assert headers["Access-Control-Allow-Credentials"] == "true"


def test_cors_disallows_unknown_origin():
    security.allowed_origins = ["http://localhost:8765"]
    assert security.get_cors_headers("https://evil.example") == {}


def test_cors_allowed_wildcard_without_credentials():
    security.allowed_origins = ["*"]
    headers = security.get_cors_headers("http://localhost:8765")
    assert headers["Access-Control-Allow-Origin"] == "http://localhost:8765"
    assert "Access-Control-Allow-Credentials" not in headers


def test_rate_limit_blocks_after_max_login_attempts():
    client_ip = "203.0.113.10"
    for _ in range(5):
        allowed, _ = security.check_login_rate_limit(client_ip)
        assert allowed is True

    allowed, retry_after = security.check_login_rate_limit(client_ip)
    assert allowed is False
    assert isinstance(retry_after, int)
    assert retry_after > 0


def test_successful_login_resets_rate_limit():
    client_ip = "203.0.113.11"
    for _ in range(5):
        security.record_login_failure(client_ip)

    allowed, _ = security.check_login_rate_limit(client_ip)
    assert allowed is False

    security.reset_login_attempts(client_ip)
    allowed, _ = security.check_login_rate_limit(client_ip)
    assert allowed is True
