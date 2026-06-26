#!/usr/bin/env python3
"""
Script de entrada para a skill sales-prospecting.
Suporta: args individuais, --json, --file, --output, --model
"""
import sys
import json
import argparse
import subprocess
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Sales Prospecting - Gera propostas personalizadas")
    parser.add_argument("--lead_name", help="Nome do lead")
    parser.add_argument("--business_type", help="Tipo de negócio")
    parser.add_argument("--location", help="Cidade/Estado")
    parser.add_argument("--phone", help="WhatsApp do lead")
    parser.add_argument("--json", help="JSON string com lead_name, business_type, location, phone")
    parser.add_argument("--file", help="Arquivo JSON com array de leads")
    parser.add_argument("--output", help="Arquivo para salvar resultado")
    parser.add_argument("--model", help="Modelo a usar (default: usa model do SKILL.md)", default=None)
    return parser.parse_args()


def load_template():
    template_path = Path(__file__).parent.parent / "templates" / "prompt.txt"
    return template_path.read_text(encoding="utf-8")


def load_skill_config():
    """Lê model/temperature do SKILL.md frontmatter"""
    import yaml
    skill_md = Path(__file__).parent.parent / "SKILL.md"
    if skill_md.exists():
        content = skill_md.read_text(encoding="utf-8")
        if content.startswith("---"):
            _, frontmatter, _ = content.split("---", 2)
            config = yaml.safe_load(frontmatter)
            return config.get("model"), config.get("temperature", 0.7)
    return None, 0.7


def render_prompt(template, lead):
    return template.format(
        lead_name=lead.get("lead_name", ""),
        business_type=lead.get("business_type", ""),
        location=lead.get("location", ""),
        phone=lead.get("phone", "")
    )


def run_hermes(prompt, model=None, temperature=0.7):
    """Executa o Hermes via CLI.
    
    Nota: -t no hermes chat é para toolsets, não temperature.
    Temperature é lida do SKILL.md ou config.yaml.
    """
    skill_model, skill_temp = load_skill_config()
    model = model or skill_model or "auto"
    temperature = skill_temp  # usa do SKILL.md
    
    cmd = ["hermes", "chat", "-q", prompt, "-Q"]
    if model != "auto":
        cmd.extend(["-m", model])
    # -Q = quiet mode (apenas resposta final, sem banner/spinner)
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=180
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        # Diagnóstico comum: NVIDIA_API_KEY não configurada
        if "404" in stderr and "nvidia" in model.lower():
            raise RuntimeError(
                f"Modelo NVIDIA precisa de NVIDIA_API_KEY configurada.\n"
                f"Execute: hermes config set NVIDIA_API_KEY \"sua_chave\"\n"
                f"Ou use modelo que funcione com Nous Portal (ex: moonshotai/kimi-k2.6)\n"
                f"Erro original: {stderr}"
            )
        raise RuntimeError(f"Hermes falhou: {stderr}")
    return result.stdout.strip()


def main():
    args = parse_args()
    template = load_template()

    # Coleta leads
    leads = []

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
            leads = data if isinstance(data, list) else [data]
    elif args.json:
        leads = [json.loads(args.json)]
    elif all([args.lead_name, args.business_type, args.location, args.phone]):
        leads = [{
            "lead_name": args.lead_name,
            "business_type": args.business_type,
            "location": args.location,
            "phone": args.phone
        }]
    else:
        print("ERRO: Forneça --lead_name/--business_type/--location/--phone OU --json OU --file", file=sys.stderr)
        sys.exit(1)

    # Processa cada lead
    outputs = []
    for i, lead in enumerate(leads):
        prompt = render_prompt(template, lead)
        try:
            result = run_hermes(prompt, model=args.model)
            outputs.append(f"=== LEAD {i+1}: {lead.get('lead_name', 'Sem nome')} ===\n{result}")
        except Exception as e:
            outputs.append(f"=== LEAD {i+1}: {lead.get('lead_name', 'Sem nome')} ===\nERRO: {e}")

    final_output = "\n\n".join(outputs)

    if args.output:
        Path(args.output).write_text(final_output, encoding="utf-8")
        print(f"Salvo em: {args.output}")
    else:
        print(final_output)


if __name__ == "__main__":
    main()