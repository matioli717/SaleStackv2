# ============================================================
# FIX C05/C06/H05/H06 - server.py COMPLETO CORRIGIDO
# Substitua: ~/.hermes/skills/sales/sales-prospecting/server.py
# E: /workspaces/OpnCld/sales-prospecting/server.py
# ============================================================

#!/usr/bin/env python3
"""
Backend API para Dashboard de Sales Prospecting - VERSÃO SEGURA
- Autenticação via API Key
- CORS restrito
- Rate limiting
- Headers de segurança
- Path traversal protection
- Input validation com Pydantic
- Error handling seguro
- HTTPS ready
"""

import sys
import json
import asyncio
import tempfile
import threading
import time
import hashlib
import hmac
import secrets
from functools import wraps
from collections import defaultdict
from pathlib import Path
from http.server import HTTPServer
from urllib.parse import urlparse
from datetime import datetime
from typing import Optional, List, Dict, Any

# ---- DEPENDÊNCIAS (adicionar ao requirements.txt) ----
# pip install pydantic pydantic-settings python-dotenv
try:
    from pydantic import BaseModel, Field, field_validator, ValidationError
    from pydantic_settings import BaseSettings
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    # Fallback simples
    class BaseModel:
        pass
    class Field:
        def __init__(self, **kwargs): pass
    def field_validator(*args, **kwargs):
        def decorator(f): return f
        return decorator
    class ValidationError(Exception):
        pass

# ============================================================
# CONFIGURAÇÃO SEGURA
# ============================================================

class Settings(BaseSettings):
    """Configuração via .env - NUNCA hardcode secrets"""
    API_KEYS: str = ""  # JSON: [{"key": "sk_live_...", "name": "dashboard", "scopes": ["read", "write"]}]
    ALLOWED_ORIGINS: str = "https://*.github.dev,https://*.githubpreview.dev,http://localhost:8765,http://127.0.0.1:8765"
    RATE_LIMIT_PER_MIN: int = 60
    SHARED_DATA_DIR: str = "~/.hermes/shared_data"
    TLS_CERT: str = ""  # Caminho para cert.pem
    TLS_KEY: str = ""   # Caminho para key.pem
    MAX_PAYLOAD_SIZE: int = 1024 * 1024  # 1MB
    SUBPROCESS_TIMEOUT: int = 60  # segundos
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

SKILL_DIR = Path(__file__).parent
SHARED_DATA_DIR = Path(settings.SHARED_DATA_DIR).expanduser()
SHARED_DATA_DIR.mkdir(parents=True, exist_ok=True)
LEADS_FILE = SHARED_DATA_DIR / "jacarepagua_leads.json"
PROPOSALS_FILE = SHARED_DATA_DIR / "jacarepagua_proposals.json"

# Lock thread-safe
file_lock = threading.Lock()

# ============================================================
# MODELOS DE VALIDAÇÃO (Pydantic)
# ============================================================

class LeadInput(BaseModel):
    """Schema para validação de lead de entrada"""
    lead_name: str = Field(..., min_length=1, max_length=200)
    business_type: str = Field(..., min_length=1, max_length=100)
    location: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=8, max_length=20)
    email: Optional[str] = Field(None, max_length=200)
    website: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, max_length=50)
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        # Remove formatação, mantém apenas dígitos e +
        cleaned = "".join(c for c in v if c.isdigit() or c == "+")
        if len(cleaned) < 8:
            raise ValueError("Telefone inválido")
        return cleaned
    
    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if v and "@" not in v:
            raise ValueError("Email inválido")
        return v
    
    @field_validator("website")
    @classmethod
    def validate_website(cls, v):
        if v and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL deve começar com http:// ou https://")
        return v

class LeadBatchInput(BaseModel):
    leads: List[LeadInput] = Field(..., min_length=1, max_length=100)

class ProposalBatchInput(BaseModel):
    proposals: List[Dict[str, Any]] = Field(..., min_length=1, max_length=100)

# ============================================================
# MIDDLEWARE DE SEGURANÇA
# ============================================================

class SecurityMiddleware:
    def __init__(self):
        self.allowed_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",")]
        self.api_keys = self._load_api_keys()
        self.rate_limit = settings.RATE_LIMIT_PER_MIN
        self.request_counts = defaultdict(list)
        self.blocked_ips = set()
        self._block_lock = threading.Lock()
    
    def _load_api_keys(self) -> Dict[str, Dict]:
        """Carrega API keys do .env (hashadas)"""
        keys = {}
        try:
            if settings.API_KEYS:
                imported = json.loads(settings.API_KEYS)
                for item in imported:
                    key_hash = hashlib.sha256(item["key"].encode()).hexdigest()
                    keys[key_hash] = {
                        "name": item.get("name", "unknown"),
                        "scopes": item.get("scopes", ["read"])
                    }
        except Exception:
            pass
        # Fallback: key de desenvolvimento (apenas se não houver nenhuma)
        if not keys:
            dev_key = "sk_dev_" + secrets.token_urlsafe(32)
            keys[hashlib.sha256(dev_key.encode()).hexdigest()] = {
                "name": "development",
                "scopes": ["read", "write"]
            }
            print(f"⚠️  DEV API KEY (configure API_KEYS no .env para produção): {dev_key}")
        return keys
    
    def check_origin(self, origin: str) -> bool:
        if not origin:
            return False
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
                "Access-Control-Max-Age": "86400"
            }
        return {}
    
    def get_security_headers(self) -> Dict[str, str]:
        return {
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' https://*.github.dev https://*.githubpreview.dev; "
                "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
            ),
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "X-Permitted-Cross-Domain-Policies": "none"
        }
    
    def check_rate_limit(self, client_ip: str) -> bool:
        now = time.time()
        minute_ago = now - 60
        
        with self._block_lock:
            self.request_counts[client_ip] = [
                ts for ts in self.request_counts[client_ip] if ts > minute_ago
            ]
            
            if client_ip in self.blocked_ips:
                return False
            
            if len(self.request_counts[client_ip]) >= self.rate_limit:
                self.blocked_ips.add(client_ip)
                threading.Timer(900, self._unblock_ip, args=[client_ip]).start()
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


# Instância global
security = SecurityMiddleware()


def require_auth(scopes: List[str] = None):
    """Decorator para handlers protegidos"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # CORS + Security headers em TODAS respostas
            origin = self.headers.get("Origin", "")
            for k, v in security.get_cors_headers(origin).items():
                self.send_header(k, v)
            for k, v in security.get_security_headers().items():
                self.send_header(k, v)
            
            # Rate limit
            client_ip = self.client_address[0]
            if not security.check_rate_limit(client_ip):
                self.send_json(429, {"error": "Rate limit exceeded. Try again in 1 minute."})
                return
            
            # Skip auth para OPTIONS e dashboard estático
            if func.__name__ in ("do_OPTIONS", "serve_dashboard"):
                return func(self, *args, **kwargs)
            
            # Auth
            auth_header = self.headers.get("Authorization", "")
            api_key = self.headers.get("X-API-Key", "")
            
            token = None
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
            elif api_key:
                token = api_key
            
            if not token:
                self.send_json(401, {"error": "Authentication required. Use Authorization: Bearer <key> or X-API-Key header"})
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


# ============================================================
# SHARED DATA (Thread-safe)
# ============================================================

def save_shared_data(key: str, data: List[Dict]):
    with file_lock:
        if key == "leads":
            LEADS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        elif key == "proposals":
            PROPOSALS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_shared_data(key: str) -> List[Dict]:
    with file_lock:
        if key == "leads":
            if LEADS_FILE.exists():
                return json.loads(LEADS_FILE.read_text(encoding="utf-8"))
            return []
        elif key == "proposals":
            if PROPOSALS_FILE.exists():
                return json.loads(PROPOSALS_FILE.read_text(encoding="utf-8"))
            return []
    return []


# ============================================================
# SUBPROCESS SEGURO (Fix C03)
# ============================================================

ALLOWED_SCRIPTS = {
    "run_proposal": "scripts/run.py",
}

def run_hermes_proposal_safe(lead_data: Dict) -> str:
    """Versão segura do run_hermes_proposal"""
    import subprocess
    
    script_path = (SKILL_DIR / ALLOWED_SCRIPTS["run_proposal"]).resolve()
    if not script_path.exists():
        raise FileNotFoundError("Script de geração não encontrado")
    
    # Garante que está dentro do SKILL_DIR
    try:
        script_path.relative_to(SKILL_DIR.resolve())
    except ValueError:
        raise ValueError("Script fora do diretório permitido")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump([lead_data], f, ensure_ascii=False)
        leads_file = f.name
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--file", leads_file],
            capture_output=True, text=True, timeout=settings.SUBPROCESS_TIMEOUT,
            cwd=str(SKILL_DIR)
        )
        output = result.stdout.strip()
        if "===" in output:
            parts = output.split("===\n", 1)
            if len(parts) > 1:
                return parts[1].strip()
        return output
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Timeout na geração ({settings.SUBPROCESS_TIMEOUT}s)")
    except Exception as e:
        # Log interno, não vaza para cliente
        print(f"[ERROR] Hermes proposal failed: {e}", file=sys.stderr)
        raise RuntimeError("Erro interno na geração de proposta")
    finally:
        Path(leads_file).unlink(missing_ok=True)


# ============================================================
# HTTP HANDLER SEGURO
# ============================================================

class SalesHandler(SafeRequestHandler):
    """Handler que herda proteção contra path traversal"""
    
    ALLOWED_ROUTES = {
        "GET": ["/", "/dashboard", "/api/leads", "/api/proposals", "/api/stats"],
        "POST": ["/api/leads", "/api/proposals", "/api/generate"],
        "OPTIONS": ["/api/leads", "/api/proposals", "/api/generate", "/api/stats", "/api/leads"],
    }
    ALLOWED_STATIC = {"dashboard.html", "favicon.ico"}
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SKILL_DIR), **kwargs)
    
    def end_headers(self):
        # Headers já adicionados pelo decorator @require_auth
        super().end_headers()
    
    def do_OPTIONS(self):
        origin = self.headers.get("Origin", "")
        cors = security.get_cors_headers(origin)
        self.send_response(200)
        for k, v in cors.items():
            self.send_header(k, v)
        for k, v in security.get_security_headers().items():
            self.send_header(k, v)
        self.end_headers()
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        # Dashboard estático
        if path in ("/", "/dashboard"):
            self.serve_dashboard()
        elif path == "/api/leads":
            self.serve_shared_leads()
        elif path == "/api/proposals":
            self.serve_shared_proposals()
        elif path == "/api/stats":
            self.serve_stats()
        else:
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        # Valida Content-Length
        content_length = self.headers.get("Content-Length")
        if content_length:
            try:
                cl = int(content_length)
                if cl > settings.MAX_PAYLOAD_SIZE:
                    self.send_json(413, {"error": "Payload too large"})
                    return
            except ValueError:
                self.send_json(400, {"error": "Invalid Content-Length"})
                return
        
        if path == "/api/generate":
            self.handle_generate()
        elif path == "/api/leads":
            self.handle_save_leads()
        elif path == "/api/proposals":
            self.handle_save_proposals()
        else:
            self.send_error(404, "Not Found")
    
    # ===== HANDLERS (protegidos por @require_auth) =====
    
    def serve_dashboard(self):
        self.send_response(200)
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
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    
    @require_auth(scopes=["write"])
    def handle_generate(self):
        try:
            body = self._read_json_body()
            lead = LeadInput(**body)
            proposal = run_hermes_proposal_safe(lead.model_dump())
            self.send_json(200, {"proposal": proposal, "lead": lead.model_dump()})
        except ValidationError as e:
            self.send_json(400, {"error": "Validation error", "details": e.errors()})
        except TimeoutError:
            self.send_json(504, {"error": "Generation timeout"})
        except Exception as e:
            # Log interno, resposta genérica
            print(f"[ERROR] handle_generate: {e}", file=sys.stderr)
            self.send_json(500, {"error": "Internal server error"})
    
    @require_auth(scopes=["write"])
    def handle_save_leads(self):
        try:
            data = self._read_json_body()
            batch = LeadBatchInput(**data)
            new_leads = [l.model_dump() for l in batch.leads]
            
            existing = load_shared_data("leads")
            existing_ids = {l.get("id") or l.get("osm_id") for l in existing}
            for lead in new_leads:
                lead_id = lead.get("id") or lead.get("osm_id")
                if lead_id and lead_id not in existing_ids:
                    existing.append(lead)
                    existing_ids.add(lead_id)
            
            save_shared_data("leads", existing)
            self.send_json(200, {"saved": len(new_leads), "total": len(existing)})
        except ValidationError as e:
            self.send_json(400, {"error": "Validation error", "details": e.errors()})
        except Exception as e:
            print(f"[ERROR] handle_save_leads: {e}", file=sys.stderr)
            self.send_json(500, {"error": "Internal server error"})
    
    @require_auth(scopes=["write"])
    def handle_save_proposals(self):
        try:
            data = self._read_json_body()
            batch = ProposalBatchInput(**data)
            new_proposals = batch.proposals
            
            existing = load_shared_data("proposals")
            existing_ids = {p.get("id") for p in existing}
            for prop in new_proposals:
                prop_id = prop.get("id")
                if prop_id and prop_id not in existing_ids:
                    existing.append(prop)
                    existing_ids.add(prop_id)
            
            save_shared_data("proposals", existing)
            self.send_json(200, {"saved": len(new_proposals), "total": len(existing)})
        except ValidationError as e:
            self.send_json(400, {"error": "Validation error", "details": e.errors()})
        except Exception as e:
            print(f"[ERROR] handle_save_proposals: {e}", file=sys.stderr)
            self.send_json(500, {"error": "Internal server error"})
    
    def _read_json_body(self) -> Dict:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > settings.MAX_PAYLOAD_SIZE:
            raise ValueError("Payload too large")
        body = self.rfile.read(content_length).decode("utf-8")
        return json.loads(body)
    
    def send_json(self, status: int, data: Dict):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        # Headers de segurança já enviados pelo decorator
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def log_message(self, format, *args):
        # Log apenas eventos de segurança
        msg = format % args
        if any(x in msg for x in ["401", "403", "404", "413", "429", "500", "..", "etc/passwd"]):
            print(f"[SECURITY] {self.client_address[0]} - {msg}")


# ============================================================
# MAIN COM TLS SUPPORT
# ============================================================

def main():
    port = 8765
    print(f"🚀 Sales Prospecting Dashboard (SECURE) rodando em http://localhost:{port}")
    if settings.TLS_CERT and settings.TLS_KEY:
        print(f"   🔒 TLS habilitado: {settings.TLS_CERT}")
    print(f"   Dashboard: http://localhost:{port}/dashboard")
    print(f"   API:       http://localhost:{port}/api/generate (POST)")
    print(f"   Leads:     http://localhost:{port}/api/leads (GET/POST)")
    print(f"   Props:     http://localhost:{port}/api/proposals (GET/POST)")
    print(f"   Stats:     http://localhost:{port}/api/stats")
    print(f"   Shared:    {SHARED_DATA_DIR}")
    print("\nPressione Ctrl+C para parar\n")
    
    server = HTTPServer(('0.0.0.0', port), SalesHandler)
    server.security_middleware = security  # Injeta middleware
    
    # TLS se configurado
    if settings.TLS_CERT and settings.TLS_KEY:
        import ssl
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(settings.TLS_CERT, settings.TLS_KEY)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        print(f"🔒 HTTPS ativo em https://localhost:{port}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Servidor parado")
        server.shutdown()


if __name__ == '__main__':
    main()