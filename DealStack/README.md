# 🎯 SaleStack — Sistema Automatizado de Prospecção e Vendas

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/JWT-Auth-000000?style=flat-square&logo=jsonwebtokens&logoColor=white" alt="JWT"/>
  <img src="https://img.shields.io/badge/n8n-Automation-EA4C89?style=flat-square&logo=n8n&logoColor=white" alt="n8n"/>
  <img src="https://img.shields.io/badge/Stripe-Billing-635BFF?style=flat-square&logo=stripe&logoColor=white" alt="Stripe"/>
  <img src="https://img.shields.io/badge/Status-Production%20Ready-brightgreen?style=flat-square" alt="Status"/>
</p>

---

## O que é

O **SaleStack** gera leads qualificados automaticamente a partir do Google Maps, qualifica cada um com pontuação inteligente, e entrega propostas visuais prontas para fechar negócio — tudo em uma plataforma web multi-tenant com cobrança recorrente via Stripe.

> **Sem planilha, sem chute, sem perder tempo com lead frio.**

---

## Como funciona

```
🗺️  Extrai →  🤖  Qualifica →  📄  Converte
```

1. **🗺️ Extrai leads por região** — Informa bairro/cidade e categoria. O SaleStack busca no OpenStreetMap/Google Maps todos os negócios locais com telefone e dados de contato.

2. **🤖 Qualifica e pontua automaticamente** — Cada lead recebe uma nota de 0 a 100. Blacklist de nomes (shoppings, redes, clínicas) é bloqueada. Segmentos de alto valor (marcenarias, pet shops, restaurantes) ganham bônus. Leads sem telefone são penalizados.

3. **📄 Gera proposta visual personalizada** — Com 1 clique, o sistema monta uma página de vendas cinematográfica com identidade visual única: paleta de cores determinística por nome, fonte por segmento (Playfair para móveis, Poppins para moda, Nunito para saúde...) e tom de copy formal/casual/neutro.

---

## Funcionalidades

| Funcionalidade | Descrição |
|---|---|
| 📊 **Dashboard de gestão** | Kanban visual com filtros por status, produto e pontuação |
| 🗺️ **Extração por região** | Configura local, categoria, raio e limite de leads |
| 🎬 **Proposta visual por cliente** | Página de vendas única com tema, cores e tom automáticos |
| ✅ **Filtro de bons prospects** | "Mostrar todos" ou só leads com score ≥ 60 |
| 🚫 **Blacklist inteligente** | Shoppings, redes, clínicas, condomínios — tudo bloqueado automaticamente |
| 👥 **Multi-tenant** | Cada cliente tem workspace isolado com próprios leads e regiões |
| 📋 **Planos com limites** | Starter (100 leads), Pro (300), Agency (1000), Founder (ilimitado) |
| 💳 **Stripe integrado** | Checkout, assinatura recorrente, portal de pagamento, webhooks |
| 🔗 **Sistema de afiliação** | Link exclusivo, comissão 30% recorrente por indicação |
| 🔐 **JWT + controle por plano** | Login seguro, rotas protegidas, suspensão automática por falta de pagamento |
| 📤 **Exportar CSV** | Todos os leads filtrados exportados com 1 clique |
| 📱 **Proposta visual responsiva** | Funciona no celular, WhatsApp, desktop — com GSAP animations |

---

## Planos

| Plano | Preço | Leads/mês | Regiões | Usuários | White Label |
|---|---|---|---|---|---|
| **Starter** | R$ 97/mês | 100 | 1 | 1 | ❌ |
| **Pro** | R$ 197/mês | 300 | 3 | 3 | ❌ |
| **Agency** | R$ 497/mês | 1.000 | Ilimitadas | 10 | ✅ |
| **Founder** | R$ 997/mês | Ilimitados | Ilimitadas | 3 | ✅ |
| **Founder Vitalício** | R$ 2.497 único | Ilimitados | Ilimitadas | 3 | ✅ |

> Founder Vitalício: apenas **50 vagas** vitalícias — pagou uma vez, usa para sempre.

---

## Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| **Backend** | Python 3.11+, http.server (sem dependências pesadas) |
| **Autenticação** | JWT (HS256, 24h expiry) |
| **Banco** | JSON file-based (~/.hermes/shared_data) |
| **Frontend** | HTML + CSS + Vanilla JS (sem frameworks) |
| **Pagamentos** | Stripe (checkout, subscriptions, webhooks, portal) |
| **Automação** | n8n, cron jobs |
| **IA** | Claude AI (propostas visuais, qualificação) |
| **APIs** | OpenStreetMap Overpass API, Google Maps |
| **Animações** | GSAP (propostas visuais) |
| **Deploy** | Render, Docker, GitHub Codespaces |

---

## Estrutura do Projeto

```
├── sales-prospecting/
│   ├── server.py              ← Core do SaaS (1538 linhas)
│   ├── dashboard.html         ← Dashboard multitenant
│   ├── login.html             ← Login + cadastro com plano
│   ├── landing.html           ← Landing page com pricing
│   ├── sales.html             ← Template proposta visual
│   ├── data/                  ← Leads, propostas, dados brutos
│   ├── scripts/
│   │   ├── prospecting/       ← Pipeline de extração (OSM, Shopify)
│   │   └── security/          ← Scripts de hardening
│   ├── meta-ops/              ← Operações Meta Ads
│   ├── n8n-workflows/         ← Workflows n8n
│   └── shopify-ops/           ← Operações Shopify
├── landing-dealstack/         ← Landing page estática (fallback)
├── sales-video/               ← Frontend Vite/React (proposta visual)
├── content-factory/           ← Geração de conteúdo com IA
├── data/                      ← Leads e propostas processadas
├── scripts/
│   ├── deploy/                ← Scripts de deploy
│   └── prospecting/           ← Pipelines legados
└── .env.example               ← Template de variáveis de ambiente
```

---

## Como Rodar Localmente

### Pré-requisitos

- Python 3.11+
- Git
- (Opcional) Conta Stripe para receber pagamentos

### Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/matioli717/SaleStackv2.git
cd SaleStackv2/DealStack

# 2. Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env com suas chaves (veja tabela abaixo)

# 3. Instale dependências
pip install -r sales-prospecting/requirements.txt

# 4. Inicie o servidor
cd sales-prospecting && python3 server.py

# 5. Acesse
# Landing page: http://localhost:8765/
# Dashboard:    http://localhost:8765/dashboard
# Admin:        http://localhost:8765/admin
```

### Primeiro Acesso

| Função | Usuário | Senha |
|---|---|---|
| **Admin** | `admin` | Gerada na primeira execução (check o console) |

---

## Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `JWT_SECRET` | ✅ | Secret para assinar tokens JWT |
| `ADMIN_USERNAME` | ✅ | Nome de usuário admin (padrão: admin) |
| `ADMIN_PASSWORD` | ✅ | Senha do admin (se vazia, é gerada automaticamente) |
| `STRIPE_SECRET_KEY` | ❌ | Chave secreta do Stripe (sk_live_ ou sk_test_) |
| `STRIPE_PUBLISHABLE_KEY` | ❌ | Chave publicável do Stripe (pk_live_ ou pk_test_) |
| `STRIPE_WEBHOOK_SECRET` | ❌ | Signing secret do webhook Stripe (whsec_) |
| `ALLOWED_ORIGINS` | ❌ | Origens CORS permitidas (separadas por vírgula) |
| `API_KEYS` | ❌ | Chaves de API para integrações externas |
| `RATE_LIMIT_PER_MIN` | ❌ | Limite de requisições por minuto (padrão: 60) |
| `MAX_CONTENT_LENGTH` | ❌ | Tamanho máximo de payload (padrão: 1MB) |
| `SHARED_DATA_DIR` | ❌ | Diretório de dados compartilhados (padrão: ~/.hermes/shared_data) |

---

## Roadmap

- [x] Extração de leads do Google Maps/OSM
- [x] Dashboard com Kanban e filtros
- [x] Proposta visual cinematográfica por segmento
- [x] Filtro inteligente de bons prospects (score ≥ 60)
- [x] Blacklist automática (shoppings, redes, clínicas)
- [x] Paginação (25 leads/página)
- [x] Multi-tenant com workspaces isolados
- [x] Planos com limites por usuário
- [x] Stripe (checkout, assinatura, webhook, portal)
- [x] Sistema de afiliação com comissão 30%
- [x] Painel admin (MRR, bloqueio/ativação manual)
- [x] Landing page com pricing dinâmico
- [ ] App mobile (PWA)
- [ ] Integração WhatsApp Business API
- [ ] Métricas e relatórios avançados
- [ ] Importação de leads via CSV
- [ ] API pública para integrações

---

## 💰 Programa de Afiliados

Ganhe **30% de comissão recorrente** todo mês indicando o SaleStack.

**Como funciona:**
1. Você recebe um link exclusivo de afiliado
2. Compartilha com sua rede (clientes, grupos, redes sociais)
3. Cada assinante que entrar pelo seu link gera comissão **todo mês**
4. Acompanhe suas estatísticas no dashboard

> **Exemplo:** 10 indicações no plano Pro (R$ 197) = **R$ 591/mês** de comissão recorrente.

---

## Contato

📱 **WhatsApp:** [Clique aqui para falar conosco](https://wa.me/5521999999999)

💻 **Assinar agora:** Acesse a [landing page](http://localhost:8765/) e escolha seu plano

---

<p align="center">
  <strong>Feito com 🤖 IA + ☕ café em Jacarepaguá, Rio de Janeiro</strong>
</p>

<p align="center">
  <a href="https://github.com/matioli717/SaleStackv2/stargazers"><img src="https://img.shields.io/github/stars/matioli717/SaleStackv2?style=social" alt="Stars"/></a>
  <a href="https://github.com/matioli717/SaleStackv2/forks"><img src="https://img.shields.io/github/forks/matioli717/SaleStackv2?style=social" alt="Forks"/></a>
</p>
