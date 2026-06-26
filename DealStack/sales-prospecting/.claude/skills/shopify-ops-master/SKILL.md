---
name: shopify-ops-master
description: Operações Shopify: catálogo, estoque, preço, SEO, GraphQL, bulk ops, scripts prontos para usar.
---

# Shopify Ops Master

Use esta skill para operar Shopify de forma rápida e reprodutível.

## Scripts incluídos

`/workspaces/OpnCld/shopify-ops/shopify_ops.py`
- export-catalog: exporta catálogo para CSV
  Ex.: SHOPIFY_STORE_DOMAIN="sua-loja" SHOPIFY_API_TOKEN="token" python3 shopify_ops.py export-catalog --out catalog.csv

## Queries GraphQL úteis

### Inventário por variante
```graphql
query {
  productVariants(first: 250) {
    edges {
      node {
        id
        inventoryQuantity
        sku
        product { title }
      }
    }
  }
}
```

### Produtos com imagem e status
```graphql
query {
  products(first: 50) {
    edges {
      node {
        title
        status
        productType
        vendor
        variants(first: 5) { nodes { price inventoryQuantity sku } }
      }
    }
  }
}
```

## Checklist de operação semanal
- [ ] Catálogo com status publicado e preço atualizado
- [ ] Estoque mapeado no Shopify e sincronizado com Sheets
- [ ] Coleções e tags de SEO revisadas
- [ ] Checkout e formas de pagamento ativas
