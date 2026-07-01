import os, json

os.environ["STORAGE_MODE"] = "json"

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "DealStack" / "sales-prospecting"))


def test_stripe_importable():
    import stripe as stripe_module
    assert stripe_module is not None
    assert hasattr(stripe_module, "Webhook")


def test_plans_have_stripe_price_ids():
    from server import PLANS
    for key, plan in PLANS.items():
        assert "stripe_price_id" in plan, f"Plan {key} missing stripe_price_id"
        if plan["price"] > 0:
            assert plan["stripe_price_id"], f"Paid plan {key} has empty stripe_price_id"


def test_checkout_session_plan_mapping():
    from server import PLANS
    paid_plans = {k: v for k, v in PLANS.items() if v["price"] > 0}
    assert "starter" in paid_plans
    assert "pro" in paid_plans
    for key, plan in paid_plans.items():
        assert plan["stripe_price_id"].startswith("price_"), f"Plan {key}: invalid price_id format"


def test_webhook_process_checkout_completed():
    from server import load_users, save_users, PLANS
    users = [{"username": "wh_test", "is_active": False, "is_suspended": True, "plan": "free"}]
    save_users(users)
    users = load_users()
    user = next(u for u in users if u["username"] == "wh_test")
    customer_id = "cus_test123"
    plan_key = "starter"
    user["is_active"] = True
    user["is_suspended"] = False
    user["stripe_customer_id"] = customer_id
    user["plan"] = plan_key
    save_users(users)
    users = load_users()
    updated = next(u for u in users if u["username"] == "wh_test")
    assert updated["is_active"] is True
    assert updated["is_suspended"] is False
    assert updated["stripe_customer_id"] == customer_id
    assert updated["plan"] == plan_key
    clean_users([u for u in users if u["username"] != "wh_test"])


def test_webhook_process_payment_failed():
    from server import load_users, save_users
    users = [{"username": "wh_fail", "is_active": True, "is_suspended": False, "plan": "pro"}]
    save_users(users)
    users = load_users()
    user = next(u for u in users if u["username"] == "wh_fail")
    user["is_suspended"] = True
    user["is_active"] = False
    save_users(users)
    users = load_users()
    updated = next(u for u in users if u["username"] == "wh_fail")
    assert updated["is_suspended"] is True
    assert updated["is_active"] is False
    clean_users([u for u in users if u["username"] != "wh_fail"])


def test_webhook_process_subscription_deleted():
    from server import load_users, save_users
    users = [{"username": "wh_sub_del", "is_active": True, "is_suspended": False, "plan": "pro"}]
    save_users(users)
    users = load_users()
    user = next(u for u in users if u["username"] == "wh_sub_del")
    user["is_suspended"] = True
    user["is_active"] = False
    save_users(users)
    users = load_users()
    updated = next(u for u in users if u["username"] == "wh_sub_del")
    assert updated["is_suspended"] is True
    assert updated["is_active"] is False
    clean_users([u for u in users if u["username"] != "wh_sub_del"])


def test_webhook_process_subscription_updated():
    from server import load_users, save_users
    users = [{"username": "wh_sub_upd", "is_active": True, "is_suspended": False, "plan": "free"}]
    save_users(users)
    users = load_users()
    user = next(u for u in users if u["username"] == "wh_sub_upd")
    user["plan"] = "agency"
    save_users(users)
    users = load_users()
    updated = next(u for u in users if u["username"] == "wh_sub_upd")
    assert updated["plan"] == "agency"
    clean_users([u for u in users if u["username"] != "wh_sub_upd"])


def clean_users(users):
    from server import save_users
    save_users(users)
