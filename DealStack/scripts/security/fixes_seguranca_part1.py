#!/usr/bin/env python3
"""
🔧 FIXES DE SEGURANÇA - DealStack
Código corrigido para cada vulnerabilidade do relatório_seguranca.md

USO:
1. Copie cada classe/função para o arquivo correspondente
2. Substitua a implementação original
3. Teste localmente antes de commitar

ORDEM DE APLICAÇÃO (prioridade):
1. server.py - Auth, CORS, Headers, Path Traversal, Rate Limit
2. dashboard.html - CSP, Input Validation, localStorage -> sessionStorage
3. generate_content.py - Template Injection fix
4. add_prospect.py - CSV Injection fix
5. shopify_ops.py / meta_*.py - Token validation, API version
"""

# ============================================================
# FIX C01/C02/C06/H05/H06 - server.py: Auth + CORS + Headers + Rate Limit
# ============================================================

import hashlib
import hmac
import time
import secrets
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta

class SecurityMiddleware:
    """Middleware de segurança para HTTPServer"""
    
    def __init__(self, allowed_origins=None, api_keys=None, rate_limit=60):
        self.allowed_origins = allowed_origins or [
            "https://*.github.dev",
            "https://*.githubpreview.dev",
            "http://localhost:8765",
            "http://127.0.0.1:8765"
        ]
        self.api_keys = api_keys or {}  # {key_hash: {"name": "client", "scopes": ["read", "write"]}}
        self.rate_limit = rate_limit  # req/min por IP
        self.request_counts = defaultdict(list)
        self.blocked_ips = set()
        
    def check_origin(self, origin: str) -> bool:
        """Valida Origin contra lista permitida (suporta wildcards)"""
        if not origin:
            return False
        for allowed in self.allowed_origins:
            if allowed == "*":
                return True
            if allowed.startswith("*."):
                suffix = allowed[1:]  # .github.dev
                if origin.endswith(suffix):
                    return True
            if origin == allowed:
                return True
        return False
    
    def get_cors_headers(self, origin: str) -> dict:
        """Retorna headers CORS seguros"""
        if self.check_origin(origin):
            return {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key",
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Max-Age": "86400"
            }
        return {}
    
    def get_security_headers(self) -> dict:
        """Headers de segurança obrigatórios"""
        return {
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' https://*.github.dev https://*.githubpreview.dev; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            ),
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "X-Permitted-Cross-Domain-Policies": "none"
        }
    
    def check_rate_limit(self, client_ip: str) -> bool:
        """Rate limiting simples: max N req/min por IP"""
        now = time.time()
        minute_ago = now - 60
        
        # Limpa requests antigos
        self.request_counts[client_ip] = [
            ts for ts in self.request_counts[client_ip] if ts > minute_ago
        ]
        
        if client_ip in self.blocked_ips:
            return False
            
        if len(self.request_counts[client_ip]) >= self.rate_limit:
            self.blocked_ips.add(client_ip)
            # Auto-desbloqueia após 15 min
            import threading
            threading.Timer(900, self.blocked_ips.discard, args=[client_ip]).start()
            return False
            
        self.request_counts[client_ip].append(now)
        return True
    
    def hash_api_key(self, api_key: str) -> str:
        """Hash seguro para armazenar API keys"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    def verify_api_key(self, provided_key: str) -> dict | None:
        """Verifica API key via hash timing-safe"""
        if not provided_key:
            return None
        provided_hash = self.hash_api_key(provided_key)
        for stored_hash, info in self.api_keys.items():
            if hmac.compare_digest(provided_hash, stored_hash):
                return info
        return None


def require_auth(scopes=None):
    """
    Decorator para exigir autenticação em handlers.
    Uso:
        @require_auth(scopes=["read"])
        def handle_get(self): ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Pega middleware do server (injeta via compose)
            middleware = getattr(self.server, 'security_middleware', None)
            if not middleware:
                self.send_json(500, {"error": "Security middleware não configurado"})
                return
            
            # Rate limit
            client_ip = self.client_address[0]
            if not middleware.check_rate_limit(client_ip):
                self.send_json(429, {"error": "Rate limit exceeded. Tente novamente em 1 minuto."})
                return
            
            # CORS headers em todas as respostas
            origin = self.headers.get("Origin", "")
            cors_headers = middleware.get_cors_headers(origin)
            for k, v in cors_headers.items():
                self.send_header(k, v)
            
            # Headers de segurança
            for k, v in middleware.get_security_headers().items():
                self.send_header(k, v)
            
            # Auth para rotas protegidas
            if func.__name__ not in ("do_OPTIONS", "serve_dashboard", "serve_json"):
                auth_header = self.headers.get("Authorization", "")
                api_key = self.headers.get("X-API-Key", "")
                
                # Tenta Bearer token primeiro
                token = None
                if auth_header.startswith("Bearer "):
                    token = auth_header[7:]
                elif api_key:
                    token = api_key
                
                if not token:
                    self.send_json(401, {"error": "Authentication required. Use Authorization: Bearer <token> or X-API-Key header"})
                    return
                
                key_info = middleware.verify_api_key(token)
                if not key_info:
                    self.send_json(401, {"error": "Invalid API key"})
                    return
                
                if scopes:
                    if not any(s in key_info.get("scopes", []) for s in scopes):
                        self.send_json(403, {"error": f"Insufficient scopes. Required: {scopes}"})
                        return
                
                # Injeta info do cliente no handler
                self.auth_client = key_info
            
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


# ============================================================
# FIX C03 - Command Injection Protection
# ============================================================

import shlex
from pathlib import Path
from typing import List, Tuple

ALLOWED_SCRIPTS = {
    "run_proposal": "scripts/run.py",
    "extract_leads": "scripts/extract.py",
}

def safe_subprocess_run(
    script_name: str, 
    args: List[str], 
    cwd: Path, 
    timeout: int = 60,
    input_data: str = None
) -> Tuple[int, str, str]:
    """
    Executa subprocess de forma segura:
    - Valida script contra allowlist
    - Não usa shell=True
    - Sanitiza argumentos
    - Timeout configurável (default 60s)
    """
    if script_name not in ALLOWED_SCRIPTS:
        raise ValueError(f"Script não permitido: {script_name}")
    
    script_path = cwd / ALLOWED_SCRIPTS[script_name]
    if not script_path.exists():
        raise FileNotFoundError(f"Script não encontrado: {script_path}")
    
    # Resolve path real (previne symlink attacks)
    script_path = script_path.resolve()
    cwd = cwd.resolve()
    
    # Garante que script está dentro do cwd
    try:
        script_path.relative_to(cwd)
    except ValueError:
        raise ValueError("Script fora do diretório permitido")
    
    # Sanitiza args - apenas alphanumeric, dash, underscore, dot
    safe_args = []
    for arg in args:
        if not all(c.isalnum() or c in "-_./" for c in arg):
            raise ValueError(f"Argumento inválido: {arg}")
        safe_args.append(arg)
    
    cmd = [str(script_path)] + safe_args
    
    import subprocess
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd),
            input=input_data
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Processo excedeu timeout de {timeout}s")
    except Exception as e:
        raise RuntimeError(f"Erro ao executar subprocess: {e}")


# ============================================================
# FIX C04 - Path Traversal Protection (Custom Handler)
# ============================================================

from http.server import SimpleHTTPRequestHandler
from urllib.parse import urlparse, unquote
import os

class SafeRequestHandler(SimpleHTTPRequestHandler):
    """Handler que SÓ serve rotas explícitas - NUNCA fallback para filesystem"""
    
    # Rotas permitidas (exatas ou prefixos)
    ALLOWED_ROUTES = {
        "GET": ["/", "/dashboard", "/api/leads", "/api/proposals", "/api/stats", "/api/generate"],
        "POST": ["/api/leads", "/api/proposals", "/api/generate"],
        "OPTIONS": ["/api/leads", "/api/proposals", "/api/generate", "/api/stats"],
    }
    
    # Arquivos estáticos permitidos (nome exato)
    ALLOWED_STATIC = {
        "dashboard.html",
        "favicon.ico",
    }
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        # Rota explícita permitida
        if path in self.ALLOWED_ROUTES["GET"]:
            # Delegate para handler específico (implementar no filho)
            if hasattr(self, f"handle_{path.strip('/').replace('/', '_')}"):
                getattr(self, f"handle_{path.strip('/').replace('/', '_')}")()
            else:
                self.send_error(404, "Not Found")
            return
        
        # Arquivo estático permitido
        if path.lstrip("/") in self.ALLOWED_STATIC:
            super().do_GET()
            return
        
        # Tudo mais = 404 (NUNCA path traversal)
        self.send_error(404, "Not Found")
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path in self.ALLOWED_ROUTES["POST"]:
            handler_name = f"handle_{path.strip('/').replace('/', '_')}"
            if hasattr(self, handler_name):
                getattr(self, handler_name)()
            else:
                self.send_error(404, "Not Found")
            return
        
        self.send_error(404, "Not Found")
    
    def do_OPTIONS(self):
        # CORS preflight
        origin = self.headers.get("Origin", "")
        middleware = getattr(self.server, 'security_middleware', None)
        if middleware:
            cors = middleware.get_cors_headers(origin)
            self.send_response(200)
            for k, v in cors.items():
                self.send_header(k, v)
            self.end_headers()
        else:
            self.send_error(404)
    
    # Override para silenciar logs de erro mas logar segurança
    def log_message(self, format, *args):
        # Log apenas acessos suspeitos
        msg = format % args
        if any(x in msg for x in ["404", "403", "401", "429", "500", "..", "etc/passwd", "wp-admin", ".env"]):
            print(f"[SECURITY] {self.client_address[0]} - {msg}")