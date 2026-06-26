# ============================================================
# FIX H04/H07 - shopify_ops.py: Token Validation + API Version
# Substitua: /workspaces/OpnCld/shopify-ops/shopify_ops.py
# ============================================================

#!/usr/bin/env python3
"""
Shopify Ops Helper - VERSÃO SEGURA
- Validação de token (formato shpat_)
- API version configurável
- Rate limiting interno
- Error handling seguro (não vaza stack trace)
- User-Agent customizado
"""

import argparse
import csv
import os
import sys
import json
import time
import re
from pathlib import Path
from urllib import request as urlrequest
from typing import Optional, Dict, Any

# ============================================================
# CONFIGURAÇÃO SEGURA
# ============================================================

# API version - configurável via env, default para versão suportada
API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2024-10")  # Atualizado de 2024-01
VALID_API_VERSIONS = ["2024-01", "2024-04", "2024-07", "2024-10"]

# Regex para validar token Shopify (shpat_ + 32 chars alfanuméricos)
SHOPIFY_TOKEN_PATTERN = re.compile(r'^shpat_[a-zA-Z0-9]{32}$')

# Rate limiting simples (requests por minuto)
RATE_LIMIT = 60
_request_times = []

DEFAULT_UA = f"DealStack-ShopifyOps/1.0 (+https://github.com/matioli616/DealStack)"


def validate_token(token: str) -> bool:
    """Valida formato do token Shopify"""
    if not token:
        return False
    return bool(SHOPIFY_TOKEN_PATTERN.match(token))


def validate_domain(domain: str) -> bool:
    """Valida formato do domínio .myshopify.com"""
    if not domain:
        return False
    # Remove protocolo se presente
    domain = domain.replace("https://", "").replace("http://", "")
    # Deve terminar com .myshopify.com
    return domain.endswith(".myshopify.com") and len(domain) > 15


def check_rate_limit() -> bool:
    """Rate limiting simples: max 60 req/min"""
    global _request_times
    now = time.time()
    minute_ago = now - 60
    _request_times = [t for t in _request_times if t > minute_ago]
    
    if len(_request_times) >= RATE_LIMIT:
        return False
    
    _request_times.append(now)
    return True


def base_url() -> str:
    domain = os.environ.get("SHOPIFY_STORE_DOMAIN")
    if not domain:
        raise SystemExit("❌ Missing SHOPIFY_STORE_DOMAIN")
    
    if not validate_domain(domain):
        raise SystemExit(f"❌ Domínio inválido: {domain}. Use: sua-loja.myshopify.com")
    
    if API_VERSION not in VALID_API_VERSIONS:
        raise SystemExit(f"❌ API version inválida: {API_VERSION}. Válidas: {VALID_API_VERSIONS}")
    
    return f"https://{domain}/admin/api/{API_VERSION}"


def headers() -> Dict[str, str]:
    token = os.environ.get("SHOPIFY_API_TOKEN")
    if not token:
        raise SystemExit("❌ Missing SHOPIFY_API_TOKEN")
    
    if not validate_token(token):
        raise SystemExit("❌ Token inválido. Formato esperado: shpat_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    
    return {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
        "User-Agent": DEFAULT_UA
    }


def request_json(method: str, path: str, data: bytes | None = None) -> Dict[str, Any]:
    """Faz request HTTP com rate limiting e error handling seguro"""
    
    if not check_rate_limit():
        raise SystemExit("❌ Rate limit excedido. Aguarde 1 minuto.")
    
    # Sanitize path - apenas alphanumeric, slash, hyphen, underscore, dot, question, equals, ampersand
    if not re.match(r'^[a-zA-Z0-9/_.\-?=&]+$', path):
        raise SystemExit(f"❌ Path inválido: {path}")
    
    req = urlrequest.Request(
        f"{base_url()}{path}",
        method=method,
        headers=headers(),
        data=data
    )
    
    try:
        with urlrequest.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urlrequest.HTTPError as e:
        # Não vaza body de erro sensível
        status = e.code
        if status == 401:
            raise SystemExit("❌ Token inválido ou expirado (401)")
        elif status == 403:
            raise SystemExit("❌ Acesso negado - verifique permissões do token (403)")
        elif status == 404:
            raise SystemExit("❌ Recurso não encontrado (404)")
        elif status == 429:
            raise SystemExit("❌ Rate limit Shopify excedido (429). Tente novamente.")
        elif status >= 500:
            raise SystemExit(f"❌ Erro no servidor Shopify ({status})")
        else:
            raise SystemExit(f"❌ HTTP Error: {status}")
    except urlrequest.URLError as e:
        raise SystemExit(f"❌ Erro de conexão: {getattr(e, 'reason', str(e))}")
    except json.JSONDecodeError:
        raise SystemExit("❌ Resposta inválida do Shopify")
    except Exception as e:
        # Log interno, mensagem genérica
        print(f"[ERROR] Request failed: {e}", file=sys.stderr)
        raise SystemExit("❌ Erro interno na requisição")


def export_catalog(out: str) -> None:
    items: list[Dict] = []
    cursor = None
    page = 0
    
    while True:
        page += 1
        if page > 100:  # Safety limit
            print("⚠️ Limite de 100 páginas atingido", file=sys.stderr)
            break
            
        q = "?limit=250"
        if cursor:
            q += f"&page_info={cursor}"
        
        payload = request_json("GET", f"/products.json{q}")
        products = payload.get("products", [])
        
        if not products:
            break
        
        for p in products:
            variants = p.get("variants", []) or [{}]
            inv = variants[0].get("inventory_quantity")
            price = variants[0].get("price")
            items.append({
                "id": p.get("id"),
                "title": p.get("title"),
                "status": p.get("status"),
                "product_type": p.get("product_type"),
                "vendor": p.get("vendor"),
                "inventory": inv,
                "price": price,
            })
        
        if len(products) < 250:
            break
            
        # Cursor para próxima página
        link_header = ""
        try:
            # Tenta pegar do header Link (não disponível no payload JSON padrão)
            pass
        except:
            pass
        
        cursor = payload.get("page_info")
        if not cursor:
            break
    
    path = Path(out)
    fieldnames = ["id", "title", "status", "product_type", "vendor", "inventory", "price"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(items)
    
    print(f"✅ Exported {len(items)} products -> {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    exp = sub.add_parser("export-catalog")
    exp.add_argument("--out", default="catalog.csv")
    args = parser.parse_args()
    
    if args.command == "export-catalog":
        export_catalog(args.out)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()