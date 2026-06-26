import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "DealStack" / "sales-prospecting"))
from server import security, validate_password_strength, hash_password, verify_password


def test_security_headers_present():
    headers = security.get_security_headers()
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "Strict-Transport-Security" in headers
    assert headers["Content-Security-Policy"].startswith("default-src 'self'")
    assert headers["Cross-Origin-Embedder-Policy"] == "require-corp"
    assert headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert headers["Cross-Origin-Resource-Policy"] == "same-origin"
    assert headers["X-DNS-Prefetch-Control"] == "off"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert headers["Permissions-Policy"] is not None
    assert headers["X-Permitted-Cross-Domain-Policies"] == "none"


def test_cors_rejects_unknown_origin():
    security.allowed_origins = ["http://localhost:8765"]
    assert security.get_cors_headers("https://evil.example") == {}


def test_cors_allows_configured_origin():
    security.allowed_origins = ["http://localhost:8765"]
    headers = security.get_cors_headers("http://localhost:8765")
    assert headers["Access-Control-Allow-Origin"] == "http://localhost:8765"
    assert headers["Access-Control-Allow-Credentials"] == "true"


def test_cors_allows_wildcard_with_credentials():
    security.allowed_origins = ["*"]
    headers = security.get_cors_headers("http://localhost:8765")
    assert headers["Access-Control-Allow-Origin"] == "http://localhost:8765"
    assert "Access-Control-Allow-Credentials" in headers


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


def test_password_strength_valid():
    assert validate_password_strength("SenhaForte1") is None


def test_password_strength_too_short():
    err = validate_password_strength("Ab1")
    assert err is not None
    assert "mínimo" in err.lower()


def test_password_strength_no_digit():
    err = validate_password_strength("SenhaForte")
    assert err is not None
    assert "dígito" in err.lower()


def test_password_strength_no_upper():
    err = validate_password_strength("senhaforte1")
    assert err is not None
    assert "maiúscula" in err.lower()


def test_password_strength_no_lower():
    err = validate_password_strength("SENHAFORT1")
    assert err is not None
    assert "minúscula" in err.lower()


def test_hash_password_with_bcrypt():
    h = hash_password("SenhaForte1")
    assert h.startswith("$2b$")
    assert verify_password("SenhaForte1", h) is True
    assert verify_password("SenhaErrada1", h) is False
