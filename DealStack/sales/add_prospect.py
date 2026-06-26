# ============================================================
# FIX H03 - add_prospect.py: CSV Injection Fix
# ============================================================

#!/usr/bin/env python3
"""
Add Prospect - VERSÃO SEGURA
- Previne CSV Injection (Formula Injection)
- Validação de input com Pydantic
- Sanitização de campos perigosos
"""

import csv
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

# pip install pydantic
try:
    from pydantic import BaseModel, Field, field_validator, ValidationError
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

CSV_PATH = Path(__file__).with_name('prospects.csv')
FIELDS = ['nome', 'empresa', 'cargo', 'canal', 'status', 'data_contato', 'resposta', 'data_followup', 'notas']

# Caracteres perigosos no início de célula CSV/Excel
DANGEROUS_PREFIXES = ('=', '+', '-', '@', '\t', '\r', '\n')
MAX_FIELD_LENGTH = 500

class ProspectInput(BaseModel):
    """Schema para validação de prospect"""
    nome: str = Field(..., min_length=1, max_length=200)
    empresa: str = Field(..., min_length=1, max_length=200)
    cargo: str = Field(default="", max_length=100)
    canal: str = Field(default="", max_length=50)
    status: str = Field(default="pending", max_length=20)
    data_contato: Optional[str] = None
    resposta: str = Field(default="", max_length=500)
    data_followup: str = Field(default="", max_length=20)
    notas: str = Field(default="", max_length=1000)
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        allowed = ['pending', 'contacted', 'replied', 'negotiating', 'closed', 'lost']
        if v not in allowed:
            raise ValueError(f"Status deve ser um de: {allowed}")
        return v
    
    @field_validator('data_contato', 'data_followup')
    @classmethod
    def validate_date(cls, v):
        if v:
            try:
                datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                raise ValueError("Data deve estar no formato YYYY-MM-DD")
        return v or datetime.now().strftime('%Y-%m-%d')


def sanitize_csv_field(value: str) -> str:
    """
    Sanitiza campo para prevenir CSV Injection.
    
    TÉCNICAS:
    1. Prefixa com ' (apóstrofo) se começa com caractere perigoso
    2. Escapa aspas duplas dobrando (" -> "")
    3. Remove caracteres de controle
    4. Limita tamanho
    """
    if not isinstance(value, str):
        value = str(value)
    
    # Remove caracteres de controle (exceto tab, newline que o csv.writer trata)
    value = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', value)
    
    # Limita tamanho
    if len(value) > MAX_FIELD_LENGTH:
        value = value[:MAX_FIELD_LENGTH]
    
    # CSV Injection protection: prefixa com ' se começa com perigoso
    stripped = value.lstrip()
    if stripped and stripped[0] in DANGEROUS_PREFIXES:
        value = "'" + value
    
    return value


def add(prospect: dict):
    """Adiciona prospect ao CSV com sanitização"""
    # Valida e sanitiza
    try:
        validated = ProspectInput(**prospect)
        clean_data = validated.model_dump()
    except ValidationError as e:
        print(f"Erro de validação: {e}", file=sys.stderr)
        raise
    
    # Sanitiza todos os campos
    sanitized = {k: sanitize_csv_field(v) for k, v in clean_data.items()}
    
    # Garante que todas as colunas existem
    row = {k: sanitized.get(k, '') for k in FIELDS}
    
    file_exists = CSV_PATH.exists() and CSV_PATH.stat().st_size > 0
    with CSV_PATH.open('a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, quoting=csv.QUOTE_ALL)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
    
    print(f"Adicionado: {row.get('nome')} — {row.get('empresa')} ({row.get('canal')})")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Uso: python3 add_prospect.py --nome "Fulano" --empresa "X" --cargo "Y" --canal "LinkedIn" --status "pending"')
        sys.exit(0)
    
    args = sys.argv[1:]
    data = {}
    i = 0
    while i < len(args):
        if args[i].startswith('--'):
            key = args[i][2:]
            if i + 1 < len(args) and not args[i + 1].startswith('--'):
                data[key] = args[i + 1]
                i += 2
            else:
                data[key] = ''
                i += 1
        else:
            i += 1
    
    data.setdefault('status', 'pending')
    data.setdefault('data_contato', datetime.now().strftime('%Y-%m-%d'))
    
    try:
        add(data)
    except ValidationError as e:
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(1)