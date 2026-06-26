#!/usr/bin/env python3
"""
Pipeline: extrai leads via extract.py e injeta no dashboard via POST /api/leads
"""
import json
import sys
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path

import os

DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://dealstack-m9re.onrender.com")
def _get_api_key():
    key = os.environ.get("DASHBOARD_API_KEY") or os.environ.get("API_KEYS", "")
    if key and key.startswith("["):
        try: return json.loads(key)[0].get("key", "")
        except: pass
    return key

API_KEY = _get_api_key()
if not API_KEY:
    print("❌ API key não configurada (DASHBOARD_API_KEY ou API_KEYS).", file=sys.stderr)
    sys.exit(1)
EXTRACT_SCRIPT = Path("/workspaces/OpnCld/scripts/prospecting/extract.py")


def run_extract(location: str, category: str = "retail", radius: int = 5000, limit: int = 50) -> list:
    cmd = [
        sys.executable,
        str(EXTRACT_SCRIPT),
        "--location", location,
        "--category", category,
        "--radius", str(radius),
        "--limit", str(limit),
        "--only_with_phone",
        "--verbose",
    ]
    print(f"[EXTRACT] {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0 and not result.stdout.strip():
        print(f"[EXTRACT] ERRO: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    try:
        leads = json.loads(result.stdout)
        return leads if isinstance(leads, list) else []
    except json.JSONDecodeError:
        print("[EXTRACT] Saída não é JSON válido.", file=sys.stderr)
        print(result.stdout[:500])
        return []


def post_leads(leads: list) -> None:
    if not leads:
        print("[DASHBOARD] Nenhum lead para enviar.")
        return
    payload = json.dumps({"leads": leads}, ensure_ascii=False).encode("utf-8")
    url = urllib.parse.urljoin(DASHBOARD_URL, "/api/leads")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "X-API-Key": API_KEY,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        print(f"[DASHBOARD] POST /api/leads -> {resp.status}")
        print(f"[DASHBOARD] Resposta: {body}")


def main():
    # Ajuste estes parâmetros conforme a extração desejada
    location = "Jacarepaguá, Rio de Janeiro"
    category = "retail"
    radius = 5000
    limit = 50

    leads = run_extract(location=location, category=category, radius=radius, limit=limit)
    print(f"[EXTRACT] Leads extraídos: {len(leads)}")
    if not leads:
        sys.exit(0)

    # Sanitiza para o formato esperado pelo servidor (opcional)
    # O servidor usa lead_name/business_type/location/phone, então mantemos como está.
    post_leads(leads)


if __name__ == "__main__":
    main()
