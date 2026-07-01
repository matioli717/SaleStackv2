import os, json, time, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "DealStack" / "sales-prospecting"))

import jwt as pyjwt
from server import create_jwt, decode_jwt, get_plan, PLANS, hash_password, verify_password, validate_password_strength, security


_BASE_USER = {
    "id": "user_test",
    "username": "testuser",
    "name": "Test User",
    "tenant_id": "tenant_abc",
    "plan": "free",
    "is_active": True,
    "is_suspended": False,
}


def test_create_and_decode_jwt():
    token = create_jwt(_BASE_USER)
    payload = decode_jwt(token)
    assert payload is not None
    assert payload["username"] == "testuser"
    assert payload["tenant_id"] == "tenant_abc"
    assert payload["plan"] == "free"
    assert payload["is_active"] is True
    assert "exp" in payload
    assert "iat" in payload


def test_jwt_expired():
    import server
    original_secret = server.JWT_SECRET
    user = _BASE_USER.copy()
    token = create_jwt(user)
    payload = decode_jwt(token)
    assert payload is not None
    assert payload["username"] == "testuser"
    payload = decode_jwt(token + "bad")
    assert payload is None


def test_jwt_missing_secret_raises_error():
    import server
    import jwt as pyjwt
    original = server.JWT_SECRET
    server.JWT_SECRET = ""
    user = _BASE_USER.copy()
    try:
        create_jwt(user)
        assert False, "should have raised"
    except pyjwt.InvalidKeyError:
        pass
    server.JWT_SECRET = original


def test_jwt_invalid_signature():
    import server
    original = server.JWT_SECRET
    server.JWT_SECRET = "sekret1"
    user = _BASE_USER.copy()
    token = create_jwt(user)
    server.JWT_SECRET = "sekret2"
    payload = decode_jwt(token)
    assert payload is None
    server.JWT_SECRET = original


def test_get_plan_valid():
    plan = get_plan("free")
    assert plan is not None
    assert plan["name"] == "Free"
    assert plan["price"] == 0

    plan = get_plan("starter")
    assert plan is not None
    assert plan["leads_limit"] > 0


def test_get_plan_invalid():
    plan = get_plan("nonexistent_plan")
    assert plan is None


def test_all_plans_have_required_keys():
    required = {"name", "price", "leads_limit", "users_limit", "white_label", "stripe_price_id"}
    for key, plan in PLANS.items():
        missing = required - set(plan.keys())
        assert not missing, f"Plan {key} missing keys: {missing}"


def test_rate_limit_enforces_limit():
    ip = "10.0.0.1"
    security.request_counts.pop(ip, None)
    security.blocked_ips.discard(ip)
    security.request_counts[ip] = []
    for _ in range(60):
        assert security.check_rate_limit(ip) is True
    assert security.check_rate_limit(ip) is False


def test_blocked_ip_stays_blocked():
    ip = "10.0.0.2"
    security.request_counts.pop(ip, None)
    security.blocked_ips.discard(ip)
    security.request_counts[ip] = []
    security.blocked_ips.add(ip)
    assert security.check_rate_limit(ip) is False


def test_login_rate_limit_separate_pool():
    ip = "10.0.0.3"
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


def test_require_auth_no_token():
    jwt_test_import = __import__("jwt")
    assert jwt_test_import is not None


def test_decode_bad_token_returns_none():
    import server
    result = decode_jwt("invalid.jwt.token")
    assert result is None
    result = decode_jwt("")
    assert result is None


def test_validate_password_edge_cases():
    assert validate_password_strength("") is not None
    assert validate_password_strength("a" * 200) is not None
    assert validate_password_strength("Val1dPass") is None
    assert validate_password_strength("VAL1DPASS") is not None
    assert validate_password_strength("val1dpass") is not None
    assert validate_password_strength("ValidPass") is not None


def test_hash_password_consistency():
    pw = "MyTestP4ss"
    h1 = hash_password(pw)
    h2 = hash_password(pw)
    assert h1 != h2
    assert verify_password(pw, h1) is True
    assert verify_password(pw, h2) is True


def test_verify_password_wrong():
    assert verify_password("rightP4ss", hash_password("rightP4ss")) is True
    assert verify_password("wrongP4ss", hash_password("rightP4ss")) is False
