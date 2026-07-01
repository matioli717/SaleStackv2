import os, sys, json, time, threading, pathlib, urllib.request, urllib.error, socket, pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "DealStack" / "sales-prospecting"))

import server as srv
from http.server import HTTPServer


@pytest.fixture(scope="session")
def shared_dir():
    d = pathlib.Path("/tmp/opencode/shared_test_data")
    d.mkdir(parents=True, exist_ok=True)
    yield d
    import shutil
    shutil.rmtree(str(d), ignore_errors=True)


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def http_server(shared_dir):
    port = _find_free_port()
    server = HTTPServer(("127.0.0.1", port), srv.SalesHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.3)
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def _req(method, url, path, data=None, token=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(f"{url}{path}", data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return e.code, {"raw": body}
    except Exception as e:
        return 0, {"error": str(e)}


ADMIN_TOKEN = None
USER_TOKEN = None


class TestIntegration:

    def test_01_login_admin(self, http_server):
        global ADMIN_TOKEN
        status, data = _req("POST", http_server, "/api/login",
                            {"username": "admin", "password": "AdminTest123"})
        assert status == 200, f"login failed: {data}"
        assert "token" in data
        ADMIN_TOKEN = data["token"]
        status, data = _req("POST", http_server, "/api/admin/activate",
                            {"username": "admin", "plan": "agency"}, token=ADMIN_TOKEN)
        assert status == 200, f"activate admin: {data}"

    def test_02_login_wrong_password(self, http_server):
        status, data = _req("POST", http_server, "/api/login",
                            {"username": "admin", "password": "wrongpass1"})
        assert status == 401

    def test_03_register_user(self, http_server):
        global USER_TOKEN
        status, data = _req("POST", http_server, "/api/register",
                            {"username": "int_user", "password": "TestPass1", "plan": "free"})
        assert status == 201, f"register: {data}"
        status, data = _req("POST", http_server, "/api/login",
                            {"username": "int_user", "password": "TestPass1"})
        assert status == 200
        USER_TOKEN = data["token"]

    def test_04_no_auth_returns_401(self, http_server):
        status, data = _req("GET", http_server, "/api/me")
        assert status == 401

    def test_05_bad_token_returns_401(self, http_server):
        status, data = _req("GET", http_server, "/api/me", token="invalid.jwt.token")
        assert status == 401

    def test_06_get_me(self, http_server):
        status, data = _req("GET", http_server, "/api/me", token=ADMIN_TOKEN)
        assert status == 200
        assert data["username"] == "admin"

    def test_07_save_leads(self, http_server):
        leads = [
            {"id": "lead_a", "lead_name": "Lead A", "phone": "11111", "status": "novo"},
            {"id": "lead_b", "lead_name": "Lead B", "phone": "22222", "status": "novo"},
        ]
        status, data = _req("POST", http_server, "/api/leads", {"leads": leads}, token=ADMIN_TOKEN)
        assert status == 200
        assert data["saved"] == 2

    def test_08_list_leads(self, http_server):
        status, data = _req("GET", http_server, "/api/leads", token=ADMIN_TOKEN)
        assert status == 200
        ids = {l["id"] for l in data["leads"]}
        assert "lead_a" in ids
        assert "lead_b" in ids

    def test_09_leads_have_tenant_id(self, http_server):
        status, data = _req("GET", http_server, "/api/leads", token=ADMIN_TOKEN)
        for l in data["leads"]:
            if l["id"] in ("lead_a", "lead_b"):
                assert "tenant_id" in l

    def test_10_proposals_tenant_isolation(self, http_server):
        status, data = _req("POST", http_server, "/api/proposals", {"proposals": [
            {"id": "prop_a", "lead_name": "Admin Prop"},
        ]}, token=ADMIN_TOKEN)
        assert status == 200

        status, data = _req("POST", http_server, "/api/proposals", {"proposals": [
            {"id": "prop_b", "lead_name": "User Prop"},
        ]}, token=USER_TOKEN)
        assert status == 200

        status, admin_data = _req("GET", http_server, "/api/proposals", token=ADMIN_TOKEN)
        admin_ids = {p["id"] for p in admin_data["proposals"]}
        assert "prop_a" in admin_ids

        status, user_data = _req("GET", http_server, "/api/proposals", token=USER_TOKEN)
        user_ids = {p["id"] for p in user_data["proposals"]}
        assert "prop_b" in user_ids
        assert "prop_a" not in user_ids

    def test_11_webhook_checkout(self, http_server):
        event = {"type": "checkout.session.completed",
                 "data": {"object": {"client_reference_id": "int_user",
                                     "customer": "cus_test", "metadata": {"plan": "starter"}}}}
        status, data = _req("POST", http_server, "/api/webhook/stripe", event)
        assert status == 200
        assert data["received"] is True

    def test_12_webhook_payment_failed(self, http_server):
        event = {"type": "invoice.payment_failed",
                 "data": {"object": {"client_reference_id": "int_user"}}}
        status, data = _req("POST", http_server, "/api/webhook/stripe", event)
        assert status == 200

    def test_13_webhook_subscription_deleted(self, http_server):
        event = {"type": "customer.subscription.deleted",
                 "data": {"object": {"client_reference_id": "int_user"}}}
        status, data = _req("POST", http_server, "/api/webhook/stripe", event)
        assert status == 200

    def test_14_update_lead_status(self, http_server):
        status, data = _req("POST", http_server, "/api/leads/status",
                            {"id": "lead_a", "status": "contatado"}, token=ADMIN_TOKEN)
        assert status == 200
        status, data = _req("GET", http_server, "/api/leads", token=ADMIN_TOKEN)
        lead = next((l for l in data["leads"] if l["id"] == "lead_a"), None)
        assert lead is not None
        assert lead["status"] == "contatado"

    def test_15_get_plans(self, http_server):
        status, data = _req("GET", http_server, "/api/plans", token=ADMIN_TOKEN)
        assert status == 200
        assert "free" in data["plans"]
        assert "stripe_price_id" not in data["plans"]["free"]

    def test_16_get_limits(self, http_server):
        status, data = _req("GET", http_server, "/api/limits", token=ADMIN_TOKEN)
        assert status == 200
        assert "leads" in data
        assert "users" in data

    def test_17_get_stats(self, http_server):
        status, data = _req("GET", http_server, "/api/stats", token=ADMIN_TOKEN)
        assert status == 200
        assert data["total_leads"] >= 2
