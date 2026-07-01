#!/usr/bin/env python3
"""
Pipeline Unificado: Maps Lead Extractor (OSM) + Shopify Lead Extractor + Sales Prospecting
Suporta múltiplas fontes de leads: OSM (maps-lead-extractor) e Google Search (shopify-lead-extractor)
"""
import sys
import json
import argparse
import subprocess
import urllib.request
import os
from pathlib import Path
from datetime import datetime

# Diretórios das skills (scripts movidos para scripts/prospecting/)
SCRIPTS_DIR = Path(__file__).parent
MAPS_EXTRACT_SCRIPT = SCRIPTS_DIR / "extract.py"
SHOPIFY_EXTRACT_SCRIPT = Path(__file__).parent.parent.parent / "shopify-ops" / "shopify_ops.py"
# Note: shopify-ops lives under sales-prospecting/ after code consolidation
RUN_SCRIPT = SCRIPTS_DIR / "generate_proposals_direct.py"

# API do Dashboard
DASHBOARD_API = "http://localhost:8765/api"


def run_cmd(cmd, cwd=None, timeout=300):
    """Executa comando e retorna (success, stdout, stderr)."""
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    return result.returncode == 0, result.stdout, result.stderr


def post_to_dashboard(endpoint: str, data: dict) -> bool:
    """POST para API do dashboard."""
    try:
        url = f"http://localhost:8765/api{endpoint}"
        # Usa API key do .env - SEM fallback hardcoded
        api_key = os.environ.get("DASHBOARD_API_KEY")
        if not api_key:
            print(f"   ⚠️ DASHBOARD_API_KEY não configurada; sincronização ignorada.")
            return False
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'X-API-Key': api_key
            },
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"   ⚠️ Falha ao sincronizar com dashboard: {e}")
        return False


def extract_osm_leads(args, leads_file):
    """Extrai leads via OpenStreetMap (maps-lead-extractor)."""
    print("📍 [1/2] Extraindo leads do OpenStreetMap...")

    extract_cmd = [
        sys.executable, str(MAPS_EXTRACT_SCRIPT),
        "--location", args.location,
        "--category", args.category,
        "--limit", str(args.limit),
        "--radius", str(args.radius),
        "--output", str(leads_file)
    ]
    if args.only_with_phone:
        extract_cmd.append("--only_with_phone")
    if hasattr(args, 'only_with_website') and args.only_with_website:
        extract_cmd.append("--only_with_website")
    if args.only_whatsapp_dd21:
        extract_cmd.append("--only_whatsapp_dd21")

    ok, stdout, stderr = run_cmd(extract_cmd, timeout=120)
    
    if not ok:
        print(f"❌ Erro na extração OSM: {stderr}")
        return None
    
    leads = json.loads(leads_file.read_text(encoding="utf-8"))
    for l in leads:
        l["category"] = args.category
    return leads


def extract_shopify_leads(args, leads_file):
    """Extrai leads via Google Search (shopify-lead-extractor)."""
    print("🛍️ [1/2] Extraindo leads Shopify via Google Search...")
    
    niches = args.niches.split(',') if hasattr(args, 'niches') and args.niches else [args.niche]
    
    extract_cmd = [
        sys.executable, str(SHOPIFY_EXTRACT_SCRIPT),
        "--location", args.location,
        "--niches", args.niches if args.niches else args.niche,
        "--limit", str(args.limit),
        "--output", str(leads_file)
    ]
    if args.only_with_phone:
        extract_cmd.append("--only_with_phone")
    
    ok, stdout, stderr = run_cmd([
        sys.executable, str(SHOPIFY_EXTRACT_SCRIPT),
        "--location", args.location,
        "--niches", args.niches if args.niches else args.niche,
        "--limit", str(args.limit),
        "--output", str(leads_file)
    ] + (["--only_with_phone"] if args.only_with_phone else []), timeout=300)
    
    if not ok:
        print(f"❌ Erro na extração Shopify: {stderr}")
        return None
    
    leads = json.loads(leads_file.read_text(encoding="utf-8"))
    
    # Enriquece com nicho/categoria
    for r in leads:
        r["category"] = args.category
        # Infere business_type do nicho
        for niche in niches:
            if niche.lower() in r.get('store_url', '').lower():
                r['business_type'] = infer_business_type(niche)
                break
        else:
            r['business_type'] = infer_business_type(niches[0])
    
    return leads


def infer_business_type(niche: str) -> str:
    niche_lower = niche.lower()
    mapping = {
        'moda': 'Moda feminina', 'roupa': 'Moda feminina', 'vestuario': 'Moda feminina',
        'masculina': 'Moda masculina', 'feminina': 'Moda feminina',
        'beleza': 'Beleza/Cosméticos', 'cosmeticos': 'Beleza/Cosméticos', 'maquiagem': 'Beleza/Cosméticos',
        'suplemento': 'Suplementos', 'vitamina': 'Suplementos', 'whey': 'Suplementos',
        'pet': 'Pet Shop', 'cachorro': 'Pet Shop', 'gato': 'Pet Shop',
        'eletronico': 'Eletrônicos', 'celular': 'Eletrônicos', 'informatica': 'Eletrônicos',
        'casa': 'Casa/Decoração', 'decoracao': 'Casa/Decoração', 'moveis': 'Casa/Decoração',
        'esporte': 'Esportes', 'fitness': 'Esportes', 'academia': 'Esportes',
        'alimento': 'Alimentos/Bebidas', 'bebida': 'Alimentos/Bebidas', 'cafe': 'Alimentos/Bebidas',
        'livro': 'Livros/Papelaria', 'papelaria': 'Livros/Papelaria',
        'infantil': 'Infantil/Bebê', 'bebe': 'Infantil/Bebê',
        'automotivo': 'Automotivo', 'peca': 'Automotivo',
    }
    for key, val in mapping.items():
        if key in niche_lower:
            return val
    return niche.title()


def generate_proposals(leads_file, proposals_file, model=None):
    """Gera propostas via sales-prospecting."""
    run_cmd_args = [
        sys.executable, str(RUN_SCRIPT),
        "--file", str(leads_file),
        "--output", str(proposals_file)
    ]
    if model:
        run_cmd_args.extend(["--model", model])
    
    ok, stdout, stderr = run_cmd(run_cmd_args, timeout=120)
    if not ok:
        print(f"❌ Erro na geração: {stderr}")
        return None
    
    # Parseia propostas
    content = Path(proposals_file).read_text(encoding="utf-8")
    import re
    blocks = re.split(r'=== LEAD \d+: ', content)
    proposals = []
    for i, block in enumerate(blocks):
        block = block.strip()
        if not block:
            continue
        lines = block.split('\n')
        lead_name = f"Lead {i}"
        if lines[0]:
            lead_name = lines[0].split('===')[0].strip()
            if '===' in lead_name:
                lead_name = lead_name.split('===')[0].strip()
        proposals.append({
            "id": f"prop_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}",
            "lead_name": lead_name,
            "content": "=== LEAD " + str(i) + ": " + block,
            "date": datetime.now().isoformat(),
            "status": "pending"
        })
    return proposals


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline Unificado: OSM + Shopify + Sales Prospecting"
    )
    parser.add_argument("--source", required=True, choices=["osm", "shopify"], 
                        help="Fonte dos leads: osm (OpenStreetMap) ou shopify (Google Search)")
    parser.add_argument("--location", required=True, help="Cidade/endereço (ex: 'Rio de Janeiro, RJ')")
    parser.add_argument("--category", required=True, 
                        choices=["hospitality", "retail", "food", "health", "beauty",
                                 "automotive", "services", "education", "entertainment"],
                        help="Categoria de negócio (para OSM)")
    parser.add_argument("--niche", help="Nicho para busca Shopify (ex: 'moda feminina')")
    parser.add_argument("--niches", help="Múltiplos nichos separados por vírgula (para Shopify)")
    parser.add_argument("--limit", type=int, default=20, help="Máximo de leads")
    parser.add_argument("--radius", type=int, default=5000, help="Raio em metros (OSM)")
    parser.add_argument("--only_with_phone", action="store_true", help="Só leads com telefone")
    parser.add_argument("--only_whatsapp_dd21", action="store_true", help="Só leads com WhatsApp válido DDD 21 (21 9xxxxxxxx)")
    parser.add_argument("--output_dir", default="./pipeline_output", help="Diretório de saída")
    parser.add_argument("--model", help="Modelo LLM (padrão: auto)")
    parser.add_argument("--dry_run", action="store_true", help="Só mostra o que faria")
    parser.add_argument("--no_sync", action="store_true", help="Não sincroniza com dashboard")
    args = parser.parse_args()

    # Validação
    if args.source == "shopify" and not (args.niche or args.niches):
        parser.error("Para source=shopify, forneça --niche ou --niches")
    if args.source == "osm" and not args.category:
        parser.error("Para source=osm, forneça --category")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_location = args.location.replace(",", "").replace(" ", "_").lower()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    leads_file = output_dir / f"leads_{safe_location}_{timestamp}.json"
    proposals_file = output_dir / f"propostas_{safe_location}_{timestamp}.txt"

    print(f"\n{'='*60}")
    print(f"🚀 PIPELINE UNIFICADO: {args.source.upper()} | {args.location}")
    print(f"{'='*60}")
    print(f"📁 Output: {output_dir}")
    print(f"   Leads:      {leads_file.name}")
    print(f"   Propostas:  {proposals_file.name}")
    print(f"{'='*60}\n")

    if args.dry_run:
        print("🔍 DRY RUN - Mostra comandos que seriam executados")
        if args.source == "osm":
            print(f"  1. OSM Extract: {MAPS_EXTRACT_SCRIPT} --location '{args.location}' --category {args.category} ...")
        else:
            print(f"  1. Shopify Extract: {SHOPIFY_EXTRACT_SCRIPT} --location '{args.location}' --niche '{args.niche or args.niches}' ...")
        print(f"  2. Generate Proposals: {RUN_SCRIPT} --file {leads_file} --output {proposals_file}")
        return 0

    # ===== PASSO 1: Extrai leads =====
    if args.source == "osm":
        leads = extract_osm_leads(args, leads_file)
    else:
        leads = extract_shopify_leads(args, leads_file)

    if not leads:
        return 1

    n_leads = len(leads)
    print(f"   ✅ {n_leads} leads extraídos")
    if n_leads == 0:
        print("   ⚠️ Nenhum lead encontrado.")
        return 0

    # Adiciona categoria e localização
    for l in leads:
        l["category"] = args.category
        l["location"] = args.location
    leads_file.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")

    # Sincroniza leads com dashboard
    if not args.no_sync:
        print("   🔄 Sincronizando leads com dashboard...")
        ok = post_to_dashboard("/leads", {"leads": leads})
        if ok:
            print(f"   ✅ {len(leads)} leads sincronizados")
        else:
            print(f"   ⚠️ Falha ao sincronizar leads")

    # ===== PASSO 2: Gera propostas =====
    print(f"\n📝 [2/2] Gerando {n_leads} propostas personalizadas...")
    proposals = generate_proposals(leads_file, proposals_file, args.model)
    if proposals is None:
        return 1

    print(f"   ✅ Propostas salvas em: {proposals_file}")

    # Parseia propostas para dashboard
    proposals_data = []
    try:
        content = Path(proposals_file).read_text(encoding="utf-8")
        import re
        blocks = re.split(r'=== LEAD \d+: ', content)
        for i, block in enumerate(blocks):
            block = block.strip()
            if not block:
                continue
            lines = block.split('\n')
            lead_name = f"Lead {i}"
            if lines[0]:
                lead_name = lines[0].split('===')[0].strip().split('===')[0]
            proposals_data.append({
                "id": f"prop_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}",
                "lead_name": lead_name,
                "content": "=== LEAD " + str(i) + ": " + block,
                "category": args.category,
                "date": datetime.now().isoformat(),
                "status": "pending"
            })
    except Exception as e:
        print(f"   ⚠️ Erro parseando propostas: {e}")

    # Sincroniza com dashboard
    if not args.no_sync and proposals_data:
        print("   🔄 Sincronizando propostas com dashboard...")
        ok = post_to_dashboard("/proposals", {"proposals": proposals_data})
        if ok:
            print(f"   ✅ {len(proposals_data)} propostas sincronizadas")
        else:
            print(f"   ⚠️ Falha ao sincronizar propostas")

    # ===== Resumo =====
    print(f"\n{'='*60}")
    print(f"✅ PIPELINE CONCLUÍDO")
    print(f"{'='*60}")
    print(f"📊 Leads processados: {n_leads}")
    print(f"📄 Propostas geradas: {proposals_file}")
    print(f"📂 Leads brutos:      {leads_file}")
    print(f"\n💡 Próximos passos:")
    print(f"   1. Revise as propostas em {proposals_file}")
    print(f"   2. Copie os textos (PROPOSTA + SUBJECT) para WhatsApp")
    print(f"   3. Dashboard: http://localhost:8765/dashboard")
    print(f"   4. Automatize com cron (ver abaixo)")
    print(f"{'='*60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())