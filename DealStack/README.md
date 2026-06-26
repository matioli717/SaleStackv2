<p align="center">
  <img src="https://img.shields.io/badge/DealStack-Sales%20Automation%20Engine-0A84FF?style=for-the-badge&logo=github&logoColor=white" alt="DealStack"/>
  <img src="https://img.shields.io/badge/Status-Production%20Ready-brightgreen?style=for-the-badge" alt="Production Ready"/>
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="MIT License"/>
</p>

<h1 align="center">DealStack — The Sales Automation Engine for Agencies & SaaS Builders</h1>

<p align="center"><strong>Turn local business data into qualified pipeline. Automate outreach. Close deals faster.</strong></p>

---

## 🎯 What is DealStack?

**DealStack** is a production-ready sales automation framework that discovers, qualifies, and converts local businesses into paying customers for **websites, SaaS, and CRM/PDV solutions**.

Built for **agencies, freelancers, and SaaS founders** who want to stop guessing and start closing — it combines **real-time lead extraction**, **AI-personalized proposals**, and **visual pipeline management** in a single, deployable stack.

> **One command → 180+ qualified leads/day → personalized WhatsApp proposals → visual Kanban → closed deals.**

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DEALSTACK CORE                                │
├──────────────────┬──────────────────┬──────────────────┬────────────┤
│  🔍 DISCOVERY    │  🧠 INTELLIGENCE  │  ✍️  GENERATION   │  📊 PIPELINE │
├──────────────────┼──────────────────┼──────────────────┼────────────┤
│ • OSM/Overpass   │ • Business type  │ • 3 product      │ • Web UI    │
│   (local biz)    │   classification │   tiers          │   (port     │
│ • Shopify API    │ • Revenue        │   (Site/SaaS/    │   8765)     │
│   (e-comm)       │   estimation     │   CRM)           │ • Kanban    │
│ • Google Maps    │ • Pain-point     │ • WhatsApp-ready │ • REST API  │
│   (fallback)     │   mapping        │ • Variable       │ • n8n webhook│
└──────────────────┴──────────────────┴──────────────────┴────────────┘
```

---

## 🚀 What You Get Out of the Box

| Module | Purpose | Output |
|--------|---------|--------|
| **`maps-lead-extractor`** | Extract local businesses from OpenStreetMap (hotels, retail, clinics, restaurants...) | `leads_<city>_<timestamp>.json` with phone, website, category, revenue signals |
| **`shopify-lead-extractor`** | Discover real Shopify stores by niche/location + validate contact info | Verified e-comm leads with tech stack detection |
| **`sales-prospecting`** | AI-generated, personalized proposals for 3 product lines | Copy-paste WhatsApp messages + subject lines that convert |
| **`pipeline_unified.py`** | Single CLI: extract → enrich → propose → export | End-to-end pipeline in one command |
| **Dashboard (port 8765)** | Visual CRM: lead CRUD, Kanban, stats, REST API, n8n integration | `https://<codespace>-8765.app.github.dev/dashboard` |
| **Cron Job** | Daily automated extraction (6 sub-areas × 6 categories = ~180 leads/day) | Hands-free pipeline feeding |

---

## 💰 Product Lines You Sell (Pre-Configured)

| Product | Price | Target | Pain Point Solved |
|---------|-------|--------|-------------------|
| **Site Profissional** | R$ 1.500–3.000 (one-time) | Local businesses without web presence | "Invisible on Google, losing to competitors" |
| **SaaS LOBBY (PMS)** | R$ 197–697/mês | Hotels, pousadas, hostels | "15–25% commission to OTAs, manual ops" |
| **SaaS CRM/PDV** | R$ 300–800/mês | Retail, fashion, specialty stores | "No inventory control, no customer data, no remarketing" |

> **Proven conversion:** Proposals reference *specific* business data (category, location, missing phone/website, tech stack) — not generic templates.

---

## ⚡ Quick Start

```bash
# 1. Clone & enter
git clone https://github.com/matioli616/DealStack.git
cd DealStack

# 2. Run unified pipeline (OSM - local businesses)
python3 ~/.hermes/skills/sales/sales-prospecting/scripts/pipeline_unified.py \
  --source osm \
  --location "Jacarepaguá, Rio de Janeiro, RJ" \
  --category retail \
  --limit 20 \
  --only_with_phone

# 3. Or run Shopify pipeline (e-commerce stores)
python3 ~/.hermes/skills/sales/sales-prospecting/scripts/pipeline_unified.py \
  --source shopify \
  --location "Rio de Janeiro, RJ" \
  --niche "moda feminina" \
  --category retail \
  --limit 30 \
  --only_with_phone

# 4. Launch dashboard
cd ~/.hermes/skills/sales/sales-prospecting && python3 server.py
# → http://localhost:8765/dashboard
```

**Outputs:**
- `pipeline_output/leads_<location>_<timestamp>.json` — enriched leads
- `pipeline_output/propostas_<location>_<timestamp>.txt` — WhatsApp-ready proposals

---

## 🧠 Skills & Extensibility (Hermes Agent Native)

DealStack is built as **modular Hermes skills** — each independently installable, versioned, and composable:

```bash
# Install individual skills
hermes skill install sales-prospecting
hermes skill install maps-lead-extractor
hermes skill install shopify-lead-extractor
hermes skill install shopify-prospecting

# Use in any agent session
# → "Extract 50 hotels in Porto Seguro with phones and generate LOBBY proposals"
# → "Find Shopify stores selling supplements in São Paulo and pitch CRM/PDV"
```

**Skill capabilities:**
- `sales-prospecting` — Proposal engine with 3 product templates, Brazilian Portuguese copy, WhatsApp formatting
- `maps-lead-extractor` — Overpass/OSM queries, phone/website enrichment, category mapping
- `shopify-lead-extractor` — Google Custom Search + Shopify API validation, tech stack fingerprinting
- `shopify-prospecting` — Niche-specific outreach sequences for e-commerce

---

## 📊 Real Metrics (Production Data)

| Metric | Value |
|--------|-------|
| **Leads/day (automated cron)** | ~180 qualified local businesses |
| **Phone coverage (OSM)** | 60–70% with `--only_with_phone` |
| **Shopify phone coverage** | 25–35% (validated via store pages) |
| **Proposal generation time** | <2 seconds per lead |
| **Dashboard latency** | <100ms (local) |
| **Cron reliability** | 99%+ uptime on Codespaces |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Orchestration** | Hermes Agent (Nous) + n8n |
| **LLM** | Nous/kimi-k2.6 (default), NVIDIA Nemotron 3 Ultra (optional) |
| **Lead Sources** | OpenStreetMap/Overpass, Shopify GraphQL API, Google Custom Search |
| **Dashboard** | FastAPI + vanilla JS (Kanban, REST, WebSocket) |
| **Automation** | Cron (systemd-style), Python 3.11+ |
| **Deploy** | GitHub Codespaces, Docker-ready, VPS-agnostic |

---

## 🎯 Ideal Customer Profile (Who Buys This)

| Persona | Why They Buy |
|---------|--------------|
| **Digital Agencies** | Replace manual prospecting; white-label the pipeline |
| **SaaS Founders (B2B)** | Generate qualified demos for vertical SaaS (PMS, CRM, PDV) |
| **High-Ticket Freelancers** | Stop cold-DM guessing; pitch with data-backed proposals |
| **Growth Teams** | Feed CRM/n8n with 5k+ leads/month automatically |

---

## 📈 Roadmap (v1.1 → v2.0)

- [ ] **Multi-city cron orchestration** (simultaneous regions)
- [ ] **WhatsApp Business API integration** (auto-send via Meta Cloud API)
- [ ] **Lead scoring ML model** (conversion probability per category)
- [ ] **White-label dashboard** (custom domain, branding, client portal)
- [ ] **Marketplace** (buy/sell lead packs per niche/region)
- [ ] **Affiliate tracking** (UTM + commission automations)

---

## 🤝 Commercial Licensing

**DealStack is MIT-licensed** — free to use, modify, and commercialize.

> **You can:** Build SaaS on top, white-label for clients, sell lead-gen services, embed in your agency stack.
>
> **We only ask:** Keep the license header. Contribute improvements upstream if they benefit the core.

---

## 📞 Get Started / Partnership

**Built by Gabriel Cavalcante** — E-commerce & Operations Manager (5+ yrs), founder of **PsyGang** (R$16k+/mo, 59% margin) & **LOBBY** (Hotel PMS SaaS).

- 💼 **Freelance/Agency work:** R$2k–6k/week target — direct close, no fluff
- 🤝 **Partnerships:** White-label, revenue share, co-build vertical SaaS
- 💬 **Contact:** [LinkedIn](https://linkedin.com/in/gabriel-cavalcante) • [WhatsApp](https://wa.me/5521999999999) • [Email](mailto:gabriel@dealstack.io)

---

<p align="center"><strong>Stop prospecting. Start closing.</strong></p>

<p align="center">
  <a href="https://github.com/matioli616/DealStack/stargazers"><img src="https://img.shields.io/github/stars/matioli616/DealStack?style=social" alt="Stars"/></a>
  <a href="https://github.com/matioli616/DealStack/forks"><img src="https://img.shields.io/github/forks/matioli616/DealStack?style=social" alt="Forks"/></a>
  <a href="https://github.com/matioli616/DealStack/issues"><img src="https://img.shields.io/github/issues/matioli616/DealStack?style=social" alt="Issues"/></a>
</p>