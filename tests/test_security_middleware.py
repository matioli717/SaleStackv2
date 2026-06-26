import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "DealStack" / "sales-prospecting"))
from server import security


def test_security_headers_present():
    headers = security.get_security_headers()
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "Strict-Transport-Security" in headers


def test_cors_rejects_unknown_origin():
    security.allowed_origins = ["http://localhost:8765"]
    assert security.get_cors_headers("https://evil.example") == {}


def test_login_rate_limit_and_reset():
    ip = "203.0.113.5"
    security.login_attempts.pop(ip, None)
    for _ in range(5):
        ok, _ = security.check_login_rate_limit(ip)
        assert ok is True
    ok, retry = security.check_login_rate_limit(ip)
    assert ok is False
    assert retry > 0
    security.reset_login_attempts(ip)
    ok, _ = security.check_login_rate_limit(ip)
    assert ok is True
