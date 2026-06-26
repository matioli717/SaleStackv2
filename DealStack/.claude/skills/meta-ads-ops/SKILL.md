---
name: meta-ads-ops
description: Meta Ads: campanhas, criativos, otimização, relatórios automatizados, scripts Python prontos.
---

# Meta Ads Ops

Use esta skill para gerenciar campanhas, medir desempenho e automatizar relatórios.

## Scripts incluídos

`/workspaces/OpnCld/meta-ops/meta_ads_reporter.py`
- python3 meta_ads_reporter.py account-id --token TOKEN --out report.csv
- Gera CSV com métricas de desempenho para análise rápida.

## Métricas obrigatórias
- ROAS
- CPA
- CTR
- CPM
- Frequency

## Regra de otimização
- Criativo fraco (CTR < 1% ou ROAS < 1.2): pausar em até 24h.
- Escala com ROAS >= 2.5 e CPA abaixo da meta.
