# ============================================================
# FIX meta_campaign_manager.py - VERSÃO SEGURA
# Substitua: /workspaces/OpnCld/meta-ops/meta_campaign_manager.py
# ============================================================

#!/usr/bin/env python3
"""
Meta Ads Campaign Manager - VERSÃO SEGURA
- Validação de token
- API version v20.0
- Rate limiting
- Error handling seguro
- Input validation
"""

import argparse
import csv
import json
import os
import sys
import time
import re
from urllib import request as urlrequest
from typing import Dict, Any, List

# ============================================================
# CONFIGURAÇÃO
# ============================================================

META_API_VERSION = os.environ.get("META_API_VERSION", "v20.0")
VALID_API_VERSIONS = ["v18.0", "v19.0", "v20.0"]
META_GRAPH = f"https://graph.facebook.com/{META_API_VERSION}"

RATE_LIMIT = 60
_request_times = []

DEFAULT_UA = f"DealStack-MetaCampaign/1.0 (+https://github.com/matioli616/DealStack)"
ACCESS_TOKEN_PATTERN = re.compile(r'^EAA[A-Za-z0-9_-]{100,}$')  # Meta Access Token format


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


def _headers() -> Dict[str, str]:
    token = os.environ.get('META_ACCESS_TOKEN') or os.environ.get('META_ADS_TOKEN')
    if not token:
        raise SystemExit('❌ Missing META_ADS_TOKEN or META_ACCESS_TOKEN')
    if not validate_token(token):
        raise SystemExit('❌ Token inválido. Formato: EAA... (long-lived)')
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'User-Agent': DEFAULT_UA
    }


def _get(path: str) -> Dict[str, Any]:
    if not check_rate_limit():
        raise SystemExit("❌ Rate limit excedido. Aguarde 1 minuto.")
    
    if not re.match(r'^[a-zA-Z0-9/_.\-?=&]+$', path):
        raise SystemExit(f"❌ Path inválido: {path}")
    
    req = urlrequest.Request(f"{META_GRAPH}{path}", headers=_headers())
    
    try:
        with urlrequest.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urlrequest.HTTPError as e:
        status = e.code
        if status == 401:
            raise SystemExit("❌ Token inválido ou expirado (401)")
        elif status == 403:
            raise SystemExit("❌ Acesso negado (403)")
        elif status == 429:
            raise SystemExit("❌ Rate limit Meta (429)")
        elif status >= 500:
            raise SystemExit(f"❌ Erro servidor Meta ({status})")
        else:
            raise SystemExit(f"❌ HTTP Error: {status}")
    except urlrequest.URLError as e:
        raise SystemExit(f"❌ Erro conexão: {getattr(e, 'reason', str(e))}")
    except json.JSONDecodeError:
        raise SystemExit("❌ Resposta inválida Meta")
    except Exception as e:
        print(f"[ERROR] _get failed: {e}", file=sys.stderr)
        raise SystemExit("❌ Erro interno")


def campaign_insights(account_id: str, out: str = 'meta_insights.csv') -> None:
    if not account_id.isdigit():
        raise SystemExit("❌ account-id deve ser numérico")
    
    data = _get(f'/{account_id}/insights?fields=account_name,impressions,clicks,spend,actions,ad_name,adset_name,campaign_name,cpc,cpm,ctr&limit=500')
    rows = data.get('data', [])
    fieldnames = ['account_name','campaign_name','adset_name','ad_name','impressions','clicks','spend','cpc','cpm','ctr','actions']
    
    with open(out, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, '') for k in fieldnames})
    print(f'✅ exported {len(rows)} rows -> {out}')


def campaign_summary(account_id: str) -> Dict:
    if not account_id.isdigit():
        raise SystemExit("❌ account-id deve ser numérico")
    data = _get(f'/{account_id}/insights?fields=impressions,clicks,spend,cpc,ctr&limit=1&summary=true')
    summary = data.get('summary', {})
    return {
        'impressions': summary.get('impressions', 0),
        'clicks': summary.get('clicks', 0),
        'spend': summary.get('spend', 0),
        'cpc': summary.get('cpc', 0),
        'ctr': summary.get('ctr', 0),
    }


def list_campaigns(account_id: str, status: str = 'ALL') -> List:
    if not account_id.isdigit():
        raise SystemExit("❌ account-id deve ser numérico")
    valid_status = ['ALL', 'ACTIVE', 'PAUSED', 'DELETED', 'ARCHIVED']
    if status not in valid_status:
        raise SystemExit(f"❌ Status inválido. Use: {valid_status}")
    
    data = _get(f'/{account_id}/campaigns?fields=name,status,objective,created_time&limit=100')
    campaigns = data.get('data', [])
    if status != 'ALL':
        campaigns = [c for c in campaigns if c.get('status') == status]
    return campaigns


def main():
    parser = argparse.ArgumentParser(description='Meta Ads Manager - Secure')
    sub = parser.add_subparsers(dest='command')
    
    ci = sub.add_parser('insights')
    ci.add_argument('--account-id', required=True)
    ci.add_argument('--out', default='meta_insights.csv')
    
    cs = sub.add_parser('summary')
    cs.add_argument('--account-id', required=True)
    
    lc = sub.add_parser('list-campaigns')
    lc.add_argument('--account-id', required=True)
    lc.add_argument('--status', default='ALL')
    
    args = parser.parse_args()
    
    if args.command == 'insights':
        campaign_insights(args.account_id, args.out)
    elif args.command == 'summary':
        print(json.dumps(campaign_summary(args.account_id), indent=2, ensure_ascii=False))
    elif args.command == 'list-campaigns':
        print(json.dumps(list_campaigns(args.account_id, args.status), indent=2, ensure_ascii=False))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()