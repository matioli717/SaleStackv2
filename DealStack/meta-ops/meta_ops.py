# ============================================================
# FIX H04/H07 - meta_ops.py + meta_campaign_manager.py
# Substitua ambos os arquivos
# ============================================================

#!/usr/bin/env python3
"""
Meta Ads Ops - VERSÃO SEGURA
- Validação de token
- API version atualizada (v20.0)
- Rate limiting
- Error handling seguro
- User-Agent customizado
"""

import argparse
import csv
import os
import sys
import json
import time
import re
from urllib import request as urlrequest
from typing import Dict, Any, List

# ============================================================
# CONFIGURAÇÃO
# ============================================================

META_API_VERSION = os.environ.get("META_API_VERSION", "v20.0")  # Atualizado de v19.0
VALID_API_VERSIONS = ["v18.0", "v19.0", "v20.0"]
META_GRAPH = f"https://graph.facebook.com/{META_API_VERSION}"

RATE_LIMIT = 60
_request_times = []

DEFAULT_UA = f"DealStack-MetaOps/1.0 (+https://github.com/matioli616/DealStack)"
ACCESS_TOKEN_PATTERN = re.compile(r'^EAA[A-Za-z0-9]{100,}$')  # Meta Access Token format


def validate_token(token: str) -> bool:
    if not token:
        return False
    return bool(ACCESS_TOKEN_PATTERN.match(token))


def check_rate_limit() -> bool:
    global _request_times
    now = time.time()
    minute_ago = now - 60
    _request_times = [t for t in _request_times if t > minute_ago]
    if len(_request_times) >= RATE_LIMIT:
        return False
    _request_times.append(now)
    return True


def headers() -> Dict[str, str]:
    token = os.environ.get('META_ACCESS_TOKEN') or os.environ.get('META_ADS_TOKEN')
    if not token:
        raise SystemExit('❌ Missing META_ADS_TOKEN or META_ACCESS_TOKEN')
    if not validate_token(token):
        raise SystemExit('❌ Token inválido. Formato esperado: EAA... (long-lived access token)')
    return {
        'Authorization': f'Bearer {token}',
        'User-Agent': DEFAULT_UA
    }


def fetch(path: str) -> Dict[str, Any]:
    if not check_rate_limit():
        raise SystemExit("❌ Rate limit excedido. Aguarde 1 minuto.")
    
    # Sanitize path
    if not re.match(r'^[a-zA-Z0-9/_.\-?=&]+$', path):
        raise SystemExit(f"❌ Path inválido: {path}")
    
    req = urlrequest.Request(f"{META_GRAPH}{path}", headers=headers())
    
    try:
        with urlrequest.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urlrequest.HTTPError as e:
        status = e.code
        if status == 401:
            raise SystemExit("❌ Token inválido ou expirado (401)")
        elif status == 403:
            raise SystemExit("❌ Acesso negado - verifique permissões (403)")
        elif status == 429:
            raise SystemExit("❌ Rate limit Meta excedido (429)")
        elif status >= 500:
            raise SystemExit(f"❌ Erro no servidor Meta ({status})")
        else:
            raise SystemExit(f"❌ HTTP Error: {status}")
    except urlrequest.URLError as e:
        raise SystemExit(f"❌ Erro de conexão: {getattr(e, 'reason', str(e))}")
    except json.JSONDecodeError:
        raise SystemExit("❌ Resposta inválida da Meta")
    except Exception as e:
        print(f"[ERROR] Fetch failed: {e}", file=sys.stderr)
        raise SystemExit("❌ Erro interno na requisição")


def campaign_insights(account_id: str, out: str) -> None:
    # Valida account_id (apenas números)
    if not account_id.isdigit():
        raise SystemExit("❌ account-id deve ser numérico")
    
    data = fetch(f'/{account_id}/insights?fields=account_name,impressions,clicks,spend,actions,ad_name,adset_name,campaign_name&limit=500')
    rows = data.get('data', [])
    fieldnames = ['campaign_name','adset_name','ad_name','impressions','clicks','spend','actions']
    
    with open(out, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k,'') for k in fieldnames})
    print(f'✅ exported {len(rows)} rows -> {out}')


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command')
    ci = sub.add_parser('campaign-insights')
    ci.add_argument('--account-id', required=True)
    ci.add_argument('--out', default='meta_insights.csv')
    args = parser.parse_args()
    if args.command == 'campaign-insights':
        campaign_insights(args.account_id, args.out)


if __name__ == '__main__':
    main()