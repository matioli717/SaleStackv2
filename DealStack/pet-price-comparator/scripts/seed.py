#!/usr/bin/env python
"""Seed script with sample products and prices for testing."""

import asyncio
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import engine, async_session_maker, Base
from app.models.product import Product, Price, Retailer


SAMPLE_PRODUCTS = [
    # Ração Cão
    {
        "gtin": "7896006701234",
        "name": "Premier Raça Pequena Frango 15kg",
        "brand": "Premier",
        "category": "racao",
        "subcategory": "racao_cao",
        "weight_kg": 15000,
        "description": "Ração super premium para cães de raças pequenas",
    },
    {
        "gtin": "7896006701241",
        "name": "Royal Canin Mini Adult 7.5kg",
        "brand": "Royal Canin",
        "category": "racao",
        "subcategory": "racao_cao",
        "weight_kg": 7500,
        "description": "Ração para cães adultos de raças miniaturas",
    },
    {
        "gtin": "7896006701258",
        "name": "Golden Formula Filhotes Frango 15kg",
        "brand": "Golden",
        "category": "racao",
        "subcategory": "racao_cao",
        "weight_kg": 15000,
        "description": "Ração para filhotes de todas as raças",
    },
    {
        "gtin": "7896006701265",
        "name": "Nutrilus Adulto Carne 15kg",
        "brand": "Nutrilus",
        "category": "racao",
        "subcategory": "racao_cao",
        "weight_kg": 15000,
        "description": "Ração econômica para cães adultos",
    },
    # Ração Gato
    {
        "gtin": "7896006701272",
        "name": "Premier Gatos Castrados Salmão 7.5kg",
        "brand": "Premier",
        "category": "racao",
        "subcategory": "racao_gato",
        "weight_kg": 7500,
        "description": "Ração para gatos castrados sabor salmão",
    },
    {
        "gtin": "7896006701289",
        "name": "Royal Canin Sterilised 37 4kg",
        "brand": "Royal Canin",
        "category": "racao",
        "subcategory": "racao_gato",
        "weight_kg": 4000,
        "description": "Ração para gatos esterilizados",
    },
    {
        "gtin": "7896006701296",
        "name": "Whiskas Adulto Carne 10kg",
        "brand": "Whiskas",
        "category": "racao",
        "subcategory": "racao_gato",
        "weight_kg": 10000,
        "description": "Ração para gatos adultos sabor carne",
    },
    # Antipulga
    {
        "gtin": "7896006701302",
        "name": "Bravecto 140mg Cães 10-20kg (1 comp)",
        "brand": "MSD",
        "category": "medicamento",
        "subcategory": "antipulga",
        "weight_kg": 140,
        "description": "Antipulga e carrapato mastigável 12 semanas",
    },
    {
        "gtin": "7896006701319",
        "name": "NexGard 68mg Cães 10-25kg (3 comp)",
        "brand": "Boehringer",
        "category": "medicamento",
        "subcategory": "antipulga",
        "weight_kg": 204,
        "description": "Antipulga e carrapato mastigável mensal",
    },
    {
        "gtin": "7896006701326",
        "name": "Simparic 20mg Cães 10-20kg (3 comp)",
        "brand": "Zoetis",
        "category": "medicamento",
        "subcategory": "antipulga",
        "weight_kg": 60,
        "description": "Antipulga e carrapato mastigável mensal",
    },
    # Vermífugo
    {
        "gtin": "7896006701333",
        "name": "Drontal Plus Cães 10-20kg (2 comp)",
        "brand": "Bayer",
        "category": "medicamento",
        "subcategory": "vermifugo",
        "weight_kg": 0,
        "description": "Vermífugo de amplo espectro para cães",
    },
    {
        "gtin": "7896006701340",
        "name": "Milbemax Cães Pequenos 2-5kg (2 comp)",
        "brand": "Elanco",
        "category": "medicamento",
        "subcategory": "vermifugo",
        "weight_kg": 0,
        "description": "Vermífugo para cães de pequeno porte",
    },
    {
        "gtin": "7896006701357",
        "name": "Profender Gatos 2.5-5kg (1 pipeta)",
        "brand": "Bayer",
        "category": "medicamento",
        "subcategory": "vermifugo",
        "weight_kg": 0,
        "description": "Vermífugo tópico para gatos",
    },
]


# Preços simulados (em centavos) - variações realistas por varejista
PRICE_VARIATIONS = {
    Retailer.PETLOVE: {"base_mult": 1.00, "stock_rate": 0.95},
    Retailer.COBASI: {"base_mult": 1.03, "stock_rate": 0.90},
    Retailer.PETZ: {"base_mult": 1.05, "stock_rate": 0.85},
    Retailer.AMAZON: {"base_mult": 0.98, "stock_rate": 0.80},
    Retailer.PARCEIRO_LOCAL: {"base_mult": 0.95, "stock_rate": 1.00},  # 5% mais barato que o melhor online
}


def generate_base_price(product: dict) -> int:
    """Gera preço base realista por categoria/peso."""
    base_prices = {
        ("racao", "racao_cao"): {"15000": 18000, "7500": 12000},
        ("racao", "racao_gato"): {"7500": 14000, "4000": 9500, "10000": 16000},
        ("medicamento", "antipulga"): {"140": 18000, "204": 22000, "60": 16000},
        ("medicamento", "vermifugo"): {"0": 4500},
    }
    key = (product["category"], product["subcategory"])
    weight_key = str(product.get("weight_kg", 0))
    return base_prices.get(key, {}).get(weight_key, 5000)


async def seed_products(db: AsyncSession) -> None:
    print("Seeding products...")

    for pdata in SAMPLE_PRODUCTS:
        # Check if exists
        from sqlalchemy import select
        result = await db.execute(select(Product).where(Product.gtin == pdata["gtin"]))
        if result.scalar_one_or_none():
            print(f"  Skipping {pdata['gtin']} (already exists)")
            continue

        product = Product(**pdata)
        db.add(product)
        await db.flush()

        # Generate prices for each retailer
        base_price = generate_base_price(pdata)

        for retailer, config in PRICE_VARIATIONS.items():
            import random
            if random.random() > config["stock_rate"]:
                continue  # out of stock

            price_cents = int(base_price * config["base_mult"] * (0.95 + random.random() * 0.1))

            price = Price(
                product_id=product.id,
                retailer=retailer,
                price_cents=price_cents,
                in_stock=True,
                url=f"https://{retailer.value}.com.br/produto/{pdata['gtin']}",
            )
            db.add(price)

        print(f"  Created: {pdata['name']} (base: R$ {base_price/100:.2f})")

    await db.commit()
    print("Done!")


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as db:
        await seed_products(db)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())