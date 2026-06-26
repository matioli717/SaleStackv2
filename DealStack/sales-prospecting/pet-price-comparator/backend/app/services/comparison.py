from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.models.product import Product, Price, Retailer
from app.core.config import settings


class ComparisonService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.commission_pct = settings.PARTNER_COMMISSION_PCT
        self.min_margin_pct = settings.PARTNER_MIN_MARGIN_PCT

    async def compare_by_gtin(self, gtin: str) -> dict | None:
        """Compara preços para um GTIN específico."""
        # Busca produto
        result = await self.db.execute(select(Product).where(Product.gtin == gtin))
        product = result.scalar_one_or_none()
        if not product:
            return None

        return await self._build_comparison(product)

    async def search_and_compare(self, query: str, category: str | None = None, limit: int = 10) -> list[dict]:
        """Busca produtos e retorna comparações."""
        stmt = select(Product).where(Product.is_active == True, Product.name.ilike(f"%{query}%"))
        if category:
            stmt = stmt.where(Product.category == category)
        stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        products = result.scalars().all()

        comparisons = []
        for product in products:
            comp = await self._build_comparison(product)
            if comp:
                comparisons.append(comp)

        return comparisons

    async def _build_comparison(self, product: Product) -> dict | None:
        """Constrói objeto de comparação para um produto."""
        # Busca preços mais recentes por varejista
        stmt = (
            select(Price)
            .where(Price.product_id == product.id, Price.in_stock == True)
            .distinct(Price.retailer)
            .order_by(Price.retailer, Price.captured_at.desc())
        )
        result = await self.db.execute(stmt)
        prices = result.scalars().all()

        if not prices:
            return None

        # Separa parceiro local dos online
        partner_price = None
        online_prices = []
        for p in prices:
            if p.retailer == Retailer.PARCEIRO_LOCAL:
                partner_price = p
            else:
                online_prices.append(p)

        if not online_prices:
            return None

        # Melhor preço online
        best_online = min(online_prices, key=lambda p: p.price_cents)

        # Target price = melhor online * (1 - comissão)
        target_price_cents = int(best_online.price_cents * (1 - self.commission_pct))

        # Verifica se parceiro pode cobrir com margem mínima
        can_cover = True
        if partner_price:
            min_viable_price = int(best_online.price_cents * (1 - self.min_margin_pct))
            can_cover = partner_price.price_cents <= min_viable_price

        savings_cents = best_online.price_cents - target_price_cents
        savings_pct = (savings_cents / best_online.price_cents) * 100

        return {
            "product": product,
            "best_online_price": best_online,
            "all_prices": prices,
            "target_price_cents": target_price_cents,
            "savings_cents": savings_cents,
            "savings_pct": round(savings_pct, 1),
            "partner_price_cents": partner_price.price_cents if partner_price else None,
            "can_cover": can_cover,
        }

    async def calculate_target_price(self, best_online_price_cents: int) -> int:
        """Calcula preço alvo para o parceiro."""
        return int(best_online_price_cents * (1 - self.commission_pct))

    async def can_partner_cover(self, best_online_price_cents: int, partner_price_cents: int) -> bool:
        """Verifica se parceiro pode cobrir com margem mínima."""
        min_viable = int(best_online_price_cents * (1 - self.min_margin_pct))
        return partner_price_cents <= min_viable