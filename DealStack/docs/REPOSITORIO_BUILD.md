# Repositório /workspaces/OpnCld — tudo que foi construído até agora

- DealStack: app em produção no Render, dashboard em https://dealstack-m9re.onrender.com. Backend com API key, CORS restrito, rate limit, headers de segurança, Pydantic, SQLAlchemy e deploy via Render + Neon. Commit de hardening enviado.
- Sales Prospecting: dashboard estático em `sales-prospecting/dashboard.html` + API Python em `sales-prospecting/server.py` (porta 8765). Pipeline de prospecção gera propostas personalizadas por WhatsApp usando leads do Google Maps/OSM.
- pet-price-comparator: backend FastAPI/SQLAlchemy com problema em `app/core/config.py`; entrega confiável atual é o frontend em `frontend/index.html`.
- sales-video: landing page de vendas com vídeo, formulário de contato, seção de serviços e depoimentos.
- award-winning-website: site institucional estilo Awwwards, responsivo, com animações.
- meta-ops: scripts Python para gerenciar campanhas do Meta Ads.
- shopify-ops: script para operações com Shopify.
- content-factory: módulo de geração de conteúdo com templates para análise de loja, post LinkedIn e proposta Workana.
- scripts/security: série de 8 scripts de correção de segurança aplicados ao projeto.
- scripts/prospecting: pipeline unificado, extração de leads, geração de propostas integrando Neon DB.
- data/processed e data/propostas: leads processados e propostas geradas em texto.
- pipeline_output: exports JSON/txt de leads e propostas por local/data.
