# ============================================================
# FIX H02 - generate_content.py: Template Injection Fix
# Substitua: /workspaces/OpnCld/content-factory/generate_content.py
# ============================================================

#!/usr/bin/env python3
"""
Content Factory - VERSÃO SEGURA
- Usa Jinja2 com autoescape (previne template injection)
- Validação de input com Pydantic
- Sanitização de contexto
"""

import argparse
import json
import html
import re
from pathlib import Path
from typing import Dict, Any, Optional

# pip install jinja2 pydantic
try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from jinja2.sandbox import SandboxedEnvironment
    JINJA_AVAILABLE = True
except ImportError:
    JINJA_AVAILABLE = False

try:
    from pydantic import BaseModel, Field, field_validator, ValidationError
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

TEMPLATES_DIR = Path(__file__).with_name('templates')
TEMPLATES_DIR.mkdir(exist_ok=True)

# ============================================================
# VALIDAÇÃO DE INPUT
# ============================================================

class RenderContext(BaseModel):
    """Schema para contexto de renderização"""
    # Campos permitidos - definidos explicitamente
    lead_name: Optional[str] = Field(None, max_length=200)
    business_type: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=20)
    company_name: Optional[str] = Field(None, max_length=200)
    contact_name: Optional[str] = Field(None, max_length=100)
    product: Optional[str] = Field(None, max_length=50)
    custom_fields: Dict[str, str] = Field(default_factory=dict)
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v:
            cleaned = "".join(c for c in v if c.isdigit() or c in "+-() ")
            if len(cleaned.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")) < 8:
                raise ValueError("Telefone inválido")
        return v
    
    @field_validator("custom_fields")
    @classmethod
    def validate_custom_fields(cls, v):
        # Limita tamanho e sanitiza valores
        sanitized = {}
        for k, val in v.items():
            if len(k) > 50:
                continue
            if isinstance(val, str) and len(val) > 500:
                val = val[:500]
            sanitized[k] = html.escape(str(val)) if val else ""
        return sanitized


# ============================================================
# TEMPLATE ENGINE SEGURO (Jinja2 com Autoescape + Sandbox)
# ============================================================

def get_template_env() -> "Environment":
    """Cria ambiente Jinja2 seguro"""
    if JINJA_AVAILABLE:
        # SandboxedEnvironment previne acesso a `__class__`, `__subclasses__`, etc
        env = SandboxedEnvironment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(['html', 'xml', 'md', 'txt']),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True
        )
        # Filtros customizados seguros
        env.filters['sanitize'] = lambda x: html.escape(str(x)) if x else ""
        env.filters['truncate_safe'] = lambda x, n=500: (str(x)[:n] + '...') if len(str(x)) > n else str(x)
        return env
    else:
        raise RuntimeError("Jinja2 não instalado. pip install jinja2")


# Cache do ambiente
_template_env = None

def load_template(name: str) -> str:
    """Carrega template raw (para compatibilidade)"""
    p = TEMPLATES_DIR / f'{name}.md'
    if not p.exists():
        return ""
    return p.read_text(encoding='utf-8')


def render(template_name: str, **context) -> str:
    """
    Renderiza template com Jinja2 seguro.
    
    Proteções:
    - Autoescape habilitado por padrão
    - Sandbox impede acesso a objetos perigosos
    - Contexto validado via Pydantic
    - Variáveis não definidas retornam string vazia (não erro)
    """
    # Valida contexto
    try:
        validated_ctx = RenderContext(**context)
        safe_context = validated_ctx.model_dump(exclude_none=True)
    except Exception as e:
        raise ValueError(f"Contexto inválido: {e}")
    
    if JINJA_AVAILABLE:
        global _template_env
        if _template_env is None:
            _template_env = get_template_env()
        
        try:
            template = _template_env.get_template(f'{template_name}.md')
            return template.render(**safe_context)
        except Exception as e:
            raise RuntimeError(f"Erro ao renderizar template '{template_name}': {e}")
    else:
        # Fallback seguro sem Jinja2 (usa .format com sanitização)
        tpl = load_template(template_name)
        if not tpl:
            raise FileNotFoundError(f'Template `{template_name}` não encontrado')
        
        # Sanitiza todos os valores antes do .format
        safe_format_ctx = {k: html.escape(str(v)) for k, v in safe_context.items()}
        try:
            return tpl.format(**safe_format_ctx)
        except Exception as e:
            raise RuntimeError(f'Erro ao renderizar template: {e}')


def list_templates() -> list:
    return [p.stem for p in TEMPLATES_DIR.glob('*.md')]


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command')
    ls = sub.add_parser('list')
    gn = sub.add_parser('render')
    gn.add_argument('--template', required=True)
    gn.add_argument('--context', required=True, help='JSON string com variáveis')
    
    args = parser.parse_args()
    
    if args.command == 'list':
        for t in list_templates():
            print(t)
    elif args.command == 'render':
        try:
            ctx = json.loads(args.context)
            print(render(args.template, **ctx))
        except ValidationError as e:
            print(f"Erro de validação: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Erro: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == '__main__':
    import sys
    main()