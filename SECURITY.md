# Política de Segurança - SaleStack / DealStack

## Reporting a Vulnerability

Se você descobrir uma vulnerabilidade de segurança no SaleStack, por favor
reporte imediatamente enviando um email para **security@dealstack.io**.

**NÃO abra uma Issue pública para vulnerabilidades de segurança.**

Esperamos receber seu relatório e responder em até 48 horas com um plano de ação.

## Escopo

Este documento cobre todos os componentes do SaleStack:

- `DealStack/sales-prospecting/server.py` — Servidor principal (HTTP API + Dashboard)
- `DealStack/sales-prospecting/neon_db.py` — Camada de banco PostgreSQL
- `DealStack/sales-prospecting/scripts/prospecting/` — Scripts de prospecção
- `DealStack/pet-price-comparator/` — Comparador de preços pet
- `DealStack/shopify-ops/` — Operações Shopify
- `DealStack/sales-video/` — Landing page de vendas
- `DealStack/sales/` — Scripts auxiliares de vendas
- `scripts/` e `tests/` — Scripts de suporte e testes

## Critical Security Measures

### 1. Senhas e Autenticação

- **Hashing**: Senhas são armazenadas com **bcrypt** (custo 12) — NUNCA SHA-256
- **Força mínima de senha**: 8 caracteres, 1 dígito, 1 maiúscula, 1 minúscula
- **Rate limiting de login**: Máximo de 5 tentativas em 5 minutos
- **Rate limit geral**: Configurável via `RATE_LIMIT_PER_MIN` (padrão: 60/min)

### 2. API Keys

- API Keys são armazenadas no ambiente ou `.env` — NUNCA hardcoded
- Formato: `ds_<token_urlsafe(48)>` (64 caracteres, alta entropia)
- API Keys são validadas via HMAC-SHA256 (comparação em tempo constante)
- Rotação: Recomendada a cada 90 dias

### 3. JWT (JSON Web Tokens)

- Algoritmo: **HS256**
- Expiração: 24 horas
- Validação de assinatura obrigatória em todas as rotas protegidas
- Secret deve ter no mínimo 64 caracteres hexadecimais (32 bytes)

### 4. HTTP Security Headers

| Header | Valor |
|--------|-------|
| Content-Security-Policy | `default-src 'self'; ...; report-uri /api/csp-report` |
| X-Frame-Options | `DENY` |
| X-Content-Type-Options | `nosniff` |
| Strict-Transport-Security | `max-age=31536000; includeSubDomains` |
| Referrer-Policy | `strict-origin-when-cross-origin` |
| Permissions-Policy | `geolocation=(), microphone=(), camera=()` |

### 5. CORS

- Origens permitidas são explicitamente configuradas via `ALLOWED_ORIGINS`
- NUNCA use `*` em produção
- Credentials são enviados apenas para origens na lista de permissões

### 6. Stripe Payments

- Webhook Stripe valida assinatura via `stripe.Webhook.construct_event()`
- Valores de plano são definidos no servidor — NEM o cliente pode alterá-los
- Chaves test/live separadas por ambiente

### 7. Proteção de Dados

- Multi-tenant: leads são isolados por `tenant_id`
- Senhas NUNCA são logadas ou retornadas em responses
- Dados sensíveis (Authorization, X-API-Key) são sanitizados nos logs
- Arquivos `.env` NUNCA são commitados (protegidos via `.gitignore`)

### 8. SQL Injection

- Todas as queries PostgreSQL usam **parameterized queries** (`%s`)
- NENHUMA query usa concatenação de strings com input do usuário

## Deployment Checklist

Antes de qualquer deploy em produção:

- [ ] `JWT_SECRET` gerado com `secrets.token_hex(32)`
- [ ] `ADMIN_PASSWORD` com 16+ caracteres (maiúsculas, minúsculas, dígitos, especiais)
- [ ] `API_KEYS` geradas com `ds_` + `secrets.token_urlsafe(48)`
- [ ] `ALLOWED_ORIGINS` configurada com a URL exata do deployment
- [ ] `STRIPE_SECRET_KEY` e `STRIPE_WEBHOOK_SECRET` configurados
- [ ] `DEBUG=False` (pet-price-comparator)
- [ ] HTTPS configurado (reverse proxy com nginx/Caddy/Cloudflare)
- [ ] Dependências atualizadas: `pip install -r requirements.txt`
- [ ] Portas de desenvolvimento desabilitadas em produção

## Vulnerabilidades Conhecidas e Mitigações

### Resolvidas nesta auditoria (Junho 2026)

| ID | Severidade | Descrição | Correção |
|----|-----------|-----------|----------|
| C-01 | CRÍTICA | Senhas com SHA-256 (sem salt/bcrypt) | Migrado para bcrypt (custo 12) |
| C-02 | CRÍTICA | API key com prefixo `sk_live_` hardcoded | Removida; .env agora exige chave via `secrets` |
| A-01 | ALTA | CORS default para `*` | Agora requer `ALLOWED_ORIGINS` explícita |
| A-02 | ALTA | Pipeline sem auth no dashboard | Adicionado header `X-API-Key` |
| A-03 | ALTA | JWT_SECRET fraco | Startup validará fraqueza; .env.example orienta |
| A-04 | ALTA | Pet-price-comparator CORS=`*` + DEBUG | CORS restrito; DEBUG=False; SECRET_KEY removida |
| A-05 | ALTA | URL hardcoded de deploy antigo (Render) | Substituído por env var |
| M-01 | MÉDIA | Senha mínima 6 chars, sem complexidade | Agora 8 chars + dígito + maiúscula + minúscula |
| M-02 | MÉDIA | .gitignore incompleto | Cobertura expandida (pem, key, csv, db, etc.) |
| M-03 | MÉDIA | Logs expõem tokens | Sanitização de Authorization/X-API-Key |
| M-04 | MÉDIA | CSP sem report-uri | Adicionado `report-uri /api/csp-report` |
| M-05 | MÉDIA | Dev key hardcoded em scripts security | Substituído por token gerado |

## Dependências Seguras

As seguintes bibliotecas são utilizadas para segurança:

- `bcrypt>=4.1.0` — Hashing de senhas
- `cryptography>=41.0.0` — Criptografia em repouso
- `python-dotenv>=1.0.0` — Carregamento seguro de variáveis de ambiente
- `pydantic>=2.5.0` — Validação rigorosa de inputs
- `psycopg[pool]>=3.3.0` — Conexão PostgreSQL com parameterized queries
- `jwt` (PyJWT) — JSON Web Token com HS256

## Contato

- **Email**: security@dealstack.io
- **GitHub Issues**: Para bugs não relacionados a segurança
- **Resposta esperada**: 48 horas para vulnerabilidades críticas
