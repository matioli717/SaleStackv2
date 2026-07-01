import time, sys, json, os, hashlib, hmac, secrets, re, html
from pathlib import Path
from functools import wraps
from collections import defaultdict
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
dotenv_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

try:
    from neon_db import is_neon_available, init_db as neon_init_db, get_leads as neon_get_leads, get_lead as neon_get_lead, get_leads_for_tenant as neon_get_leads_for_tenant, upsert_leads as neon_save_leads, get_proposals as neon_get_proposals, get_proposal as neon_get_proposal, upsert_proposals as neon_save_proposals, get_stats as neon_get_stats, get_metrics as neon_get_metrics, update_lead_status as neon_update_status, migrate_from_json as neon_migrate
    NEON_AVAILABLE = is_neon_available()
    if NEON_AVAILABLE:
        neon_init_db()
        print("[NEON] PostgreSQL conectado")
    else:
        print("[NEON] PostgreSQL nao disponivel (defina DATABASE_URL para ativar)")
except ImportError:
    NEON_AVAILABLE = False
    print("[NEON] neon_db.py nao encontrado, usando JSON")
except Exception as e:
    NEON_AVAILABLE = False
    print(f"[NEON] Erro ao conectar: {e}")

PASSWORD_MIN_LENGTH = 8
PASSWORD_MIN_DIGITS = 1
PASSWORD_MIN_UPPER = 1
PASSWORD_MIN_LOWER = 1

JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    JWT_SECRET = hashlib.sha256(secrets.token_hex(32).encode()).hexdigest()
    print(f"[INIT] JWT_SECRET gerado automaticamente")

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

USERS_FILE = None
LEADS_FILE = None
PROPOSALS_FILE = None

class Settings:
    def __init__(self):
        self.API_KEYS: str = os.environ.get("API_KEYS", "")
        self.ALLOWED_ORIGINS: str = os.environ.get("ALLOWED_ORIGINS", "")
        self.RATE_LIMIT_PER_MIN: int = int(os.environ.get("RATE_LIMIT_PER_MIN", "60"))
        self.MAX_CONTENT_LENGTH: int = int(os.environ.get("MAX_CONTENT_LENGTH", "1048576"))
        self.SHARED_DATA_DIR: str = os.environ.get("SHARED_DATA_DIR", "~/.hermes/shared_data")
        self.ADMIN_USERNAME: str = os.environ.get("ADMIN_USERNAME", "admin")
        self.ADMIN_PASSWORD: str = os.environ.get("ADMIN_PASSWORD", "")
        self.JWT_SECRET: str = os.environ.get("JWT_SECRET", "")
        self.STRIPE_SECRET_KEY: str = os.environ.get("STRIPE_SECRET_KEY", "")
        self.STRIPE_PUBLISHABLE_KEY: str = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
        self.STRIPE_WEBHOOK_SECRET: str = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

settings = Settings()
SKILL_DIR = Path(__file__).parent
SHARED_DATA_DIR = Path(settings.SHARED_DATA_DIR).expanduser()
SHARED_DATA_DIR.mkdir(parents=True, exist_ok=True)
USERS_FILE = SHARED_DATA_DIR / "users.json"
LEADS_FILE = SHARED_DATA_DIR / "leads.json"
PROPOSALS_FILE = SHARED_DATA_DIR / "proposals.json"

# ============================================================
# STAGE 1: PLAN DEFINITIONS + DATA MODELS
# ============================================================

PLANS = {
    "free": {
        "name": "Free", "price": 0, "leads_limit": 0,
        "regions_limit": 0, "users_limit": 1,
        "visual_proposal": "basic", "white_label": False,
        "badge": None, "stripe_price_id": ""
    },
    "starter": {
        "name": "Starter", "price": 97, "leads_limit": 100,
        "regions_limit": 1, "users_limit": 1,
        "visual_proposal": "basic", "white_label": False,
        "badge": "Starter", "stripe_price_id": "price_starter"
    },
    "pro": {
        "name": "Pro", "price": 197, "leads_limit": 300,
        "regions_limit": 3, "users_limit": 3,
        "visual_proposal": "premium", "white_label": False,
        "badge": "Pro", "stripe_price_id": "price_pro"
    },
    "agency": {
        "name": "Agency", "price": 497, "leads_limit": 1000,
        "regions_limit": 999, "users_limit": 10,
        "visual_proposal": "white_label", "white_label": True,
        "badge": "Agency", "stripe_price_id": "price_agency"
    },
    "founder": {
        "name": "Founder", "price": 997, "leads_limit": 999999,
        "regions_limit": 999, "users_limit": 3,
        "visual_proposal": "white_label", "white_label": True,
        "badge": "Founder", "stripe_price_id": "price_founder"
    },
    "founder_lifetime": {
        "name": "Founder Vitalício", "price": 2497, "leads_limit": 999999,
        "regions_limit": 999, "users_limit": 3,
        "visual_proposal": "white_label", "white_label": True,
        "badge": "Lifetime Founder", "stripe_price_id": "price_founder_lifetime",
        "is_lifetime": True, "max_slots": 50
    }
}

AFFILIATES_FILE = SHARED_DATA_DIR / "affiliates.json"
SUBSCRIPTIONS_FILE = SHARED_DATA_DIR / "subscriptions.json"
FOUNDER_SLOTS_FILE = SHARED_DATA_DIR / "founder_slots.json"
LEADS_LOG_FILE = SHARED_DATA_DIR / "leads_log.json"
INVITES_FILE = SHARED_DATA_DIR / "invites.json"

def load_json_file(path: Path) -> list:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []

def save_json_file(path: Path, data: list):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def init_data_files():
    for fname in [AFFILIATES_FILE, SUBSCRIPTIONS_FILE, LEADS_LOG_FILE, INVITES_FILE]:
        if not fname.exists():
            fname.write_text("[]", encoding="utf-8")
    if not FOUNDER_SLOTS_FILE.exists():
        FOUNDER_SLOTS_FILE.write_text(
            json.dumps({"total": 50, "used": 0}, indent=2), encoding="utf-8")

STRIPE_AVAILABLE = False
if settings.STRIPE_SECRET_KEY:
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        STRIPE_AVAILABLE = True
    except ImportError:
        print("[STRIPE] stripe lib not installed. Install with: pip install stripe")

def sync_stripe_products():
    if not STRIPE_AVAILABLE:
        return
    try:
        existing = {p.name: p for p in stripe.Product.list(active=True)}
        for key, plan in PLANS.items():
            if key == "free" or not plan["price"]:
                continue
            if plan["name"] not in existing:
                product = stripe.Product.create(
                    name=plan["name"],
                    description=f"{plan['leads_limit']} leads, {plan['users_limit']} usuarios"
                )
                price_data = {
                    "product": product.id,
                    "unit_amount": plan["price"] * 100,
                    "currency": "brl",
                }
                if plan.get("is_lifetime"):
                    price_data["type"] = "one_time"
                else:
                    price_data["recurring"] = {"interval": "month"}
                price = stripe.Price.create(**price_data)
                plan["stripe_price_id"] = price.id
                print(f"[STRIPE] Created {plan['name']} -> {price.id}")
    except Exception as e:
        print(f"[STRIPE] Sync error: {e}")

def create_stripe_checkout(plan_key: str, username: str, success_url: str, cancel_url: str) -> Optional[str]:
    if not STRIPE_AVAILABLE:
        return None
    plan = PLANS.get(plan_key)
    if not plan or not plan.get("stripe_price_id"):
        return None
    try:
        session = stripe.checkout.Session.create(
            mode="payment" if plan.get("is_lifetime") else "subscription",
            line_items=[{"price": plan["stripe_price_id"], "quantity": 1}],
            client_reference_id=username,
            metadata={"plan": plan_key},
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return session.url
    except Exception as e:
        print(f"[STRIPE] Checkout error: {e}")
        return None

def create_stripe_portal(customer_id: str, return_url: str) -> Optional[str]:
    if not STRIPE_AVAILABLE or not customer_id:
        return None
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return session.url
    except Exception as e:
        print(f"[STRIPE] Portal error: {e}")
        return None

file_lock = __import__('threading').RLock()

def get_plan(plan_key: str) -> Optional[Dict]:
    return PLANS.get(plan_key)

def get_tenant_id(user: Dict) -> str:
    return user.get("tenant_id") or user["id"]

def get_tenant_users(tenant_id: str) -> List[Dict]:
    return [u for u in load_users() if get_tenant_id(u) == tenant_id or u["id"] == tenant_id]

def get_parent_user(user: Dict) -> Optional[Dict]:
    parent_id = user.get("parent_id")
    if not parent_id:
        return None
    for u in load_users():
        if u["id"] == parent_id:
            return u
    return None

def count_tenant_leads(tenant_id: str) -> int:
    return sum(1 for l in load_shared_data("leads") if l.get("tenant_id") == tenant_id)

def check_plan_limit(tenant_id: str, resource: str, value: int = 1) -> bool:
    users = get_tenant_users(tenant_id)
    parent = next((u for u in users if u["id"] == tenant_id), users[0] if users else None)
    if not parent:
        return False
    plan = get_plan(parent.get("plan", "free"))
    if not plan:
        return False
    if resource == "leads":
        current = count_tenant_leads(tenant_id)
        return current + value <= plan["leads_limit"]
    if resource == "users":
        return len(users) + value <= plan["users_limit"]
    if resource == "regions":
        return value <= plan["regions_limit"]
    return True

def validate_password_strength(password: str) -> Optional[str]:
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Senha deve ter no mínimo {PASSWORD_MIN_LENGTH} caracteres"
    if sum(c.isdigit() for c in password) < PASSWORD_MIN_DIGITS:
        return f"Senha deve ter no mínimo {PASSWORD_MIN_DIGITS} dígito(s)"
    if sum(c.isupper() for c in password) < PASSWORD_MIN_UPPER:
        return f"Senha deve ter no mínimo {PASSWORD_MIN_UPPER} letra(s) maiúscula(s)"
    if sum(c.islower() for c in password) < PASSWORD_MIN_LOWER:
        return f"Senha deve ter no mínimo {PASSWORD_MIN_LOWER} letra(s) minúscula(s)"
    return None

def hash_password(password: str) -> str:
    if BCRYPT_AVAILABLE:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    if BCRYPT_AVAILABLE and password_hash.startswith("$2b$"):
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    return hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(), password_hash)

def init_users():
    if USERS_FILE.exists():
        return
    admin_pw = settings.ADMIN_PASSWORD
    if not admin_pw:
        admin_pw = secrets.token_urlsafe(16)
        print(f"[INIT] SENHA ADMIN GERADA: {admin_pw}")
        print(f"[INIT] Guarde esta senha! Faça login com usuario '{settings.ADMIN_USERNAME}'")
    pw_hash = hash_password(admin_pw)
    users = [
        {
            "id": "user_admin_001",
            "username": settings.ADMIN_USERNAME,
            "password_hash": pw_hash,
            "email": "admin@dealstack.io",
            "name": "Administrador",
            "plan": "enterprise",
            "tenant_id": None,
            "parent_id": None,
            "is_active": True,
            "is_suspended": False,
            "stripe_customer_id": "",
            "created_at": datetime.now().isoformat()
        }
    ]
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INIT] Usuário admin criado em {USERS_FILE}")

init_users()
init_data_files()
sync_stripe_products()

if settings.ADMIN_PASSWORD or JWT_SECRET:
    if Path(dotenv_path).exists():
        print("[SECURITY] WARNING: .env file found with credentials. For production:")
        print("[SECURITY]   1. Rotate JWT_SECRET, ADMIN_PASSWORD, and API_KEYS immediately")
        print("[SECURITY]   2. Use environment variables instead of .env on production")
        print("[SECURITY]   3. Set .env file permissions to 600: chmod 600 .env")

if not settings.API_KEYS:
    print("[SECURITY] WARNING: API_KEYS not configured. API key authentication disabled.")
    print("[SECURITY]   Configure API_KEYS in .env or environment variables.")

if JWT_SECRET and (len(JWT_SECRET) < 32 or JWT_SECRET == "ds_jwt_secret_change_in_production_2024"):
    print("[SECURITY] WARNING: JWT_SECRET is weak or default. Generate a strong secret:")
    print("[SECURITY]   python3 -c \"import secrets; print(secrets.token_hex(32))\"")

if settings.ADMIN_PASSWORD and len(settings.ADMIN_PASSWORD) < 12:
    print("[SECURITY] WARNING: ADMIN_PASSWORD is too short (< 12 chars). Use a stronger password.")

def load_users() -> List[Dict]:
    with file_lock:
        if USERS_FILE.exists():
            return json.loads(USERS_FILE.read_text(encoding="utf-8"))
        return []

def save_users(users: List[Dict]):
    with file_lock:
        USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")

def find_user(username: str) -> Optional[Dict]:
    for u in load_users():
        if u.get("username") == username:
            return u
    return None

def create_jwt(user: Dict) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "name": user.get("name", ""),
        "tenant_id": get_tenant_id(user),
        "parent_id": user.get("parent_id", ""),
        "plan": user.get("plan", "free"),
        "is_active": user.get("is_active", False),
        "is_suspended": user.get("is_suspended", False),
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_jwt(token: str) -> Optional[Dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        return None

class SecurityMiddleware:
    def __init__(self):
        self.allowed_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",")]
        self.api_keys = self._load_api_keys()
        self.rate_limit = settings.RATE_LIMIT_PER_MIN
        self.request_counts = defaultdict(list)
        self.blocked_ips = set()
        self._block_lock = __import__('threading').Lock()
        self.public_routes = {"/api/login", "/api/register", "/api/webhook/stripe", "/login"}
        self.login_attempts = defaultdict(list)
        self.login_lock = __import__('threading').Lock()
        self.max_login_attempts = 5
        self.login_window = 300

    def check_login_rate_limit(self, client_ip: str) -> tuple:
        now = time.time()
        window_ago = now - self.login_window
        with self.login_lock:
            attempts = [ts for ts in self.login_attempts.get(client_ip, []) if ts > window_ago]
            self.login_attempts[client_ip] = attempts
            if len(attempts) >= self.max_login_attempts:
                return False, int(self.login_window - (now - attempts[0]))
            self.login_attempts[client_ip].append(now)
            return True, 0

    def record_login_failure(self, client_ip: str):
        with self.login_lock:
            now = time.time()
            window_ago = now - self.login_window
            self.login_attempts[client_ip] = [ts for ts in self.login_attempts.get(client_ip, []) if ts > window_ago]
            self.login_attempts[client_ip].append(now)

    def reset_login_attempts(self, client_ip: str):
        with self.login_lock:
            self.login_attempts.pop(client_ip, None)

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
        return keys

    def check_origin(self, origin: str) -> bool:
        if not origin:
            return False
        for allowed in self.allowed_origins:
            if allowed == origin:
                return True
            if allowed.startswith("*.") and origin.endswith(allowed[1:]):
                return True
            if allowed == "*":
                return True
        return False

    def get_cors_headers(self, origin: str) -> Dict[str, str]:
        if self.check_origin(origin):
            headers = {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key",
                "Access-Control-Max-Age": "86400",
                "Access-Control-Allow-Credentials": "true",
            }
            return headers
        return {}

    def get_security_headers(self) -> Dict[str, str]:
        cs_codespaces = "https://*.app.github.dev https://*.preview.app.github.dev"
        return {
            "Content-Security-Policy": f"default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: https:; connect-src 'self' {cs_codespaces}; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; report-uri /api/csp-report",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "X-Permitted-Cross-Domain-Policies": "none",
            "Cross-Origin-Embedder-Policy": "require-corp",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-origin",
            "X-DNS-Prefetch-Control": "off",
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

    def is_public_route(self, path: str) -> bool:
        return path in self.public_routes or path.startswith("/api/webhook/")

security = SecurityMiddleware()

def require_auth(scopes: Optional[List[str]] = None):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            client_ip = self.client_address[0]
            if not security.check_rate_limit(client_ip):
                self.send_json(429, {"error": "Rate limit exceeded. Try again in 1 minute."})
                return None
            if func.__name__ in ("do_OPTIONS",):
                return func(self, *args, **kwargs)
            auth_header = self.headers.get("Authorization", "")
            api_key = self.headers.get("X-API-Key", "")
            token = None
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
            elif api_key:
                token = api_key
            if token:
                payload = decode_jwt(token)
                if payload and payload.get("is_active"):
                    if payload.get("is_suspended"):
                        self.send_json(403, {"error": "Plano suspenso. Regularize seu pagamento."})
                        return None
                    self.auth_user = payload
                    return func(self, *args, **kwargs)
            key_info = security.verify_api_key(token or "")
            if key_info:
                self.auth_user = {"username": key_info.get("name", "api"), "plan": "api", "is_active": True}
                if scopes and not any(s in key_info.get("scopes", []) for s in scopes):
                    self.send_json(403, {"error": f"Insufficient scopes"})
                    return None
                return func(self, *args, **kwargs)
            if self.is_html_request():
                self.redirect_to_login()
                return None
            self.send_json(401, {"error": "Authentication required"})
            return None
        return wrapper
    return decorator

def load_shared_data(key: str) -> List[Dict]:
    if key == "leads":
        return load_leads()
    if key == "proposals":
        return load_proposals()
    return []

def save_shared_data(key: str, data: List[Dict]):
    if key == "leads":
        save_leads(data)
    elif key == "proposals":
        save_proposals(data)

def load_leads() -> List[Dict]:
    if NEON_AVAILABLE:
        try:
            return neon_get_leads()
        except Exception as e:
            print(f"[NEON] get_leads error: {e}")
    with file_lock:
        if LEADS_FILE.exists():
            return json.loads(LEADS_FILE.read_text(encoding="utf-8"))
        return []

def save_leads(leads: List[Dict]) -> int:
    if NEON_AVAILABLE:
        try:
            return neon_save_leads(leads)
        except Exception as e:
            print(f"[NEON] save_leads error: {e}")
    with file_lock:
        LEADS_FILE.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")
        return len(leads)

def load_proposals() -> List[Dict]:
    if NEON_AVAILABLE:
        try:
            return neon_get_proposals()
        except Exception as e:
            print(f"[NEON] get_proposals error: {e}")
    with file_lock:
        if PROPOSALS_FILE.exists():
            return json.loads(PROPOSALS_FILE.read_text(encoding="utf-8"))
        return []

def save_proposals(proposals: List[Dict]) -> int:
    if NEON_AVAILABLE:
        try:
            return neon_save_proposals(proposals)
        except Exception as e:
            print(f"[NEON] save_proposals error: {e}")
    with file_lock:
        PROPOSALS_FILE.write_text(json.dumps(proposals, ensure_ascii=False, indent=2), encoding="utf-8")
        return len(proposals)

def update_lead_status_wrapper(lead_id: str, new_status: str) -> bool:
    """Update lead status across Neon or JSON storage."""
    if NEON_AVAILABLE:
        try:
            return neon_update_status(lead_id, new_status)
        except Exception as e:
            print(f"[NEON] update_status error: {e}")
    # JSON fallback - load leads, update, save
    leads = load_leads()
    updated = False
    for lead in leads:
        lid = lead.get("id") or lead.get("osm_id")
        if lid == lead_id:
            lead["status"] = new_status
            updated = True
            break
    if updated:
        save_leads(leads)
    return updated

class SalesHandler(SimpleHTTPRequestHandler):
    def is_html_request(self) -> bool:
        accept = self.headers.get("Accept", "")
        path = urlparse(self.path).path
        if path in ("/", "/dashboard", "/login", "/sales", "/admin"):
            return True
        if "text/html" in accept:
            return True
        return False

    def redirect_to_login(self):
        self.send_response(302)
        origin = self.headers.get("Origin", "")
        for k, v in security.get_cors_headers(origin).items():
            self.send_header(k, v)
        for k, v in security.get_security_headers().items():
            self.send_header(k, v)
        self.send_header("Location", "/login")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/":
            self.serve_landing()
        elif path == "/dashboard":
            self.serve_dashboard()
        elif path == "/admin":
            self.serve_admin_page()
        elif path == "/login":
            self.serve_login()
        elif path == "/sales":
            self.serve_page("sales.html", "text/html; charset=utf-8")
        elif path == "/api/leads":
            self.serve_shared_leads()
        elif path == "/api/stats":
            self.serve_stats()
        elif path == "/api/proposals":
            self.serve_shared_proposals()
        elif path == "/api/me":
            self.serve_me()
        elif path == "/api/users":
            self.serve_users()
        elif path == "/api/dependents":
            self.serve_dependents()
        elif path == "/api/csp-report":
            self.serve_csp_report()
        elif path == "/api/plans":
            self.serve_plans()
        elif path == "/api/limits":
            self.serve_limits()
        elif path == "/api/regions":
            self.serve_regions()
        elif path == "/api/affiliate/stats":
            self.serve_affiliate_stats()
        elif path == "/api/affiliates":
            self.serve_affiliates()
        elif path.startswith("/api/admin/"):
            self.serve_admin(path)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/login":
            self.handle_login()
        elif path == "/api/register":
            self.handle_register()
        elif path == "/api/leads":
            self.handle_save_leads()
        elif path == "/api/leads/status":
            self.handle_update_lead_status()
        elif path == "/api/leads/email-status":
            self.handle_update_lead_email_status()
        elif path == "/api/proposals":
            self.handle_save_proposals()
        elif path == "/api/extract":
            self.handle_extract()
        elif path == "/api/webhook/stripe":
            self.handle_stripe_webhook()
        elif path == "/api/invite":
            self.handle_invite()
        elif path.startswith("/api/admin/"):
            self.handle_admin(path)
        elif path == "/api/create-checkout-session":
            self.handle_create_checkout()
        elif path == "/api/csp-report":
            self.handle_csp_report()
        elif path == "/api/create-portal-session":
            self.handle_create_portal()
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

    def serve_landing(self):
        self.send_response(200)
        origin = self.headers.get("Origin", "")
        for k, v in security.get_cors_headers(origin).items():
            self.send_header(k, v)
        for k, v in security.get_security_headers().items():
            self.send_header(k, v)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        landing_path = SKILL_DIR / "landing.html"
        if landing_path.exists():
            self.wfile.write(landing_path.read_bytes())
        else:
            self.wfile.write(self._default_landing_page().encode("utf-8"))

    def serve_admin_page(self):
        token = None
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
        if token:
            payload = decode_jwt(token)
            if payload and payload.get("username") == "admin":
                self.send_response(200)
                origin = self.headers.get("Origin", "")
                for k, v in security.get_cors_headers(origin).items():
                    self.send_header(k, v)
                for k, v in security.get_security_headers().items():
                    self.send_header(k, v)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                admin_path = SKILL_DIR / "admin.html"
                if admin_path.exists():
                    self.wfile.write(admin_path.read_bytes())
                else:
                    self.wfile.write(self._default_admin_page().encode("utf-8"))
                return
        self.send_response(302)
        self.send_header("Location", "/login")
        self.end_headers()

    def serve_login(self):
        self.send_response(200)
        origin = self.headers.get("Origin", "")
        for k, v in security.get_cors_headers(origin).items():
            self.send_header(k, v)
        for k, v in security.get_security_headers().items():
            self.send_header(k, v)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        login_path = SKILL_DIR / "login.html"
        if login_path.exists():
            self.wfile.write(login_path.read_bytes())
        else:
            self.wfile.write(self._default_login_page().encode("utf-8"))

    def _default_login_page(self) -> str:
        return """<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>SaleStack - Login</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'DM Sans', sans-serif; background: #07070A; color: #F0F0EC; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
.login-card { background: #0F0F14; border: 1px solid rgba(255,255,255,0.07); border-radius: 16px; padding: 40px; width: 100%; max-width: 420px; }
.logo { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 24px; color: #fff; text-align: center; margin-bottom: 8px; }
.subtitle { text-align: center; color: #888899; font-size: 13px; margin-bottom: 32px; }
.form-group { margin-bottom: 20px; }
label { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #888899; margin-bottom: 6px; }
input { width: 100%; padding: 12px 14px; background: #07070A; border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; color: #F0F0EC; font-size: 14px; outline: none; transition: border-color 0.2s; }
input:focus { border-color: rgba(0,255,180,0.4); }
.btn { width: 100%; padding: 12px; background: #00FFB4; color: #000; border: none; border-radius: 10px; font-size: 14px; font-weight: 700; cursor: pointer; transition: transform 0.15s; }
.btn:hover { transform: translateY(-1px); }
.error { color: #FF3A6E; font-size: 13px; text-align: center; margin-top: 12px; display: none; }
.loading { text-align: center; margin-top: 12px; color: #888899; font-size: 13px; display: none; }
.info { text-align: center; margin-top: 16px; color: #555566; font-size: 12px; }
</style>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Syne:wght@700;800&display=swap" rel="stylesheet">
</head>
<body>
<div class="login-card">
<div class="logo">SaleStack</div>
<p class="subtitle">Sales Prospecting Platform</p>
<form id="loginForm" onsubmit="return handleLogin(event)">
<div class="form-group">
<label for="username">Usuário</label>
<input type="text" id="username" placeholder="Seu usuário" required autocomplete="username">
</div>
<div class="form-group">
<label for="password">Senha</label>
<input type="password" id="password" placeholder="Sua senha" required autocomplete="current-password">
</div>
<button type="submit" class="btn" id="loginBtn">Entrar</button>
<div class="error" id="errorMsg"></div>
<div class="loading" id="loadingMsg">Autenticando...</div>
</form>
<p class="info">Acesso exclusivo para assinantes SaleStack</p>
</div>
<script>
async function handleLogin(e){
e.preventDefault();
const btn=document.getElementById('loginBtn');
const error=document.getElementById('errorMsg');
const loading=document.getElementById('loadingMsg');
error.style.display='none';
loading.style.display='block';
btn.disabled=true;
try{
const res=await fetch('/api/login',{
method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({username: document.getElementById('username').value, password: document.getElementById('password').value})
});
const data=await res.json();
if(!res.ok){ throw new Error(data.error||'Erro ao autenticar'); }
localStorage.setItem('dealstack_token', data.token);
window.location.href='/dashboard';
}catch(e){
error.textContent=e.message;
error.style.display='block';
}finally{
loading.style.display='none';
btn.disabled=false;
}
return false;
}
document.addEventListener('DOMContentLoaded',()=>{
const token=localStorage.getItem('dealstack_token');
if(token){ fetch('/api/me',{headers:{'Authorization':'Bearer '+token}}).then(r=>{if(r.ok)window.location.href='/dashboard';}).catch(()=>{}); }
});
</script>
</body>
</html>"""

    def _default_landing_page(self) -> str:
        plans_html = ""
        for key, p in PLANS.items():
            if key == "free":
                continue
            price = f"R$ {p['price']}" if p['price'] else "Grátis"
            period = "/mês" if not p.get("is_lifetime") else " único"
            popular = " style='border-color:#00FFB4;box-shadow:0 0 30px rgba(0,255,180,0.15)'" if key == "pro" else ""
            badge = f"<span style='display:inline-block;background:rgba(0,255,180,0.15);color:#00FFB4;padding:4px 12px;border-radius:999px;font-size:11px;font-weight:700;letter-spacing:0.5px;margin-bottom:12px'>{p['badge']}</span>" if p.get('badge') else ""
            plans_html += f"""
            <div class="plan-card"{popular}>
                {badge}
                <h3 style="font-family:'Syne',sans-serif;font-size:20px;color:#F0F0EC;margin:0 0 4px 0">{p['name']}</h3>
                <div style="font-size:32px;font-weight:800;color:#fff;margin:12px 0">{price}<span style="font-size:14px;font-weight:400;color:#888899">{period}</span></div>
                <ul style="list-style:none;padding:0;margin:16px 0 24px 0;text-align:left;font-size:13px">
                    <li style="padding:6px 0;color:#bbbbcc">✓ {p['leads_limit']:,} leads</li>
                    <li style="padding:6px 0;color:#bbbbcc">✓ {p['regions_limit'] if p['regions_limit'] < 900 else 'Ilimitadas'} regiões</li>
                    <li style="padding:6px 0;color:#bbbbcc">✓ {p['users_limit']} usuários</li>
                    <li style="padding:6px 0;color:#bbbbcc">✓ {'White label' if p['white_label'] else 'Proposta básica'}</li>
                </ul>
                <a href="/login?plan={key}" style="display:block;text-align:center;padding:12px;background:{'#00FFB4' if key != 'founder_lifetime' else 'linear-gradient(135deg,#F0C040,#FF8C00)'};color:#000;border-radius:10px;font-weight:700;font-size:14px;text-decoration:none;transition:transform 0.15s">Assinar</a>
            </div>"""
        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>SaleStack - Plataforma de Prospecção</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Syne:wght@700;800&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'DM Sans',sans-serif;background:#07070A;color:#F0F0EC;min-height:100vh;overflow-x:hidden}}
body::before{{content:'';position:fixed;top:0;left:0;right:0;bottom:0;background:radial-gradient(circle at 50% -20%,rgba(0,255,180,0.06),transparent 65%);pointer-events:none;z-index:0}}
.hero{{text-align:center;padding:80px 20px 40px;position:relative;z-index:1}}
.hero h1{{font-family:'Syne',sans-serif;font-size:48px;font-weight:800;color:#fff;margin-bottom:12px;letter-spacing:-0.02em}}
.hero h1 span{{background:linear-gradient(135deg,#00FFB4,#7B5CFA);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.hero p{{color:#888899;font-size:18px;max-width:600px;margin:0 auto 32px;line-height:1.6}}
.hero .ctas{{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}}
.hero .btn{{padding:14px 32px;border-radius:12px;font-weight:700;font-size:15px;text-decoration:none;transition:transform 0.15s;display:inline-block}}
.hero .btn:hover{{transform:translateY(-2px)}}
.hero .btn-primary{{background:#00FFB4;color:#000}}
.hero .btn-secondary{{background:rgba(255,255,255,0.08);color:#F0F0EC;border:1px solid rgba(255,255,255,0.1)}}
.pricing{{max-width:1100px;margin:0 auto;padding:40px 20px 60px;position:relative;z-index:1}}
.pricing h2{{font-family:'Syne',sans-serif;font-size:32px;text-align:center;color:#fff;margin-bottom:8px}}
.pricing .sub{{text-align:center;color:#888899;font-size:14px;margin-bottom:40px}}
.plan-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}}
.plan-card{{background:#0F0F14;border:1px solid rgba(255,255,255,0.07);border-radius:16px;padding:28px;text-align:center;transition:transform 0.2s,border-color 0.2s}}
.plan-card:hover{{transform:translateY(-4px);border-color:rgba(255,255,255,0.15)}}
.affiliate{{max-width:600px;margin:0 auto;padding:40px 20px 60px;text-align:center;position:relative;z-index:1}}
.affiliate .card{{background:#0F0F14;border:1px solid rgba(255,255,255,0.07);border-radius:16px;padding:40px}}
.affiliate h2{{font-family:'Syne',sans-serif;font-size:28px;color:#fff;margin-bottom:8px}}
.affiliate p{{color:#888899;font-size:14px;margin-bottom:24px;line-height:1.6}}
.affiliate .btn{{padding:14px 32px;background:linear-gradient(135deg,#7B5CFA,#00FFB4);color:#000;border-radius:12px;font-weight:700;font-size:15px;text-decoration:none;display:inline-block;transition:transform 0.15s}}
.affiliate .btn:hover{{transform:translateY(-2px)}}
.founder-counter{{display:inline-block;background:rgba(240,192,64,0.12);color:#F0C040;padding:6px 16px;border-radius:999px;font-size:13px;font-weight:700;margin-top:16px}}
footer{{text-align:center;padding:30px;color:#444455;font-size:12px;position:relative;z-index:1}}
</style>
</head>
<body>
<div class="hero">
<h1>Prospecção <span>Inteligente</span> de Clientes</h1>
<p>Extraia leads qualificados do Google Maps, gere propostas visuais com IA e feche mais negócios com a plataforma tudo-em-um da SaleStack.</p>
<div class="ctas">
<a href="/login" class="btn btn-primary">Começar Agora</a>
<a href="#planos" class="btn btn-secondary">Ver Planos</a>
</div>
</div>
<div class="pricing" id="planos">
<h2>Planos e Preços</h2>
<p class="sub">Escolha o plano ideal para seu negócio. Cancele quando quiser.</p>
<div class="plan-grid">
{plans_html}
</div>
</div>
<div class="affiliate">
<div class="card">
<h2>💰 Programa de Afiliados</h2>
<p>Ganhe comissões recorrentes indicando a SaleStack para outros profissionais. Compartilhe seu link exclusivo e receba <strong style="color:#00FFB4">30%</strong> de comissão todo mês!</p>
<a href="/login?ref=affiliate" class="btn">Quero ser Afiliado</a>
</div>
</div>
<footer>© 2024 SaleStack. Todos os direitos reservados.</footer>
</body>
</html>"""

    def _default_admin_page(self) -> str:
        plans_opts = "".join(f'<option value="{k}">{p["name"]}</option>' for k, p in PLANS.items())
        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>SaleStack - Admin</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Syne:wght@700;800&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'DM Sans',sans-serif;background:#07070A;color:#F0F0EC;min-height:100vh;overflow-x:hidden}}
body::before{{content:'';position:fixed;top:0;left:0;right:0;bottom:0;background:radial-gradient(circle at 50% -20%,rgba(123,92,250,0.06),transparent 65%);pointer-events:none;z-index:0}}
header{{position:sticky;top:0;z-index:50;background:rgba(7,7,10,0.85);backdrop-filter:blur(12px);border-bottom:1px solid rgba(255,255,255,0.07);padding:16px 24px}}
.header-inner{{display:flex;align-items:center;justify-content:space-between;max-width:1280px;margin:0 auto}}
.logo{{font-family:'Syne',sans-serif;font-weight:800;font-size:22px;color:#fff}}
.tagline{{font-size:10px;letter-spacing:3px;text-transform:uppercase;color:#444455;margin-left:10px}}
.admin-badge{{background:rgba(123,92,250,0.2);color:#7B5CFA;padding:2px 10px;border-radius:999px;font-size:10px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;margin-left:8px}}
.container{{max-width:1280px;margin:0 auto;padding:24px;position:relative;z-index:1}}
.stats-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px}}
.stat-card{{background:#0F0F14;border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:20px}}
.stat-num{{font-size:28px;font-weight:800;color:#fff}}
.stat-label{{font-size:12px;color:#888899;margin-top:4px}}
.card{{background:#0F0F14;border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:20px;margin-bottom:16px}}
.card h3{{font-family:'Syne',sans-serif;font-size:16px;color:#fff;margin-bottom:16px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;padding:10px 8px;color:#888899;font-size:11px;text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid rgba(255,255,255,0.07);font-weight:600}}
td{{padding:10px 8px;border-bottom:1px solid rgba(255,255,255,0.04);color:#bbbbcc}}
tr:hover td{{background:rgba(255,255,255,0.03)}}
.badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:10px;font-weight:700}}
.badge-active{{background:rgba(0,255,180,0.12);color:#00FFB4}}
.badge-suspended{{background:rgba(255,58,110,0.12);color:#FF3A6E}}
.btn{{padding:8px 14px;border-radius:8px;font-weight:600;font-size:12px;font-family:'DM Sans',sans-serif;border:none;cursor:pointer;transition:transform 0.15s;white-space:nowrap}}
.btn:hover{{transform:translateY(-1px)}}
.btn-primary{{background:#00FFB4;color:#000}}
.btn-danger{{background:#FF3A6E;color:#fff}}
.btn-outline{{background:transparent;border:1px solid rgba(255,255,255,0.15);color:#F0F0EC}}
.btn-sm{{padding:5px 10px;font-size:11px}}
.action-bar{{display:flex;gap:8px;align-items:center;margin-bottom:16px}}
select{{padding:8px 10px;background:#07070A;border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#F0F0EC;font-size:13px;outline:none}}
input{{padding:8px 10px;background:#07070A;border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#F0F0EC;font-size:13px;outline:none}}
.refresh{{color:#888899;cursor:pointer;font-size:12px;text-decoration:underline}}
.refresh:hover{{color:#00FFB4}}
.affiliates-list{{font-size:13px;color:#bbbbcc;line-height:2}}
</style>
</head>
<body>
<header>
<div class="header-inner">
<div><span class="logo">SaleStack</span><span class="tagline">ADMIN</span><span class="admin-badge">ADMIN</span></div>
<div><button class="btn btn-outline btn-sm" onclick="localStorage.removeItem('dealstack_token');window.location.href='/login'">Sair</button></div>
</div>
</header>
<div class="container">
<div class="stats-grid" id="statsGrid"></div>
<div class="card">
<div class="action-bar">
<h3 style="flex:1;font-family:'Syne',sans-serif;font-size:16px;color:#fff">Usuários</h3>
<select id="planFilter"><option value="">Todos os planos</option>{plans_opts}</select>
<input id="searchUser" placeholder="Buscar usuário..." oninput="renderUsers()">
<button class="btn btn-primary btn-sm" onclick="syncStripe()">Sincronizar Stripe</button>
<button class="btn btn-outline btn-sm" onclick="loadStats()">↻</button>
</div>
<div id="usersTable"><p style="color:#888899;font-size:14px">Carregando...</p></div>
</div>
<div class="card">
<h3>Programa de Afiliados</h3>
<div id="affiliatesList"><p style="color:#888899;font-size:14px">Carregando...</p></div>
</div>
</div>
<script>
const token=localStorage.getItem('dealstack_token');
if(!token) window.location.href='/login';
const headers={{'Authorization':'Bearer '+token,'Content-Type':'application/json'}};
async function api(path,opts={{}}){{const res=await fetch('/api'+path,{{...opts,headers}});if(res.status===401){{localStorage.removeItem('dealstack_token');window.location.href='/login'}}return res.json()}}
async function loadStats(){{const s=await api('/admin/stats');document.getElementById('statsGrid').innerHTML=`
<div class="stat-card"><div class="stat-num">${{s.total_users||0}}</div><div class="stat-label">Total de Usuários</div></div>
<div class="stat-card"><div class="stat-num">${{s.active_users||0}}</div><div class="stat-label">Ativos</div></div>
<div class="stat-card"><div class="stat-num">${{s.suspended||0}}</div><div class="stat-label">Suspensos</div></div>
<div class="stat-card"><div class="stat-num" style="color:#00FFB4">R$ ${{(s.mrr||0).toLocaleString('pt-BR')}}</div><div class="stat-label">MRR</div></div>
`;renderUsers();renderAffiliates()}}
async function renderUsers(){{const u=await api('/admin/users');const planFilter=document.getElementById('planFilter').value;const q=document.getElementById('searchUser').value.toLowerCase();const filtered=u.users.filter(uu=>((!planFilter||uu.plan===planFilter)&&(!q||uu.username.toLowerCase().includes(q)||(uu.email||'').toLowerCase().includes(q))));document.getElementById('usersTable').innerHTML=`<table><thead><tr><th>Usuário</th><th>Email</th><th>Plano</th><th>Status</th><th>Criado</th><th>Ações</th></tr></thead><tbody>${{filtered.map(uu=>`
<tr>
<td><strong>${{esc(uu.username)}}</strong></td>
<td>${{esc(uu.email||'-')}}</td>
<td>${{uu.plan||'free'}}</td>
<td>${{uu.is_active?('<span class="badge badge-active">Ativo</span>'):uu.is_suspended?('<span class="badge badge-suspended">Suspenso</span>'):'<span style="color:#444455">Inativo</span>'}}</td>
<td>${{(uu.created_at||'').slice(0,10)}}</td>
<td>
<button class="btn btn-primary btn-sm" onclick="activateUser('${{uu.username}}')" ${{uu.is_active?'style="display:none"':''}}>Ativar</button>
<button class="btn btn-danger btn-sm" onclick="blockUser('${{uu.username}}')" ${{uu.is_active?'':'style="display:none"':''}}>Bloquear</button>
<button class="btn btn-outline btn-sm" onclick="deleteUser('${{uu.username}}')">Excluir</button>
</td>
</tr>`).join('')}}</tbody></table>`}}
function esc(t){{const d=document.createElement('div');d.textContent=t||'';return d.innerHTML}}
async function activateUser(u){{await api('/admin/activate',{{method:'POST',body:JSON.stringify({{username:u,plan:''}})}});loadStats()}}
async function blockUser(u){{await api('/admin/block',{{method:'POST',body:JSON.stringify({{username:u}})}});loadStats()}}
async function deleteUser(u){{if(!confirm('Excluir '+u+'?'))return;await api('/admin/delete',{{method:'POST',body:JSON.stringify({{username:u}})}});loadStats()}}
async function syncStripe(){{const btn=event.target;btn.textContent='Sincronizando...';btn.disabled=true;await api('/admin/stripe-sync',{{method:'POST'}});btn.textContent='Sincronizado ✓';setTimeout(()=>{{btn.textContent='Sincronizar Stripe';btn.disabled=false}},2000)}}
async function renderAffiliates(){{try{{const a=await api('/affiliates');let html='';if(!a.affiliates||a.affiliates.length===0){{html='<p style="color:#555566">Nenhum afiliado registrado</p>'}}else{{a.affiliates.forEach(aa=>{{html+='<div class="affiliates-list"><strong>'+esc(aa.affiliate_username||'')+'</strong> — '+aa.total_referrals+' refs, R$ '+(aa.earnings||0).toFixed(2)+'</div>'}})}}document.getElementById('affiliatesList').innerHTML=html}}catch(e){{document.getElementById('affiliatesList').innerHTML='<p style="color:#555566">Nenhum afiliado</p>'}}}}
loadStats();
</script>
</body>
</html>"""

    def serve_page(self, filename: str, content_type: str = "text/html; charset=utf-8"):
        self.send_response(200)
        origin = self.headers.get("Origin", "")
        for k, v in security.get_cors_headers(origin).items():
            self.send_header(k, v)
        for k, v in security.get_security_headers().items():
            self.send_header(k, v)
        self.send_header('Content-Type', content_type)
        self.end_headers()
        target = SKILL_DIR / filename
        if not target.exists():
            self.send_error(404, "File Not Found")
            return
        self.wfile.write(target.read_bytes())

    @require_auth(scopes=["read"])
    def serve_shared_leads(self):
        tenant_id = self.auth_user.get("tenant_id") or self.auth_user["sub"]
        leads = load_shared_data("leads")
        filtered = [l for l in leads if not l.get("tenant_id") or l.get("tenant_id") == tenant_id]
        self.send_json(200, {
            "leads": filtered,
            "count": len(filtered),
            "debug_match": {
                "user_tenant_id": tenant_id,
                "lead_tenant_ids": sorted({l.get("tenant_id") for l in leads if l.get("tenant_id")}),
                "total_loaded": len(leads),
            },
        })

    @require_auth(scopes=["read"])
    def serve_shared_proposals(self):
        proposals = load_shared_data("proposals")
        self.send_json(200, {"proposals": proposals, "count": len(proposals)})

    @require_auth(scopes=["read"])
    def serve_stats(self):
        tenant_id = self.auth_user.get("tenant_id") or self.auth_user["sub"]
        if NEON_AVAILABLE:
            try:
                metrics = neon_get_metrics(tenant_id)
                metrics["categories"] = {}
                self.send_json(200, metrics)
                return
            except Exception as e:
                print(f"[NEON] get_metrics error: {e}")
        leads = [l for l in load_leads() if not l.get("tenant_id") or l.get("tenant_id") == tenant_id]
        proposals = load_proposals()
        categories = {}
        for l in leads:
            cat = l.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
        by_status = {}
        closed = 0
        in_progress = 0
        for l in leads:
            s = l.get("status", "novo")
            by_status[s] = by_status.get(s, 0) + 1
            if s == "fechado":
                closed += 1
            elif s in ("contatado", "negociacao"):
                in_progress += 1
        total = len(leads)
        conv = round((closed / total * 100), 1) if total > 0 else 0
        self.send_json(200, {
            "total_leads": total,
            "total_proposals": len(proposals),
            "categories": categories,
            "by_status": by_status,
            "closed": closed,
            "in_progress": in_progress,
            "conversion_rate": conv,
            "leads_last_7d": 0,
            "leads_last_30d": 0,
            "leads_by_day": [],
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    @require_auth()
    def serve_me(self):
        user_data = {k: v for k, v in self.auth_user.items() if k not in ("exp", "iat")}
        full_user = find_user(self.auth_user.get("username", ""))
        if full_user:
            user_data["email"] = full_user.get("email", "")
            user_data["created_at"] = full_user.get("created_at", "")
        plan = get_plan(self.auth_user.get("plan", "free"))
        if plan:
            user_data["plan_info"] = {
                "name": plan["name"],
                "price": plan["price"],
                "leads_limit": plan["leads_limit"],
                "users_limit": plan["users_limit"],
                "white_label": plan["white_label"],
                "badge": plan["badge"],
            }
        self.send_json(200, user_data)

    @require_auth()
    def serve_users(self):
        if self.auth_user.get("username") != "admin":
            self.send_json(403, {"error": "Apenas admin pode ver usuarios"})
            return
        users = load_users()
        safe_users = [{k: v for k, v in u.items() if k != "password_hash"} for u in users]
        self.send_json(200, {"users": safe_users})

    @require_auth()
    def serve_dependents(self):
        tenant_id = self.auth_user.get("tenant_id") or self.auth_user["sub"]
        dependents = [u for u in load_users() if u.get("parent_id") and get_tenant_id(u) == tenant_id and u["id"] != self.auth_user["sub"]]
        safe = [{k: v for k, v in u.items() if k != "password_hash"} for u in dependents]
        self.send_json(200, {"dependents": safe, "count": len(safe)})

    def serve_csp_report(self):
        self.send_response(204)
        origin = self.headers.get("Origin", "")
        for k, v in security.get_cors_headers(origin).items():
            self.send_header(k, v)
        self.end_headers()

    @require_auth()
    def serve_plans(self):
        public_plans = {}
        for key, p in PLANS.items():
            public_plans[key] = {k: v for k, v in p.items() if k != "stripe_price_id"}
        self.send_json(200, {"plans": public_plans})

    @require_auth()
    def serve_limits(self):
        tenant_id = self.auth_user.get("tenant_id") or self.auth_user["sub"]
        plan = get_plan(self.auth_user.get("plan", "free"))
        users = load_users()
        tenant_users = [u for u in users if get_tenant_id(u) == tenant_id or u["id"] == tenant_id]
        current_leads = count_tenant_leads(tenant_id)
        self.send_json(200, {
            "leads": {"current": current_leads, "limit": plan["leads_limit"] if plan else 0},
            "users": {"current": len(tenant_users), "limit": plan["users_limit"] if plan else 1},
            "plan": self.auth_user.get("plan", "free"),
        })

    @require_auth()
    def serve_regions(self):
        tenant_id = self.auth_user.get("tenant_id") or self.auth_user["sub"]
        leads = [l for l in load_shared_data("leads") if l.get("tenant_id") == tenant_id]
        regions = set()
        for l in leads:
            loc = l.get("location", "") or l.get("city", "") or l.get("region", "") or ""
            if loc:
                regions.add(loc.strip())
        self.send_json(200, {"regions": sorted(regions), "count": len(regions)})

    @require_auth()
    def serve_admin(self, path: str):
        if self.auth_user.get("username") != "admin":
            self.send_json(403, {"error": "Acesso restrito ao admin"})
            return None
        if path == "/api/admin/users":
            users = load_users()
            safe = [{k: v for k, v in u.items() if k != "password_hash"} for u in users]
            return self.send_json(200, {"users": safe, "count": len(safe)})
        if path == "/api/admin/stats":
            users = load_users()
            active = sum(1 for u in users if u.get("is_active"))
            suspended = sum(1 for u in users if u.get("is_suspended"))
            plan_counts = defaultdict(int)
            for u in users:
                plan_counts[u.get("plan", "free")] += 1
            mrr = sum(PLANS.get(u.get("plan", "free"), {}).get("price", 0) for u in users if u.get("is_active") and not u.get("is_suspended"))
            self.send_json(200, {
                "total_users": len(users),
                "active_users": active,
                "suspended": suspended,
                "mrr": mrr,
                "plans": dict(plan_counts),
            })
        self.send_json(404, {"error": "Admin route not found"})

    @require_auth()
    def handle_admin(self, path: str):
        if self.auth_user.get("username") != "admin":
            self.send_json(403, {"error": "Acesso restrito ao admin"})
            return None
        if path == "/api/admin/stripe-sync":
            sync_stripe_products()
            return self.send_json(200, {"message": "Produtos sincronizados com Stripe"})
        if path == "/api/admin/migrate":
            if not NEON_AVAILABLE:
                return self.send_json(400, {"error": "Neon nao esta disponivel. Defina DATABASE_URL"})
            leads = load_leads()
            proposals = load_proposals()
            result = neon_migrate(leads, proposals)
            return self.send_json(200, {**result, "message": "Migracao concluida"})
        try:
            body = self._read_json_body()
        except ValueError as e:
            self._handle_body_error(e)
            return
        if path == "/api/admin/block":
            username = body.get("username", "")
            users = load_users()
            for u in users:
                if u["username"] == username:
                    u["is_active"] = False
                    u["is_suspended"] = True
                    save_users(users)
                    return self.send_json(200, {"message": f"Usuario {username} bloqueado"})
            return self.send_json(404, {"error": "Usuario nao encontrado"})
        if path == "/api/admin/activate":
            username = body.get("username", "")
            plan_key = body.get("plan", "")
            users = load_users()
            for u in users:
                if u["username"] == username:
                    u["is_active"] = True
                    u["is_suspended"] = False
                    if plan_key and plan_key in PLANS:
                        u["plan"] = plan_key
                    save_users(users)
                    return self.send_json(200, {"message": f"Usuario {username} ativado"})
            return self.send_json(404, {"error": "Usuario nao encontrado"})
        if path == "/api/admin/delete":
            username = body.get("username", "")
            users = load_users()
            users = [u for u in users if u["username"] != username]
            save_users(users)
            return self.send_json(200, {"message": f"Usuario {username} removido"})
        self.send_json(404, {"error": "Admin route not found"})

    @require_auth()
    def serve_affiliate_stats(self):
        affiliates = load_json_file(AFFILIATES_FILE)
        username = self.auth_user.get("username", "")
        my_refs = [a for a in affiliates if a.get("affiliate_username") == username]
        self.send_json(200, {
            "total_referrals": len(my_refs),
            "active_referrals": sum(1 for r in my_refs if r.get("status") == "active"),
            "earnings": sum(r.get("commission", 0) for r in my_refs),
            "affiliate_code": username,
        })

    @require_auth()
    def serve_affiliates(self):
        if self.auth_user.get("username") != "admin":
            self.send_json(403, {"error": "Admin only"})
            return
        affiliates = load_json_file(AFFILIATES_FILE)
        self.send_json(200, {"affiliates": affiliates})

    def _handle_body_error(self, e: ValueError):
        msg = str(e)
        if msg.startswith("413:"):
            self.send_json(413, {"error": msg[4:]})
        elif msg.startswith("400:"):
            self.send_json(400, {"error": msg[4:]})
        else:
            self.send_json(500, {"error": "Erro interno"})

    def handle_login(self):
        client_ip = self.client_address[0]
        allowed, retry_after = security.check_login_rate_limit(client_ip)
        if not allowed:
            self.send_json(429, {"error": f"Muitas tentativas. Tente novamente em {retry_after}s."})
            return
        try:
            body = self._read_json_body(skip_auth=True)
        except ValueError as e:
            self._handle_body_error(e)
            return
        try:
            username = body.get("username", "").strip()
            password = body.get("password", "").strip()
            if not username or not password:
                self.send_json(400, {"error": "Usuário e senha obrigatórios"})
                return
            user = find_user(username)
            if not user:
                security.record_login_failure(client_ip)
                self.send_json(401, {"error": "Usuário ou senha inválidos"})
                return
            if not verify_password(password, user.get("password_hash", "")):
                security.record_login_failure(client_ip)
                self.send_json(401, {"error": "Usuário ou senha inválidos"})
                return
            if not user.get("is_active", False):
                self.send_json(403, {"error": "Acesso desativado. Entre em contato com o suporte."})
                return
            if user.get("is_suspended", False):
                self.send_json(403, {"error": "Plano suspenso. Regularize seu pagamento."})
                return
            parent = get_parent_user(user)
            if parent and parent.get("is_suspended", False):
                self.send_json(403, {"error": "Plano do titular suspenso. Regularize o pagamento."})
                return
            plan = get_plan(user.get("plan", "free"))
            security.reset_login_attempts(client_ip)
            token = create_jwt(user)
            self.send_json(200, {
                "token": token,
                "user": {
                    "username": user["username"],
                    "name": user.get("name", ""),
                    "plan": user.get("plan", "free"),
                    "tenant_id": get_tenant_id(user),
                },
                "plan": {
                    "name": plan["name"] if plan else "Free",
                    "price": plan["price"] if plan else 0,
                    "leads_limit": plan["leads_limit"] if plan else 0,
                    "users_limit": plan["users_limit"] if plan else 1,
                    "white_label": plan["white_label"] if plan else False,
                }
            })
        except Exception as e:
            self.send_json(500, {"error": "Erro interno"})

    def handle_register(self):
        client_ip = self.client_address[0]
        allowed, retry_after = security.check_login_rate_limit(client_ip)
        if not allowed:
            self.send_json(429, {"error": f"Muitas tentativas. Tente novamente em {retry_after}s."})
            return
        try:
            body = self._read_json_body(skip_auth=True)
        except ValueError as e:
            self._handle_body_error(e)
            return
        try:
            username = body.get("username", "").strip()
            password = body.get("password", "").strip()
            email = body.get("email", "").strip()
            plan_key = body.get("plan", "free")
            invite_code = body.get("invite_code", "").strip()
            if not username or not password:
                self.send_json(400, {"error": "Usuário e senha obrigatórios"})
                return
            if len(username) < 3:
                self.send_json(400, {"error": "Usuário deve ter no mínimo 3 caracteres"})
                return
            pw_error = validate_password_strength(password)
            if pw_error:
                self.send_json(400, {"error": pw_error})
                return
            if plan_key not in PLANS:
                self.send_json(400, {"error": "Plano inválido"})
                return
            plan = PLANS[plan_key]
            existing = find_user(username)
            if existing:
                self.send_json(409, {"error": "Usuário já existe"})
                return
            users = load_users()
            parent_id = ""
            tenant_id = ""
            is_active = False
            if invite_code:
                parent = find_user(invite_code)
                if not parent:
                    self.send_json(400, {"error": "Código de convite inválido"})
                    return
                parent_tenant = get_tenant_id(parent)
                if not check_plan_limit(parent_tenant, "users", 1):
                    self.send_json(403, {"error": "Limite de usuários do plano atingido"})
                    return
                parent_id = parent["id"]
                tenant_id = parent_tenant
                is_active = parent.get("is_active", False)
            if plan_key == "founder_lifetime":
                slots_data = json.loads(FOUNDER_SLOTS_FILE.read_text(encoding="utf-8"))
                if slots_data["used"] >= slots_data["total"]:
                    self.send_json(403, {"error": "Todas as vagas Founder Vitalício esgotadas"})
                    return
            if plan_key != "free" and not invite_code:
                is_active = False
            new_user = {
                "id": f"user_{secrets.token_hex(8)}",
                "username": username,
                "password_hash": hash_password(password),
                "email": email,
                "name": username,
                "plan": plan_key,
                "tenant_id": tenant_id or None,
                "parent_id": parent_id or None,
                "is_active": is_active,
                "is_suspended": False,
                "stripe_customer_id": "",
                "created_at": datetime.now().isoformat()
            }
            users.append(new_user)
            save_users(users)
            msg = "Cadastro realizado. Aguarde ativação do plano."
            if plan_key == "free":
                msg = "Conta gratuita criada. Faça login para começar."
                new_user["is_active"] = True
            users[-1] = new_user
            save_users(users)
            self.send_json(201, {"message": msg, "user_id": new_user["id"]})
        except Exception as e:
            self.send_json(500, {"error": "Erro interno"})

    @require_auth()
    def handle_invite(self):
        try:
            body = self._read_json_body()
        except ValueError as e:
            self._handle_body_error(e)
            return
        try:
            tenant_id = self.auth_user.get("tenant_id") or self.auth_user["sub"]
            users = load_users()
            parent = next((u for u in users if u["id"] == tenant_id), None)
            if not parent:
                self.send_json(400, {"error": "Titular não encontrado"})
                return
            plan = get_plan(parent.get("plan", "free"))
            if not plan:
                self.send_json(400, {"error": "Plano inválido"})
                return
            dependents = [u for u in users if u.get("parent_id") == tenant_id]
            if len(dependents) >= plan["users_limit"] - 1:
                self.send_json(403, {"error": "Limite de usuários do plano atingido"})
                return
            invite_token = secrets.token_urlsafe(16)
            invite_link = f"/register?invite={parent['username']}&token={invite_token}"
            invites = load_json_file(INVITES_FILE)
            invites.append({
                "token": invite_token,
                "tenant_id": tenant_id,
                "parent_username": parent["username"],
                "created_at": datetime.now().isoformat(),
                "used": False
            })
            save_json_file(INVITES_FILE, invites)
            self.send_json(200, {"invite_link": invite_link, "invite_code": parent["username"]})
        except Exception as e:
            self.send_json(500, {"error": "Erro interno"})

    def handle_csp_report(self):
        try:
            body = self._read_json_body(skip_auth=True)
            if body and isinstance(body, dict):
                print(f"[CSP-REPORT] {json.dumps(body, ensure_ascii=False)[:500]}")
        except Exception:
            pass
        self.send_response(204)
        origin = self.headers.get("Origin", "")
        for k, v in security.get_cors_headers(origin).items():
            self.send_header(k, v)
        self.end_headers()

    @require_auth()
    def handle_create_checkout(self):
        try:
            body = self._read_json_body()
        except ValueError as e:
            self._handle_body_error(e)
            return
        try:
            plan_key = body.get("plan", "pro")
            if plan_key not in PLANS or plan_key == "free":
                self.send_json(400, {"error": "Plano inválido"})
                return
            username = self.auth_user.get("username", "")
            origin = self.headers.get("Origin", "http://localhost:8765")
            success_url = f"{origin}/dashboard?checkout=success"
            cancel_url = f"{origin}/dashboard?checkout=cancel"
            checkout_url = create_stripe_checkout(plan_key, username, success_url, cancel_url)
            if not checkout_url:
                self.send_json(503, {"error": "Stripe não configurado. Contate o administrador."})
                return
            self.send_json(200, {"url": checkout_url})
        except Exception as e:
            self.send_json(500, {"error": "Erro ao criar checkout"})

    @require_auth()
    def handle_create_portal(self):
        try:
            username = self.auth_user.get("username", "")
            user = find_user(username)
            if not user or not user.get("stripe_customer_id"):
                self.send_json(400, {"error": "Nenhuma assinatura ativa"})
                return
            origin = self.headers.get("Origin", "http://localhost:8765")
            portal_url = create_stripe_portal(user["stripe_customer_id"], f"{origin}/dashboard")
            if not portal_url:
                self.send_json(503, {"error": "Stripe não configurado"})
                return
            self.send_json(200, {"url": portal_url})
        except Exception as e:
            self.send_json(500, {"error": "Erro ao criar portal"})

    @require_auth(scopes=["write"])
    def handle_save_leads(self):
        try:
            try:
                data = self._read_json_body()
            except ValueError as e:
                self._handle_body_error(e)
                return
            batch = data.get("leads", [])
            if not batch:
                self.send_json(400, {"error": "leads vazio"})
                return
            tenant_id = self.auth_user.get("tenant_id") or self.auth_user["sub"]
            existing = load_shared_data("leads")
            tenant_leads = [l for l in existing if l.get("tenant_id") == tenant_id]
            if not check_plan_limit(tenant_id, "leads", len(batch)):
                plan = get_plan(self.auth_user.get("plan", "free"))
                limit = plan["leads_limit"] if plan else 0
                self.send_json(403, {"error": f"Limite de leads atingido ({limit}). Faça upgrade do plano."})
                return
            existing_ids = {l.get("id") or l.get("osm_id") for l in existing}
            new_saved = 0
            for lead in batch:
                lead_id = lead.get("id") or lead.get("osm_id")
                if not lead_id:
                    lead_id = f"lead_{secrets.token_hex(8)}"
                    lead["id"] = lead_id
                if lead_id in existing_ids:
                    continue
                lead["tenant_id"] = tenant_id
                existing.append(lead)
                existing_ids.add(lead_id)
                new_saved += 1
            save_shared_data("leads", existing)
            self.send_json(200, {"saved": new_saved, "total": len(existing)})
        except Exception:
            self.send_json(500, {"error": "Internal server error"})

    @require_auth(scopes=["write"])
    def handle_update_lead_status(self):
        try:
            data = self._read_json_body()
        except ValueError as e:
            self._handle_body_error(e)
            return
        try:
            lead_id = data.get("id", "")
            new_status = data.get("status", "")
            if not lead_id or not new_status:
                self.send_json(400, {"error": "id e status obrigatorios"})
                return
            valid = ("novo", "contatado", "negociacao", "fechado", "perdido")
            if new_status not in valid:
                self.send_json(400, {"error": f"Status invalido: {new_status}"})
                return
            ok = update_lead_status_wrapper(lead_id, new_status)
            if ok:
                self.send_json(200, {"message": "Status atualizado", "status": new_status})
            else:
                self.send_json(404, {"error": "Lead nao encontrado"})
        except Exception:
            self.send_json(500, {"error": "Erro interno"})

    @require_auth(scopes=["write"])
    def handle_update_lead_email_status(self):
        try:
            data = self._read_json_body()
        except ValueError as e:
            self._handle_body_error(e)
            return
        try:
            lead_id = data.get("id", "")
            email_status = data.get("emailStatus", "")
            if not lead_id or not email_status:
                self.send_json(400, {"error": "id e emailStatus obrigatorios"})
                return
            valid = ("nao_enviado", "enviado", "aberto", "respondido")
            if email_status not in valid:
                self.send_json(400, {"error": f"Status invalido: {email_status}"})
                return
            leads = load_leads()
            updated = False
            for lead in leads:
                lid = lead.get("id") or lead.get("osm_id")
                if lid == lead_id:
                    lead["emailStatus"] = email_status
                    updated = True
                    break
            if updated:
                save_leads(leads)
                self.send_json(200, {"message": "Email status atualizado", "emailStatus": email_status})
            else:
                self.send_json(404, {"error": "Lead nao encontrado"})
        except Exception:
            self.send_json(500, {"error": "Erro interno"})

    @require_auth(scopes=["write"])
    def handle_save_proposals(self):
        try:
            try:
                data = self._read_json_body()
            except ValueError as e:
                self._handle_body_error(e)
                return
            batch = data.get("proposals", [])
            if not batch:
                self.send_json(400, {"error": "proposals vazio"})
                return
            existing = load_shared_data("proposals")
            existing_ids = {p.get("id") for p in existing}
            new_saved = 0
            for prop in batch:
                prop_id = prop.get("id")
                if not prop_id or prop_id in existing_ids:
                    continue
                existing.append(prop)
                existing_ids.add(prop_id)
                new_saved += 1
            save_shared_data("proposals", existing)
            self.send_json(200, {"saved": new_saved, "total": len(existing)})
        except Exception:
            self.send_json(500, {"error": "Internal server error"})

    @require_auth()
    def handle_extract(self):
        client_ip = self.client_address[0]
        if not security.check_rate_limit(client_ip):
            self.send_json(429, {"error": "Rate limit exceeded"})
            return
        try:
            try:
                data = self._read_json_body()
            except ValueError as e:
                self._handle_body_error(e)
                return
            location = data.get("location", "").strip()
            category = data.get("category", "").strip()
            limit = int(data.get("limit", 20))
            radius = int(data.get("radius", 5000))
            only_phone = data.get("only_with_phone", True)
            if not location or not category:
                self.send_json(400, {"error": "location e category obrigatorios"})
                return
            pipeline_script = SKILL_DIR.parent / "scripts" / "prospecting" / "pipeline_unified.py"
            if not pipeline_script.exists():
                self.send_json(500, {"error": "Script pipeline nao encontrado"})
                return
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_loc = location.replace(",", "").replace(" ", "_").lower()
            output_dir = SKILL_DIR.parent / "pipeline_output"
            output_dir.mkdir(parents=True, exist_ok=True)
            commands = [
                sys.executable, str(pipeline_script),
                "--source", "osm",
                "--location", location,
                "--category", category,
                "--limit", str(limit),
                "--radius", str(radius),
                "--output_dir", str(output_dir),
            ]
            if only_phone:
                commands.append("--only_with_phone")
            result = __import__('subprocess').run(
                commands, capture_output=True, text=True, timeout=300
            )
            if result.returncode != 0:
                self.send_json(500, {"error": f"Pipeline falhou: {result.stderr[:500]}"})
                return
            leads_count = 0
            proposals_count = 0
            for f in output_dir.glob(f"leads_{safe_loc}_{timestamp}*.json"):
                try:
                    leads_count = len(json.loads(f.read_text(encoding="utf-8")))
                except: pass
            for f in output_dir.glob(f"propostas_{safe_loc}_{timestamp}*.txt"):
                proposals_count = len(f.read_text(encoding="utf-8").split("=== LEAD"))
            leads_file = output_dir / f"leads_{safe_loc}_{timestamp}.json"
            if leads_file.exists():
                new_leads = json.loads(leads_file.read_text(encoding="utf-8"))
                existing = load_shared_data("leads")
                existing_ids = {l.get("id") or l.get("osm_id") for l in existing}
                synced = 0
                tenant_id = self.auth_user.get("tenant_id") or self.auth_user["sub"]
                for lead in new_leads:
                    lid = lead.get("id") or lead.get("osm_id")
                    if lid and lid not in existing_ids:
                        lead["tenant_id"] = tenant_id
                        existing.append(lead)
                        existing_ids.add(lid)
                        synced += 1
                if synced:
                    save_shared_data("leads", existing)
            self.send_json(200, {
                "leads_count": leads_count,
                "proposals_count": proposals_count,
                "output_dir": str(output_dir),
                "location": location,
                "category": category,
            })
        except __import__('subprocess').TimeoutExpired:
            self.send_json(408, {"error": "Pipeline excedeu tempo limite (5 min)"})
        except Exception as e:
            self.send_json(500, {"error": f"Erro na extracao: {str(e)[:200]}"})

    def handle_stripe_webhook(self):
        client_ip = self.client_address[0]
        if not security.check_rate_limit(client_ip):
            self.send_json(200, {"received": True})
            return
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self.send_json(200, {"received": True})
                return
            raw_body = self.rfile.read(content_length)
            if not raw_body:
                self.send_json(200, {"received": True})
                return
            if STRIPE_AVAILABLE and settings.STRIPE_WEBHOOK_SECRET:
                sig_header = self.headers.get("Stripe-Signature", "")
                try:
                    stripe.Webhook.construct_event(raw_body, sig_header, settings.STRIPE_WEBHOOK_SECRET)
                except Exception:
                    self.send_json(400, {"error": "Invalid signature"})
                    return
            body = json.loads(raw_body)
            event_type = body.get("type", "")
            data = body.get("data", {}).get("object", {})
            username = data.get("client_reference_id", "")
            if not username:
                self.send_json(200, {"received": True})
                return
            users = load_users()
            user = next((u for u in users if u["username"] == username), None)
            if not user:
                self.send_json(200, {"received": True})
                return
            if event_type == "checkout.session.completed":
                customer_id = data.get("customer", "")
                metadata = data.get("metadata", {})
                plan_key = metadata.get("plan", "pro")
                user["is_active"] = True
                user["is_suspended"] = False
                user["stripe_customer_id"] = customer_id
                user["plan"] = plan_key
                user["tenant_id"] = user.get("tenant_id") or user["id"]
                if plan_key == "founder_lifetime":
                    slots = json.loads(FOUNDER_SLOTS_FILE.read_text(encoding="utf-8"))
                    slots["used"] = slots.get("used", 0) + 1
                    FOUNDER_SLOTS_FILE.write_text(json.dumps(slots, indent=2), encoding="utf-8")
                save_users(users)
            elif event_type == "invoice.payment_failed":
                user["is_suspended"] = True
                user["is_active"] = False
                save_users(users)
            elif event_type == "invoice.payment_succeeded":
                user["is_suspended"] = False
                user["is_active"] = True
                save_users(users)
            self.send_json(200, {"received": True})
        except Exception:
            self.send_json(200, {"received": True})

    def _read_json_body(self, skip_auth=False) -> Dict:
        content_length = int(self.headers.get("Content-Length", 0))
        max_len = settings.MAX_CONTENT_LENGTH
        if content_length > max_len:
            raise ValueError("413:Payload too large")
        if not skip_auth and content_length <= 0:
            raise ValueError("400:Empty body")
        if content_length <= 0:
            return {}
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            raise ValueError("400:Invalid JSON") from e
        if not isinstance(payload, dict):
            raise ValueError("400:Invalid payload")
        return payload

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
        parts = msg.split()
        sanitized_parts = []
        skip_next = False
        for part in parts:
            if skip_next:
                skip_next = False
                continue
            if part in ("Bearer", "X-API-Key"):
                sanitized_parts.append(part)
                skip_next = True
            else:
                sanitized_parts.append(part)
        sanitized = " ".join(sanitized_parts)
        if any(x in sanitized for x in ["401", "403", "404", "413", "429", "500", "..", "etc/passwd"]):
            print(f"[SECURITY] {self.client_address[0]} - {sanitized}")
        else:
            print(f"[ACCESS] {self.client_address[0]} - {sanitized}")

def main():
    port = int(os.getenv("PORT", "8765"))
    print(f"\n{'='*50}")
    print(f"🚀 SaleStack Dashboard (JWT Auth)")
    print(f"{'='*50}")
    print(f"   Login:     http://0.0.0.0:{port}/login")
    print(f"   Dashboard: http://0.0.0.0:{port}/dashboard")
    print(f"   API:       http://0.0.0.0:{port}/api")
    print(f"   Database:  {'Neon PostgreSQL' if NEON_AVAILABLE else 'JSON files'}")
    print(f"   Shared:    {SHARED_DATA_DIR}")
    print(f"   Users:     {USERS_FILE}")
    print(f"{'='*50}\n")
    server = HTTPServer(('0.0.0.0', port), SalesHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Servidor parado")
        server.shutdown()

if __name__ == '__main__':
    main()
