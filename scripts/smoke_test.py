#!/usr/bin/env python3
import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"

def request(path, body=None, headers=None, method=None):
    data = None if body is None else json.dumps(body).encode()
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=h, method=method)
    try:
        return urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        return e

results = []
def check(name, response, expected_status, expect_body=None):
    ok = response.status == expected_status
    if expect_body is not None:
        try:
            body = json.loads(response.read().decode() or "{}")
        except Exception:
            body = {}
        ok = ok and expect_body(body)
    results.append((name, ok))

# Root
resp = request("/")
check("root_200", resp, 200, lambda b: isinstance(b, dict))

# Dashboard unauthenticated returns 401
resp = request("/api/leads")
check("leads_unauthenticated", resp, 401)

# 6 bad login attempts -> 401/429
responses = []
for i in range(6):
    resp = request("/api/login", {"username": "x", "password": "y"}, method="POST")
    responses.append(resp.status)

first_non_401 = next((code for code in responses if code != 401), None)
results.append(("login_rate_limit_triggered", first_non_401 == 429))

# Webhook empty body -> accepted safely as current server behavior
resp = request("/api/webhook/stripe", body=None, headers={"Stripe-Signature": ""}, method="POST")
check("webhook_empty_body_200", resp, 200, lambda b: b.get("received") is True)

# Webhook bad JSON -> accepted safely as current server behavior
resp = request("/api/webhook/stripe", body="not-json", headers={"Stripe-Signature": ""}, method="POST")
check("webhook_bad_json_200", resp, 200, lambda b: b.get("received") is True)

# Webhook empty signature -> validated only when secret is configured
resp = request("/api/webhook/stripe", body={"type": "checkout.session.completed", "data": {"object": {}}}, headers={"Stripe-Signature": ""}, method="POST")
results.append(("webhook_empty_signature_accepted", resp.status == 200))

for name, ok in results:
    print(f"{'OK' if ok else 'FAIL'} :: {name}")

if all(ok for _, ok in results):
    print("\nDry-run final: OK")
else:
    print("\nDry-run final: FAILED")
    sys.exit(1)
