#!/usr/bin/env python3
"""
Direct proposal generator — no Hermes CLI subprocess, no session failures.
Uses the same prompt template logic from sales-prospecting skill.
Usage:
  python3 generate_proposals_direct.py --file leads.json --output propostas.txt
  python3 generate_proposals_direct.py --lead_name "João" --business_type "Pousada" --location "Porto Seguro, BA" --phone "73999999999"
"""
import sys
import json
import argparse
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent

def load_template():
    template_path = SKILL_DIR / "templates" / "prompt.txt"
    return template_path.read_text(encoding="utf-8")

def select_product(business_type: str) -> tuple:
    """Map business type to product line."""
    bt = business_type.lower()
    hospitality = ["hotel", "pousada", "hostel", "hospedagem"]
    retail = ["restaurante", "lanchonete", "café", "bar", "padaria", "supermercado",
              "conveniência", "floricultura", "sapataria", "móveis", "loja de roupas",
              "roupas", "acessórios", "calçados", "furniture", "clothes", "shoes"]
    
    if any(kw in bt for kw in hospitality):
        return ("LOBBY", "SaaS LOBBY (R$ 197-697/mês) — PMS completo, automação de reservas, relatórios financeiros")
    elif any(kw in bt for kw in retail):
        return ("CRM/PDV", "SaaS CRM/PDV (R$ 300-800/mês) — Gestão de clientes, controle de estoque, análise de vendas")
    else:
        return ("SITE", "Site Profissional (R$ 1.500-3.000) — Landing page customizada, SEO otimizado, integração redes sociais")

def generate_proposal(lead: dict) -> str:
    name = lead.get("lead_name", "Lead")
    biz = lead.get("business_type", "Negócio")
    phone = lead.get("phone", "")
    location = lead.get("location", "")
    has_website = "website" in lead and lead["website"]
    
    product_key, product_desc = select_product(biz)
    first_name = name.split()[0]
    
    pain_points = {
        "LOBBY": (
            f"{name} perde 15-25% de cada reserva para Booking/Decolar + gestão manual = receita vazando.",
            "Overdependência de OTAs com comissão alta + falta de PMS integrado."
        ),
        "CRM/PDV": (
            f"{name} vende no escuro: sem estoque digitalizado, não sabe o que vende, não captura cliente pra remarketing.",
            "Venda dependente de Instagram/loja física + estoque na memória = perde venda e não retém cliente."
        ),
        "SITE": (
            f"{name} é invisível no Google: cliente pesquisa \"{biz.lower()} {location.split(',')[0]}\" e acha concorrente primeiro.",
            "Ausência de presença digital própria = refém de algoritmo de rede social."
        )
    }
    
    why, pain = pain_points[product_key]
    
    if product_key == "LOBBY":
        proposal = f"Oi, vi {name} em {location} e notei que hospedagens da região perdem 15-25% por reserva pro Booking. Tenho 2 caminhos: (1) Site profissional R$ 2.500 com SEO local + botão \"Reservar Direto\" no WhatsApp — elimina comissão. (2) SaaS LOBBY R$ 397/mês: PMS completo, channel manager sincroniza Booking/Airbnb, relatórios automáticos. Qual testa primeiro? Posso mostrar demo agora."
        subject = f"{first_name}, sua hospedagem em {location.split(',')[0]} tá perdendo R$ pro Booking 📉"
    elif product_key == "CRM/PDV":
        proposal = f"Oi, vi {name} ({biz}) em {location.split(',')[0]} e achei que poderíamos conversar. Muitas lojas do segmento perdem venda porque: (1) cliente pergunta \"tem preto M?\" e ninguém responde rápido; (2) não sabe quais peças mais vendem pra reposição; (3) cliente some depois da primeira compra. Meu SaaS CRM/PDV a R$ 300-800/mês arruma estoque, cadastra cliente, mostra relatório claro do que vende. Demo nas próximas 24h?"
        subject = f"{first_name}, seu estoque de {biz.lower()} tá no papel ou no digital? 📦"
    else:
        proposal = f"Oi, {name} em {location.split(',')[0]} — quando alguém busca \"{biz.lower()} {location.split(',')[0]}\" no celular, seu concorrente com site aparece primeiro. Site profissional a partir de R$ 1.500 (pagamento único) coloca você no Google, integra WhatsApp/Instagram e elimina dependência do algoritmo. Se já tem site, o CRM/PDV a R$ 300/mês organiza vendas e clientes. Qual o gargalo hoje?"
        subject = f"{first_name}, seu {biz.lower()} em {location.split(',')[0]} aparece no Google ou só o concorrente? 🔍"
    
    return f"""=== LEAD: {name} ===
ANÁLISE:
- Por que esse lead precisa deste produto?
  {why}
- Qual é o pain point principal?
  {pain}

PROPOSTA:
{proposal}

SUBJECT:
{subject}
"""

def main():
    parser = argparse.ArgumentParser(description="Direct proposal generator (no Hermes CLI)")
    parser.add_argument("--file", help="JSON file with array of leads")
    parser.add_argument("--lead_name", help="Single lead name")
    parser.add_argument("--business_type", help="Business type")
    parser.add_argument("--location", help="Location")
    parser.add_argument("--phone", help="Phone")
    parser.add_argument("--output", help="Output file")
    args = parser.parse_args()
    
    leads = []
    if args.file:
        leads = json.loads(Path(args.file).read_text(encoding="utf-8"))
    elif all([args.lead_name, args.business_type, args.location, args.phone]):
        leads = [{
            "lead_name": args.lead_name,
            "business_type": args.business_type,
            "location": args.location,
            "phone": args.phone
        }]
    else:
        print("ERRO: Forneça --file OU --lead_name/--business_type/--location/--phone", file=sys.stderr)
        sys.exit(1)
    
    outputs = [generate_proposal(lead) for lead in leads]
    final = "\n\n".join(outputs)
    
    if args.output:
        Path(args.output).write_text(final, encoding="utf-8")
        print(f"✅ {len(leads)} propostas salvas em: {args.output}")
    else:
        print(final)

if __name__ == "__main__":
    main()