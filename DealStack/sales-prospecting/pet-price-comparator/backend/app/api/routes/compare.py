from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.models.product import Product, Price, Retailer
from app.schemas.product import PriceComparison, PriceRead, ProductRead
from app.core.config import settings

router = APIRouter(prefix="/compare", tags=["compare"])

PARTNER_COMMISSION_PCT = settings.PARTNER_COMMISSION_PCT
PARTNER_MIN_MARGIN_PCT = settings.PARTNER_MIN_MARGIN_PCT


@router.get("/{gtin}", response_model=PriceComparison)
async def compare_product(gtin: str, db: AsyncSession = Depends(get_db)):
    # Busca produto por GTIN
    result = await db.execute(select(Product).where(Product.gtin == gtin))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Busca preços atuais (mais recente por varejista)
    stmt = (
        select(Price)
        .where(Price.product_id == product.id, Price.in_stock == True)
        .distinct(Price.retailer)
        .order_by(Price.retailer, Price.captured_at.desc())
    )
    result = await db.execute(stmt)
    prices = result.scalars().all()

    if not prices:
        raise HTTPException(status_code=404, detail="No prices available")

    # Separa preço do parceiro local dos online
    partner_price = None
    online_prices = []
    for p in prices:
        if p.retailer == Retailer.PARCEIRO_LOCAL:
            partner_price = p
        else:
            online_prices.append(p)

    if not online_prices:
        raise HTTPException(status_code=404, detail="No online prices for comparison")

    # Melhor preço online
    best_online = min(online_prices, key=lambda p: p.price_cents)

    # Target price = melhor online * (1 - comissão)
    target_price_cents = int(best_online.price_cents * (1 - PARTNER_COMMISSION_PCT))

    # Verifica se parceiro pode cobrir com margem mínima
    can_cover = True
    if partner_price:
        min_viable_price = int(best_online.price_cents * (1 - PARTNER_MIN_MARGIN_PCT))
        can_cover = partner_price.price_cents <= min_viable_price

    savings_cents = best_online.price_cents - target_price_cents
    savings_pct = (savings_cents / best_online.price_cents) * 100

    return PriceComparison(
        product=ProductRead.model_validate(product),
        best_online_price=PriceRead.model_validate(best_online),
        all_prices=[PriceRead.model_validate(p) for p in prices],
        target_price_cents=target_price_cents,
        savings_cents=savings_cents,
        savings_pct=round(savings_pct, 1),
        partner_price_cents=partner_price.price_cents if partner_price else None,
        can_cover=can_cover,
    )


@router.get("/search/", response_model=list[PriceComparison])
async def search_and_compare(
    q: str = Query(..., min_length=2, description="Busca por nome/gtin"),
    category: str | None = Query(None),
    limit: int = Query(10, le=50),
):
    # TODO: conectar scraper/banco. Por enquanto, retorna mock estável.
    return _mock(q, category)


def _mock(q, category):
    prices = [
        {
            "id": "22222222-2222-2222-2222-222222222221",
            "product_id": "11111111-1111-1111-1111-111111111111",
            "retailer": "petlove",
            "price_cents": 32990,
            "in_stock": True,
            "captured_at": datetime.utcnow().isoformat(),
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "product_id": "11111111-1111-1111-1111-111111111111",
            "retailer": "cobasi",
            "price_cents": 30990,
            "in_stock": True,
            "captured_at": datetime.utcnow().isoformat(),
        },
        {
            "id": "22222222-2222-2222-2222-222222222223",
            "product_id": "11111111-1111-1111-1111-111111111111",
            "retailer": "petz",
            "price_cents": 28990,
            "in_stock": True,
            "captured_at": datetime.utcnow().isoformat(),
        },
        {
            "id": "22222222-2222-2222-2222-222222222224",
            "product_id": "11111111-1111-1111-1111-111111111111",
            "retailer": "zooplus",
            "price_cents": 31990,
            "in_stock": True,
            "captured_at": datetime.utcnow().isoformat(),
        },
        {"retailer": "parceiro_local", "price_cents": 27540, "in_stock": True, "captured_at": datetime.utcnow().isoformat()},
    ]

    best = min(prices, key=lambda p: p["price_cents"])
    target_price_cents = int(best["price_cents"] * (1 - PARTNER_COMMISSION_PCT))
    savings_cents = best["price_cents"] - target_price_cents
    savings_pct = round((savings_cents / best["price_cents"]) * 100, 1)

    product_mock = {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": f"Resultado para: {q}",
        "brand": "Marca",
        "category": category or "geral",
        "image_url": "",
        "url": "",
        "description": "",
        "retailer": "petlove",
        "external_id": "mock-1",
        "gtin": "0000000000000",
        "is_active": True,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    return [
        PriceComparison(
            product=ProductRead(**product_mock),
            best_online_price=PriceRead(**best),
            all_prices=[PriceRead(**p) for p in prices],
            target_price_cents=target_price_cents,
            savings_cents=savings_cents,
            savings_pct=savings_pct,
            partner_price_cents=27540,
            can_cover=True,
        )
    ]
