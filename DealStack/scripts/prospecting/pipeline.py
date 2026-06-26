#!/usr/bin/env python3
"""
Pipeline completo: Maps Lead Extractor + Sales Prospecting
Um comando só para extrair leads e gerar propostas personalizadas.
"""
import sys
import json
import argparse
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime

# Diretórios das skills
BASE_DIR = Path(__file__).parent.parent.parent
MAPS_SKILL = BASE_DIR / "maps-lead-extractor"
SALES_SKILL = BASE_DIR / "sales-prospecting"

EXTRACT_SCRIPT = MAPS_SKILL / "scripts" / "extract.py"
RUN_SCRIPT = SALES_SKILL / "scripts" / "run.py"

# API do Dashboard (para sincronizar resultados)
DASHBOARD_API = "http://localhost:8765/api"


def run_cmd(cmd, cwd=None, timeout=300):
    """Executa comando e retorna (success, stdout, stderr)."""
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    return result.returncode == 0, result.stdout, result.stderr


def get_api_key():
    key = os.environ.get("DASHBOARD_API_KEY") or os.environ.get("API_KEYS", "")
    if key and key.startswith("["):
        try: return json.loads(key)[0].get("key", "")
        except: pass
    return key

def post_to_dashboard(endpoint: str, data: dict) -> bool:
    """POST para API do dashboard."""
    try:
        url = f"{DASHBOARD_API}{endpoint}"
        api_key = get_api_key()
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['X-API-Key'] = api_key
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"   ⚠️ Falha ao sincronizar com dashboard: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline completo: Extrai leads do Maps → Gera propostas de vendas"
    )
    parser.add_argument("--location", required=True, help="Cidade/endereço (ex: 'Porto Seguro, BA')")
    parser.add_argument("--category", required=True,
                        choices=["hospitality", "retail", "food", "health", "beauty",
                                 "automotive", "services", "education", "entertainment"],
                        help="Categoria de negócio")
    parser.add_argument("--limit", type=int, default=20, help="Máximo de leads (padrão: 20)")
    parser.add_argument("--radius", type=int, default=5000, help="Raio em metros (padrão: 5000)")
    parser.add_argument("--only_with_phone", action="store_true", help="Só leads com telefone")
    parser.add_argument("--only_with_website", action="store_true", help="Só leads com website")
    parser.add_argument("--output_dir", default="./pipeline_output", help="Diretório de saída")
    parser.add_argument("--model", help="Modelo LLM (padrão: auto - usa config do sales-prospecting)")
    parser.add_argument("--dry_run", action="store_true", help="Só mostra o que faria, não executa")
    parser.add_argument("--no_sync", action="store_true", help="Não sincroniza com dashboard")

    args = parser.parse_args()

    # Prepara output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_location = args.location.replace(",", "").replace(" ", "_").lower()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    leads_file = output_dir / f"leads_{safe_location}_{timestamp}.json"
    proposals_file = output_dir / f"propostas_{safe_location}_{timestamp}.txt"

    print(f"\n{'='*60}")
    print(f"🚀 PIPELINE: {args.location} | {args.category} | limit={args.limit}")
    print(f"{'='*60}")
    print(f"📁 Output: {output_dir}")
    print(f"   Leads:      {leads_file.name}")
    print(f"   Propostas:  {proposals_file.name}")
    print(f"{'='*60}\n")

    if args.dry_run:
        print("🔍 DRY RUN - Comando que seria executado:")
        print(f"  1. python3 {EXTRACT_SCRIPT} \\")
        print(f"       --location '{args.location}' \\")
        print(f"       --category {args.category} \\")
        print(f"       --limit {args.limit} --radius {args.radius} \\")
        print(f"       {'--only_with_phone' if args.only_with_phone else ''} \\")
        print(f"       {'--only_with_website' if args.only_with_website else ''} \\")
        print(f"       --output {leads_file}")
        print(f"  2. python3 {RUN_SCRIPT} \\")
        print(f"       --file {leads_file} \\")
        print(f"       --output {proposals_file}")
        if args.model:
            print(f"       --model {args.model}")
        return 0

    # ===== PASSO 1: Extrai leads =====
    print("📍 [1/2] Extraindo leads do OpenStreetMap...")
    extract_cmd = [
        sys.executable, str(EXTRACT_SCRIPT),
        "--location", args.location,
        "--category", args.category,
        "--limit", str(args.limit),
        "--radius", str(args.radius),
        "--output", str(leads_file)
    ]
    if args.only_with_phone:
        extract_cmd.append("--only_with_phone")
    if args.only_with_website:
        extract_cmd.append("--only_with_website")

    ok, stdout, stderr = run_cmd(extract_cmd, timeout=120)
    if not ok:
        print(f"❌ Erro na extração: {stderr}")
        return 1

    # Conta leads extraídos
    try:
        leads = json.loads(leads_file.read_text(encoding="utf-8"))
        n_leads = len(leads)
        print(f"   ✅ {n_leads} leads extraídos")
        if n_leads == 0:
            print("   ⚠️ Nenhum lead encontrado. Tente aumentar --radius ou mudar --category.")
            return 0
    except Exception as e:
        print(f"   ❌ Erro lendo leads: {e}")
        return 1

    # Adiciona categoria aos leads (para dashboard)
    for l in leads:
        l["category"] = args.category
    leads_file.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")

    # Sincroniza leads com dashboard
    if not args.no_sync:
        print("   🔄 Sincronizando leads com dashboard...")
        post_to_dashboard("/leads", {"leads": leads})

    # ===== PASSO 2: Gera propostas =====
    print(f"\n📝 [2/2] Gerando {n_leads} propostas personalizadas...")
    run_cmd_args = [
        sys.executable, str(RUN_SCRIPT),
        "--file", str(leads_file),
        "--output", str(proposals_file)
    ]
    if args.model:
        run_cmd_args.extend(["--model", args.model])

    ok, stdout, stderr = run_cmd(run_cmd_args, timeout=180 * n_leads)
    if not ok:
        print(f"❌ Erro na geração: {stderr}")
        return 1

    print(f"   ✅ Propostas salvas em: {proposals_file}")

    # Parseia propostas para JSON (formato simple: separa por ===)
    proposals = []
    try:
        content = proposals_file.read_text(encoding="utf-8")
        # Split por === LEAD N:
        import re
        blocks = re.split(r'=== LEAD \d+: ', content)
        for i, block in enumerate(blocks):
            block = block.strip()
            if not block:
                continue
            # Primeira linha é o nome do lead (até === ou fim do bloco)
            lines = block.split('\n')
            lead_name = f"Lead {i}"
            if lines[0]:
                lead_name = lines[0].split('===')[0].strip()
                if '===' in lead_name:
                    lead_name = lead_name.split('===')[0].strip()
            proposals.append({
                "id": f"prop_{timestamp}_{i}",
                "lead_name": lead_name,
                "content": "=== LEAD " + str(i) + ": " + block,
                "category": args.category,
                "date": datetime.now().isoformat(),
                "status": "pending"
            })
    except Exception as e:
        print(f"   ⚠️ Erro parseando propostas: {e}")

    # Sincroniza propostas com dashboard
    if not args.no_sync and proposals:
        print("   🔄 Sincronizando propostas com dashboard...")
        post_to_dashboard("/proposals", {"proposals": proposals})

    # ===== Resumo =====
    print(f"\n{'='*60}")
    print(f"✅ PIPELINE CONCLUÍDO")
    print(f"{'='*60}")
    print(f"📊 Leads processados: {n_leads}")
    print(f"📄 Propostas geradas: {proposals_file}")
    print(f"📂 Leads brutos:      {leads_file}")
    if not args.no_sync:
        print(f"☁️  Sincronizado com dashboard")
    print(f"\n💡 Próximos passos:")
    print(f"   1. Revise as propostas em {proposals_file}")
    print(f"   2. Copie os textos (PROPOSTA + SUBJECT) para WhatsApp")
    print(f"   3. Dashboard: http://localhost:8765/dashboard")
    print(f"   4. Automatize com cron (ver abaixo)")
    print(f"{'='*60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())