import time

import sys, json, os, hashlib, hmac, secrets, re
from pathlib import Path
from functools import wraps
from collections import defaultdict
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    from pydantic import BaseModel, Field, field_validator, ValidationError
    from pydantic_settings import BaseSettings
    PYDANTIC_AVAILABLE = True
except Exception:
    PYDANTIC_AVAILABLE = False
    class BaseModel: pass
    class Field:
        def __init__(self, **kwargs): pass
    def field_validator(*args, **kwargs):
        def decorator(f): return f
        return decorator
    class ValidationError(Exception): pass
    class BaseSettings:
        def __init__(self, **kwargs): pass

class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}
    API_KEYS: str = ""
    ALLOWED_ORIGINS: str = "*"
    RATE_LIMIT_PER_MIN: int = 60
    SHARED_DATA_DIR: str = "~/.hermes/shared_data"

settings = Settings()
SKILL_DIR = Path(__file__).parent
SHARED_DATA_DIR = Path(settings.SHARED_DATA_DIR).expanduser()
SHARED_DATA_DIR.mkdir(parents=True, exist_ok=True)
LEADS_FILE = SHARED_DATA_DIR / "jacarepagua_leads.json"
PROPOSALS_FILE = SHARED_DATA_DIR / "jacarepagua_proposals.json"

file_lock = __import__('threading').Lock()

class SecurityMiddleware:
    def __init__(self):
        self.allowed_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",")]
        self.api_keys = self._load_api_keys()
        self.rate_limit = settings.RATE_LIMIT_PER_MIN
        self.request_counts = defaultdict(list)
        self.blocked_ips = set()
        self._block_lock = __import__('threading').Lock()
    def _load_api_keys(self) -> Dict[str, Dict]:
        keys = {}
        try:
            if settings.API_KEYS:
                imported = json.loads(settings.API_KEYS)
                for item in imported:
                    key_hash = hashlib.sha256(item["key"].encode()).hexdigest()
                    keys[key_hash] = {"name": item.get("name", "unknown"), "scopes": item.get("scopes", ["read"])}
        except Exception:
            pass
        if not keys:
            dev_key = "sk_dev_" + secrets.token_urlsafe(32)
            keys[hashlib.sha256(dev_key.encode()).hexdigest()] = {"name": "development", "scopes": ["read", "write"]}
            print(f"⚠️  DEV API KEY (configure API_KEYS no .env): {dev_key}")
        return keys
    def check_origin(self, origin: str) -> bool:
        if not origin or "*" in self.allowed_origins:
            return True
        for allowed in self.allowed_origins:
            if allowed == "*":
                return True
            if allowed.startswith("*."):
                if origin.endswith(allowed[1:]):
                    return True
            if origin == allowed:
                return True
        return False
    def get_cors_headers(self, origin: str) -> Dict[str, str]:
        if self.check_origin(origin):
            return {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key",
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Max-Age": "86400",
            }
        return {}
    def get_security_headers(self) -> Dict[str, str]:
        return {
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' http://localhost:8765 https://*.github.dev https://*.githubpreview.dev https://*.app.github.dev https://*.onrender.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "X-Permitted-Cross-Domain-Policies": "none",
        }
    def check_rate_limit(self, client_ip: str) -> bool:
        now = time.time()
        minute_ago = now - 60
        with self._block_lock:
            self.request_counts[client_ip] = [ts for ts in self.request_counts[client_ip] if ts > minute_ago]
            if client_ip in self.blocked_ips:
                return False
            if len(self.request_counts[client_ip]) >= self.rate_limit:
                self.blocked_ips.add(client_ip)
                __import__('threading').Timer(900, self._unblock_ip, args=[client_ip]).start()
                return False
            self.request_counts[client_ip].append(now)
            return True
    def _unblock_ip(self, ip: str):
        with self._block_lock:
            self.blocked_ips.discard(ip)
    def hash_api_key(self, api_key: str) -> str:
        return hashlib.sha256(api_key.encode()).hexdigest()
    def verify_api_key(self, provided_key: str) -> Optional[Dict]:
        if not provided_key:
            return None
        provided_hash = self.hash_api_key(provided_key)
        for stored_hash, info in self.api_keys.items():
            if hmac.compare_digest(provided_hash, stored_hash):
                return info
        return None

def require_auth(scopes: List[str] = None):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            client_ip = self.client_address[0]
            if not security.check_rate_limit(client_ip):
                self.send_json(429, {"error": "Rate limit exceeded. Try again in 1 minute."})
                return
            if func.__name__ in ("do_OPTIONS", "serve_dashboard"):
                return func(self, *args, **kwargs)
            auth_header = self.headers.get("Authorization", "")
            api_key = self.headers.get("X-API-Key", "")
            token = None
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
            elif api_key:
                token = api_key
            if not token:
                self.send_json(401, {"error": "Authentication required. Use Authorization: Bearer *** or X-API-Key header"})
                return
            key_info = security.verify_api_key(token)
            if not key_info:
                self.send_json(401, {"error": "Invalid API key"})
                return
            if scopes and not any(s in key_info.get("scopes", []) for s in scopes):
                self.send_json(403, {"error": f"Insufficient scopes. Required: {scopes}"})
                return
            self.auth_client = key_info
            return func(self, *args, **kwargs)
        return wrapper
    return decorator

def load_shared_data(key: str) -> List[Dict]:
    with file_lock:
        if key == "leads":
            if LEADS_FILE.exists():
                return json.loads(LEADS_FILE.read_text(encoding="utf-8"))
            return []
        if key == "proposals":
            if PROPOSALS_FILE.exists():
                return json.loads(PROPOSALS_FILE.read_text(encoding="utf-8"))
            return []
    return []

def save_shared_data(key: str, data: List[Dict]):
    with file_lock:
        if key == "leads":
            LEADS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        elif key == "proposals":
            PROPOSALS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

class SalesHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/dashboard"):
            self.serve_dashboard()
        elif path == "/api/leads":
            self.serve_shared_leads()
        elif path == "/api/stats":
            self.serve_stats()
        elif path == "/api/proposals":
            self.serve_shared_proposals()
        else:
            super().do_GET()
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/leads":
            self.handle_save_leads()
        else:
            self.send_error(404, "Not Found")
    def do_OPTIONS(self):
        origin = self.headers.get("Origin", "")
        cors = security.get_cors_headers(origin)
        self.send_response(200)
        for k, v in cors.items():
            self.send_header(k, v)
        for k, v in security.get_security_headers().items():
            self.send_header(k, v)
        self.end_headers()
    def serve_dashboard(self):
        self.send_response(200)
        origin = self.headers.get("Origin", "")
        for k, v in security.get_cors_headers(origin).items():
            self.send_header(k, v)
        for k, v in security.get_security_headers().items():
            self.send_header(k, v)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write((SKILL_DIR / "dashboard.html").read_bytes())
    @require_auth(scopes=["read"])
    def serve_shared_leads(self):
        leads = load_shared_data("leads")
        self.send_json(200, {"leads": leads, "count": len(leads)})
    @require_auth(scopes=["read"])
    def serve_shared_proposals(self):
        proposals = load_shared_data("proposals")
        self.send_json(200, {"proposals": proposals, "count": len(proposals)})
    @require_auth(scopes=["read"])
    def serve_stats(self):
        leads = load_shared_data("leads")
        proposals = load_shared_data("proposals")
        categories = {}
        for l in leads:
            cat = l.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
        self.send_json(200, {
            "total_leads": len(leads),
            "total_proposals": len(proposals),
            "categories": categories,
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    @require_auth(scopes=["write"])
    def handle_save_leads(self):
        try:
            data = self._read_json_body()
            batch = data.get("leads", [])
            if not batch:
                raise ValueError("leads vazio")
            existing = load_shared_data("leads")
            existing_ids = {l.get("id") or l.get("osm_id") for l in existing}
            new_saved = 0
            for lead in batch:
                lead_id = lead.get("id") or lead.get("osm_id")
                if not lead_id or lead_id in existing_ids:
                    continue
                existing.append(lead)
                existing_ids.add(lead_id)
                new_saved += 1
            save_shared_data("leads", existing)
            self.send_json(200, {"saved": new_saved, "total": len(existing)})
        except ValidationError as e:
            self.send_json(400, {"error": "Validation error", "details": e.errors()})
        except Exception as e:
            print(f"[ERROR] handle_save_leads: {e}", file=sys.stderr)
            self.send_json(500, {"error": "Internal server error"})
    def _read_json_body(self) -> Dict:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        return json.loads(body)
    def send_json(self, status: int, data: Dict):
        self.send_response(status)
        origin = self.headers.get("Origin", "")
        for k, v in security.get_cors_headers(origin).items():
            self.send_header(k, v)
        for k, v in security.get_security_headers().items():
            self.send_header(k, v)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    def log_message(self, format, *args):
        msg = format % args
        if any(x in msg for x in ["401", "403", "404", "413", "429", "500", "..", "etc/passwd"]):
            print(f"[SECURITY] {self.client_address[0]} - {msg}")

security = SecurityMiddleware()

def main():
    port = int(os.getenv("PORT", "8765"))
    print(f"🚀 Sales Prospecting Dashboard (SECURE) rodando em http://0.0.0.0:{port}")
    print(f"   Dashboard: http://0.0.0.0:{port}/dashboard")
    print(f"   Leads:     http://0.0.0.0:{port}/api/leads")
    print(f"   Stats:     http://0.0.0.0:{port}/api/stats")
    print(f"   Shared:    {SHARED_DATA_DIR}")
    print("\nPressione Ctrl+C para parar\n")
    server = HTTPServer(('0.0.0.0', port), SalesHandler)
    server.security_middleware = security
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Servidor parado")
        server.shutdown()

if __name__ == '__main__':
    main()
