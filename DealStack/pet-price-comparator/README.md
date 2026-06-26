# PetPrice Comparador

Comparador de preços de rações e medicamentos pet + rede de parceiro local que cobre o menor preço com entrega grátis no mesmo dia em Jacarepaguá e Barra da Tijuca (RJ).

## Stack

| Camada | Tech |
|--------|------|
| **Backend** | FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL + Redis |
| **Frontend** | Next.js 14 (App Router) + React 18 + Tailwind CSS + TanStack Query |
| **Scraping** | Playwright (Chromium) |
| **Queue/Jobs** | ARQ (Redis) |
| **Deploy** | Docker Compose (dev) |

## Estrutura

```
pet-price-comparator/
├── backend/                 # FastAPI API
│   ├── app/
│   │   ├── api/routes/      # Endpoints REST
│   │   ├── core/            # Config, security
│   │   ├── db/              # Database setup
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   └── scrapers/        # Playwright scrapers
│   ├── alembic/             # Migrations
│   ├── scripts/             # Seed, utils
│   └── requirements.txt
├── frontend/                # Next.js App
│   ├── src/
│   │   ├── app/             # Pages (App Router)
│   │   ├── components/      # React components
│   │   ├── lib/             # API client, utils
│   │   └── hooks/           # Custom hooks
│   └── package.json
├── docker-compose.yml
└── README.md
```

## API Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/products` | Lista produtos (filtros: category, brand, search) |
| GET | `/api/v1/products/{id}` | Detalhe do produto |
| GET | `/api/v1/products/{id}/prices` | Histórico de preços |
| GET | `/api/v1/compare/{gtin}` | Comparação completa por GTIN |
| GET | `/api/v1/compare/search/?q=...` | Busca + comparação múltipla |
| POST | `/api/v1/cover-requests` | Solicita cobertura do parceiro |
| GET | `/api/v1/cover-requests` | Lista solicitações (filtros: status, neighborhood) |
| GET | `/api/v1/cover-requests/{id}` | Detalhe solicitação |
| PATCH | `/api/v1/cover-requests/{id}` | Atualiza status (parceiro) |
| POST | `/api/v1/cover-requests/{id}/accept` | Parceiro aceita + checkout URL |
| POST | `/api/v1/cover-requests/{id}/reject` | Parceiro recusa |

## Desenvolvimento

### Pré-requisitos
- Docker + Docker Compose
- Ou: Python 3.12, Node 20, PostgreSQL 16, Redis 7

### Subir tudo (Docker)

```bash
docker-compose up -d --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Docs (Swagger): http://localhost:8000/docs
- PostgreSQL: localhost:5432 (postgres/postgres)
- Redis: localhost:6379

### Popular banco com dados de teste

```bash
docker-compose exec backend python scripts/seed.py
```

### Desenvolvimento local (sem Docker)

**Backend:**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # ajuste se necessário
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Fluxo Principal

1. **Usuário busca** produto (nome, GTIN, categoria)
2. **API compara** preços em Petlove, Cobasi, Petz, Amazon
3. **Calcula target** = melhor preço online × 0.95 (8% comissão + margem)
4. **Usuário clica** "Pedir cobertura do parceiro"
5. **Sistema cria** `CoverRequest` com target_price
6. **Parceiro notificado** (WhatsApp/webhook) → aceita/recusa
7. **Se aceito** → gera link checkout whitelabel
8. **Usuário finaliza** compra com parceiro local

## Modelo de Dados Resumido

```sql
products (gtin, name, brand, category, subcategory, weight_kg)
prices (product_id, retailer, price_cents, in_stock, captured_at)
cover_requests (product_id, neighborhood, target_price_cents, best_online_price_cents, status, checkout_url)
```

## Variáveis de Ambiente (Backend)

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `DATABASE_URL` | PostgreSQL async | `postgresql+asyncpg://postgres:postgres@localhost:5432/pet_comparator` |
| `REDIS_URL` | Redis | `redis://localhost:6379/0` |
| `PARTNER_WHATSAPP_NUMBER` | WhatsApp do parceiro | - |
| `PARTNER_COMMISSION_PCT` | Comissão plataforma | `0.08` (8%) |
| `PARTNER_MIN_MARGIN_PCT` | Margem mínima parceiro | `0.05` (5%) |

## Próximos Passos

- [ ] Implementar scrapers (Playwright) para 4 varejistas
- [ ] Job agendado (ARQ) para coleta 4x/dia
- [ ] Webhook WhatsApp (n8n / Evolution API) para notificar parceiro
- [ ] Página de checkout whitelabel
- [ ] Dashboard parceiro (leads, conversão, GMV)
- [ ] Testes E2E (Playwright)
- [ ] CI/CD (GitHub Actions)