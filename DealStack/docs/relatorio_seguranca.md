# 📋 RELATÓRIO DE AUDITORIA DE SEGURANÇA - DealStack / OpnCld

**Data:** 2025-06-11  
**Auditor:** Hermes Agent (Cybersecurity Specialist)  
**Projeto:** DealStack - Sales Automation Engine  
**Escopo:** `/workspaces/OpnCld/` + Skills Hermes (`~/.hermes/skills/sales/`)

---

## 📊 RESUMO EXECUTIVO

| Severidade | Quantidade | Status |
|------------|------------|--------|
| 🔴 **CRÍTICO** | 6 | ❌ Não corrigido |
| 🟠 **ALTO** | 8 | ❌ Não corrigido |
| 🟡 **MÉDIO** | 7 | ❌ Não corrigido |
| 🟢 **BAIXO** | 5 | ❌ Não corrigido |
| **TOTAL** | **26** | — |

> ⚠️ **RISCO GERAL: ALTO** — O dashboard expõe APIs sensíveis sem autenticação, CORS aberto, e há múltiplos vetores de injeção. **Não deve ir para produção** sem correções.

---

## 🔴 VULNERABILIDADES CRÍTICAS

### C01 - Ausência Total de Autenticação/Autorização nas APIs
**Arquivo:** `sales-prospecting/server.py` (linhas 93-225)  
**Impacto:** Qualquer pessoa com acesso à porta 8765 pode:
- Ler todos os leads (`GET /api/leads`)
- Ler todas as propostas (`GET /api/proposals`)
- Injetar leads falsos (`POST /api/leads`)
- Injetar propostas falsas (`POST /api/proposals`)
- Gerar propostas arbitrárias (`POST /api/generate`)

**OWASP:** A01:2021 - Broken Access Control, A07:2021 - Identification and Authentication Failures

---

### C02 - CORS Totalmente Aberto (`Access-Control-Allow-Origin: *`)
**Arquivo:** `sales-prospecting/server.py` (linhas 82-87)  
**Código:**
```python
def end_headers(self):
    self.send_header('Access-Control-Allow-Origin', '*')  # ❌ PERIGOSO
    self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    self.send_header('Access-Control-Allow-Headers', 'Content-Type')
```

**Impacto:** Qualquer site malicioso pode fazer requisições AJAX para a API e exfiltrar dados de leads/propostas.

**OWASP:** A01:2021 - Broken Access Control, A05:2021 - Security Misconfiguration

---

### C03 - Injeção de Comando via `subprocess.run` com Dados do Usuário
**Arquivo:** `sales-prospecting/server.py` (linhas 31-51)  
**Código:**
```python
def run_hermes_proposal(lead_data: dict) -> str:
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump([lead_data], f, ensure_ascii=False)  # Dados do usuário no arquivo
        leads_file = f.name

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", leads_file],  # ⚠️ Argumento controlado
        capture_output=True, text=True, timeout=300, cwd=SKILL_DIR
    )
```

**Impacto:** Se `lead_data` contiver caracteres especiais que escapem do JSON, ou se o `SCRIPT` for manipulado via symlink, permite RCE.

**OWASP:** A03:2021 - Injection, A08:2021 - Software and Data Integrity Failures

---

### C04 - Path Traversal via `SimpleHTTPRequestHandler`
**Arquivo:** `sales-prospecting/server.py` (linhas 78-80, 106)  
**Código:**
```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, directory=str(SKILL_DIR), **kwargs)  # Serve arquivos do SKILL_DIR

# ...
else:
    super().do_GET()  # ❌ Permite acesso a qualquer arquivo no SKILL_DIR
```

**Impacto:** Requisição `GET /../../etc/passwd` ou `GET /scripts/run.py` expõe código fonte e arquivos sensíveis.

**OWASP:** A01:2021 - Broken Access Control, A05:2021 - Security Misconfiguration

---

### C05 - Exposição de Dados Sensíveis em Erros (Stack Traces)
**Arquivo:** `sales-prospecting/server.py` (linhas 170-171, 197-198, 224-225)  
**Código:**
```python
except Exception as e:
    self.send_json(500, {"error": str(e)})  # ❌ Vaza stack trace interno
```

**Impacto:** Erros revelam estrutura de arquivos, caminhos absolutos, versões de biblioteca, facilitando ataques direcionados.

**OWASP:** A09:2021 - Security Logging and Monitoring Failures

---

### C06 - Ausência de HTTPS / TLS
**Arquivo:** `sales-prospecting/server.py` (linha 239, 249)  
**Código:**
```python
port = 8765
server = HTTPServer(('0.0.0.0', port), SalesHandler)  # ❌ HTTP puro
```

**Impacto:** Tokens de API (Shopify, Meta), leads, propostas trafegam em texto plano. sniffing em rede local/Codespaces.

**OWASP:** A02:2021 - Cryptographic Failures

---

## 🟠 VULNERABILIDADES ALTAS

### H01 - Validação de Input Inexistente em `/api/generate`
**Arquivo:** `sales-prospecting/server.py` (linhas 154-171)  
**Código:**
```python
def handle_generate(self):
    body = self.rfile.read(content_length).decode('utf-8')
    lead = json.loads(body)  # ❌ Sem validação de schema
    required = ['lead_name', 'business_type', 'location', 'phone']
    if not all(k in lead for k in required):  # Apenas verifica existência
        ...
```

**Impacto:** Campos como `phone` aceitam qualquer string (XSS payload, SQL injection, comandos shell). `lead_name` pode conter scripts.

---

### H02 - JSON Injection / Template Injection no Content Factory
**Arquivo:** `content-factory/generate_content.py` (linhas 20-27)  
**Código:**
```python
def render(template_name: str, **context) -> str:
    tpl = load_template(template_name)
    try:
        return tpl.format(**context)  # ❌ .format() sem escaping
    except Exception as e:
        raise RuntimeError(f'Erro ao renderizar template: {e}')
```

**Impacto:** Se `context` vier de input do usuário, permite `{__import__('os').system('rm -rf /')}` ou acesso a atributos privados Python.

---

### H03 - CSV Injection (Formula Injection) em `add_prospect.py`
**Arquivo:** `sales/add_prospect.py` (linhas 9-16)  
**Código:**
```python
def add(prospect: dict):
    writer.writerow({k: prospect.get(k, '') for k in FIELDS})  # ❌ Sem sanitização
```

**Impacto:** Input `=cmd|' /C calc'!A0` em qualquer campo executa fórmula ao abrir no Excel/Sheets.

---

### H04 - Tokens de API em Variáveis de Ambiente sem `.env.example` / Validação
**Arquivos:** 
- `shopify-ops/shopify_ops.py` (linhas 22-25): `SHOPIFY_API_TOKEN`
- `meta-ops/meta_ops.py` (linhas 10-13): `META_ACCESS_TOKEN` / `META_ADS_TOKEN`
- `meta-ops/meta_campaign_manager.py` (linhas 16-19): `META_ACCESS_TOKEN`

**Impacto:** 
- Sem `.env.example` desenvolvedores cometem tokens reais
- Sem validação de formato (ex: `shpat_` prefixo Shopify)
- Tokens vazam em logs de erro (`SystemExit` mostra variável)

---

### H05 - Ausência de Rate Limiting nas APIs
**Arquivo:** `sales-prospecting/server.py` (todo o arquivo)  
**Impacto:** 
- Brute force em `/api/generate` (DoS via custos de LLM)
- Enumeração de leads via `/api/leads` repetido
- Flood de `POST /api/leads` para encher disco

---

### H06 - Headers de Segurança Ausentes
**Arquivo:** `sales-prospecting/server.py` (linhas 82-87, 121-123)  
**Headers faltando:**
| Header | Valor Recomendado | Proteção |
|--------|-------------------|----------|
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'` | XSS |
| `X-Frame-Options` | `DENY` | Clickjacking |
| `X-Content-Type-Options` | `nosniff` | MIME sniffing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Vazamento referrer |
| `Permissions-Policy` | `geolocation=(), microphone=()` | APIs sensíveis |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | HTTPS enforcement |

---

### H07 - Versão Desatualizada da Meta Graph API (v19.0)
**Arquivos:** 
- `meta-ops/meta_ops.py` (linha 7): `v19.0`
- `meta-ops/meta_campaign_manager.py` (linha 13): `v19.0`

**Impacto:** v19.0 deprecated em 2024. Meta remove suporte a versões antigas → quebra integração silenciosamente.

---

### H08 - Dados de Leads/Propostas em Arquivos JSON sem Controle de Acesso
**Arquivo:** `sales-prospecting/server.py` (linhas 21-25, 54-74)  
**Código:**
```python
SHARED_DATA_DIR = Path.home() / ".hermes" / "shared_data"
LEADS_FILE = SHARED_DATA_DIR / "jacarepagua_leads.json"
```

**Impacto:** 
- Permissões default do SO (geralmente 644) → qualquer usuário do sistema lê
- Dados PII (nome, telefone, endereço, negócio) expostos
- Sem criptografia em repouso

---

## 🟡 VULNERABILIDADES MÉDIAS

### M01 - CSRF Ausente em Endpoints de Escrita (POST)
**Arquivo:** `sales-prospecting/server.py` (linhas 108-117)  
**Impacto:** Formulário malicioso em site terceito pode fazer `POST /api/leads` ou `POST /api/proposals` sem consentimento do usuário logado (se houver auth no futuro).

---

### M02 - Logging de Segurança Inexistente
**Arquivo:** `sales-prospecting/server.py` (linha 233)  
**Código:**
```python
def log_message(self, fmt, *args):
    pass  # ❌ Silencia TUDO — inclusive ataques
```

**Impacto:** Impossível detectar:
- Tentativas de enumeração de endpoints
- Payloads maliciosos
- Acessos não autorizados
- Erros 4xx/5xx suspeitos

---

### M03 - `localStorage` Usado para Dados Sensíveis no Frontend
**Arquivo:** `sales-prospecting/dashboard.html` (linhas 430-433, 430-433)  
**Código:**
```javascript
function saveLocal() {
    localStorage.setItem('sales_leads', JSON.stringify(leads));
    localStorage.setItem('sales_proposals', JSON.stringify(proposals));
}
```

**Impacto:** 
- XSS rouba todos os leads/propostas
- Dados persistem após logout
- Acessível por qualquer script na mesma origem

---

### M04 - Falta de Validação de Tipos e Formatos (Phone, Email, URL)
**Arquivos:** 
- `sales-prospecting/server.py` (linha 159): apenas verifica existência
- `sales-prospecting/dashboard.html` (linhas 264, 286): inputs sem `pattern` ou validação JS

**Impacto:** Dados inconsistentes quebram pipeline, injetam lixo no CRM.

---

### M05 - Debug Endpoint Exposto: `/api/leads-example`
**Arquivo:** `sales-prospecting/server.py` (linhas 97-98)  
**Código:**
```python
elif parsed.path == '/api/leads-example':
    self.serve_json(SKILL_DIR / "references" / "leads-example.json")
```

**Impacto:** Vaza estrutura interna de dados, facilita engenharia reversa de payloads.

---

### M06 - Subprocess Timeout Excessivo (5 min = 300s)
**Arquivo:** `sales-prospecting/server.py` (linha 41)  
**Código:**
```python
result = subprocess.run(..., timeout=300, ...)  # 5 minutos!
```

**Impacto:** DoS fácil — 10 requisições paralelas travam o servidor por 50 min.

---

### M07 - Ausência de `requirements.txt` / `pyproject.toml` com Versões Fixas
**Projeto inteiro:** Sem arquivo de dependências.  
**Impacto:** 
- Builds não reprodutíveis
- Atualizações automáticas quebram código
- Vulnerabilidades em dependências transitivas não detectadas

---

## 🟢 VULNERABILIDADES BAIXAS

### L01 - Information Disclosure em Respostas de API
**Arquivo:** `sales-prospecting/server.py` (linhas 132-133, 136-137)  
**Código:**
```python
self.send_json(200, {"leads": leads, "count": len(leads), "source": "cronjob"})
```

**Impacto:** Campo `source: "cronjob"` vaza arquitetura interna.

---

### L02 - Ausência de `security.txt` / Política de Divulgação Responsável
**Projeto:** Não existe `.well-known/security.txt`  
**Impacto:** Pesquisadores não sabem como reportar vulns.

---

### L03 - Comentários em Código Revelam Estrutura Interna
**Arquivo:** `sales-prospecting/server.py` (linhas 21-28, 30-52)  
**Impacto:** Comentários como `# ===== ARQUIVO COMPARTILHADO PARA CRON JOB =====` ajudam atacante a entender fluxo.

---

### L04 - Falta de Validação de Tamanho de Payload (DoS via Payload Grande)
**Arquivo:** `sales-prospecting/server.py` (linha 155)  
**Código:**
```python
content_length = int(self.headers.get('Content-Length', 0))
body = self.rfile.read(content_length).decode('utf-8')  # ❌ Sem limite
```

**Impacto:** Request de 1GB+ causa OOM.

---

### L05 - User-Agent / Fingerprinting não Bloqueado
**Arquivo:** `shopify-ops/shopify_ops.py`, `meta-ops/*.py`  
**Impacto:** Requests usam `urllib` default User-Agent → fácil bloqueio por WAF, fingerprinting de ferramenta.

---

## 📈 MATRIZ DE RISCO POR ARQUIVO

| Arquivo | Crítico | Alto | Médio | Baixo | Total |
|---------|---------|------|-------|-------|-------|
| `sales-prospecting/server.py` | 4 | 4 | 4 | 3 | 15 |
| `sales-prospecting/dashboard.html` | 0 | 1 | 1 | 1 | 3 |
| `content-factory/generate_content.py` | 0 | 1 | 0 | 0 | 1 |
| `sales/add_prospect.py` | 0 | 1 | 0 | 0 | 1 |
| `shopify-ops/shopify_ops.py` | 0 | 1 | 0 | 1 | 2 |
| `meta-ops/meta_ops.py` | 0 | 1 | 0 | 0 | 1 |
| `meta-ops/meta_campaign_manager.py` | 0 | 1 | 0 | 0 | 1 |
| **TOTAL** | **4** | **9** | **5** | **5** | **23** |

> Nota: Alguns achados afetam múltiplos arquivos (contados uma vez por arquivo)

---

## ✅ CHECKLIST DE CORREÇÃO

- [ ] **C01** - Implementar autenticação JWT/API Key em todas as rotas `/api/*`
- [ ] **C02** - Restringir CORS a origins conhecidas (Codespaces URL + localhost)
- [ ] **C03** - Sanitizar input antes de `subprocess.run`, usar allowlist de comandos
- [ ] **C04** - Remover `super().do_GET()` fallback, servir apenas rotas explícitas
- [ ] **C05** - Logar erros internamente, retornar mensagens genéricas ao cliente
- [ ] **C06** - Adicionar suporte a TLS (certificados auto-assinados para dev, Let's Encrypt para prod)
- [ ] **H01** - Validar schema com `pydantic` ou `marshmallow` em todas as entradas
- [ ] **H02** - Usar `jinja2` com autoescape ou sanitizar `.format()` inputs
- [ ] **H03** - Prefixar campos CSV com `'` ou usar biblioteca `csv` com quoting
- [ ] **H04** - Criar `.env.example`, validar formato de tokens na inicialização
- [ ] **H05** - Implementar rate limiting (ex: `slowapi` ou middleware customizado)
- [ ] **H06** - Adicionar todos os headers de segurança via middleware
- [ ] **H07** - Atualizar Meta API para v20.0+ (verificar changelog)
- [ ] **H08** - Criptografar arquivos JSON em repouso (ex: `cryptography.fernet`)
- [ ] **M01** - Adicionar CSRF tokens (double-submit cookie) em POSTs
- [ ] **M02** - Implementar logging estruturado (JSON) com níveis de segurança
- [ ] **M03** - Migrar `localStorage` para `sessionStorage` ou IndexedDB com criptografia
- [ ] **M04** - Adicionar validação regex para telefone, email, URL no frontend e backend
- [ ] **M05** - Remover ou proteger `/api/leads-example` पीछे autenticação
- [ ] **M06** - Reduzir timeout subprocess para 60s, adicionar circuit breaker
- [ ] **M07** - Criar `requirements.txt` com `pip-tools` ou `poetry`, pinar versões
- [ ] **L01** - Remover campos internos de respostas públicas
- [ ] **L02** - Criar `.well-known/security.txt`
- [ ] **L03** - Remover comentários sensíveis de código de produção
- [ ] **L04** - Limitar `Content-Length` máximo (ex: 1MB)
- [ ] **L05** - Definir User-Agent customizado nas integrações HTTP

---

## 🎯 PRÓXIMOS PASSOS RECOMENDADOS (ORDEM DE PRIORIDADE)

1. **Imediato (antes de qualquer deploy):**
   - C01, C02, C04, C06 — Autenticação, CORS, Path Traversal, HTTPS
   - H01, H03 — Input validation, CSV injection

2. **Curto prazo (1 semana):**
   - C03, C05, H02, H05, H06, H08 — Command injection, error handling, template injection, rate limiting, headers, encryption at rest

3. **Médio prazo (2 semanas):**
   - H04, H07, M01-M06, L01-L05 — Secrets management, API versions, CSRF, logging, storage, validation, cleanup

4. **Contínuo:**
   - M07 — Dependency scanning semanal (`pip-audit`, `safety`, `dependabot`)
   - Pen test trimestral
   - Security training para time