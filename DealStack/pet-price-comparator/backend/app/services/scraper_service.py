"""Scraper service - orchestrates scrapers and persists prices to database."""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import async_session_maker
from app.scrapers import get_all_scrapers, get_scraper
from app.scrapers.base import BaseScraper
from app.models.product import Product, Price, Retailer  # noqa: E402


logger = logging.getLogger(__name__)


class ScraperService:
    """Orchestrates scraping across all retailers and persists results."""

    def __init__(self, max_concurrent_scrapers: int = 2):
        self.max_concurrent = max_concurrent_scrapers
        self._semaphore = asyncio.Semaphore(max_concurrent_scrapers)

    async def scrape_all_retailers(self, query: str, max_results_per_retailer: int = 20) -> dict[str, list]:
        """Search all retailers for a query and return products by retailer."""
        scrapers = get_all_scrapers()
        results = {}

        async def scrape_one(scraper):
            async with self._semaphore:
                try:
                    logger.info(f"Searching {scraper.retailer_name} for: {query}")
                    products = await scraper.search_products(query, max_results_per_retailer)
                    logger.info(f"Found {len(products)} products from {scraper.retailer_name}")
                    return scraper.retailer_name, products
                except Exception as e:
                    logger.error(f"Error scraping {scraper.retailer_name}: {e}")
                    return scraper.retailer_name, []

        tasks = [scrape_one(s) for s in scrapers]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results_list:
            if isinstance(result, Exception):
                logger.error(f"Scraper task failed: {result}")
                continue
            retailer, products = result
            results[retailer] = products

        return results

    async def scrape_product_prices(self, product_urls: dict[str, str]) -> dict[str, Optional[float]]:
        """Get current prices for specific product URLs by retailer."""
        results = {}

        async def scrape_price(retailer: str, url: str):
            async with self._semaphore:
                try:
                    scraper = get_scraper(retailer)
                    async with scraper:
                        price_data = await scraper.get_price(url)
                        return retailer, price_data.price if price_data else None
                except Exception as e:
                    logger.error(f"Error getting price from {retailer} ({url}): {e}")
                    return retailer, None

        tasks = [scrape_price(retailer, url) for retailer, url in product_urls.items()]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results_list:
            if isinstance(result, Exception):
                continue
            retailer, price = result
            results[retailer] = price

        return results

    async def refresh_all_prices(self, batch_size: int = 50) -> dict[str, int]:
        """Refresh prices for all products in database. Returns counts per retailer."""
        async with async_session_maker() as session:
            # Get all products with their retailer URLs
            result = await session.execute(
                select(Product).where(Product.is_active == True)
            )
            products = result.scalars().all()

        # Group by retailer
        by_retailer: dict[str, list[Product]] = {}
        for product in products:
            if product.retailer not in by_retailer:
                by_retailer[product.retailer] = []
            by_retailer[product.retailer].append(product)

        results = {}

        for retailer, products in by_retailer.items():
            try:
                scraper = get_scraper(retailer)
                async with scraper:
                    count = await self._refresh_retailer_prices(scraper, products, batch_size)
                    results[retailer] = count
            except Exception as e:
                logger.error(f"Failed to refresh prices for {retailer}: {e}")
                results[retailer] = 0

        return results

    async def _refresh_retailer_prices(
        self, scraper: BaseScraper, products: list[Product], batch_size: int
    ) -> int:
        """Refresh prices for a single retailer's products."""
        updated = 0

        for i in range(0, len(products), batch_size):
            batch = products[i : i + batch_size]

            async def update_one(product: Product) -> bool:
                async with self._semaphore:
                    try:
                        price_data = await scraper.get_price(product.url)
                        if price_data and price_data.price:
                            async with async_session_maker() as session:
                                # Get fresh product instance
                                fresh_product = await session.get(Product, product.id)
                                if not fresh_product:
                                    return False

                                # Create new price record
                                new_price = Price(
                                    product_id=fresh_product.id,
                                    retailer=fresh_product.retailer,
                                    price_cents=int(price_data.price * 100),
                                    in_stock=price_data.availability != "out_of_stock",
                                    captured_at=price_data.scraped_at,
                                )
                                session.add(new_price)
                                await session.commit()
                                return True
                    except Exception as e:
                        logger.error(f"Error updating price for {product.id}: {e}")
                    return False

            tasks = [update_one(p) for p in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            updated += sum(1 for r in results if r is True)

            # Small delay between batches to be polite
            if i + batch_size < len(products):
                await asyncio.sleep(2)

        return updated

    async def search_and_upsert_products(
        self, query: str, max_results_per_retailer: int = 20
    ) -> dict[str, int]:
        """Search all retailers and upsert products to database."""
        results = await self.scrape_all_retailers(query, max_results_per_retailer)
        counts = {}

        for retailer, products in results.items():
            count = await self._upsert_products(retailer, products)
            counts[retailer] = count

        return counts

    async def _upsert_products(self, retailer: str, products: list) -> int:
        """Upsert scraped products to database."""
        if not products:
            return 0

        async with async_session_maker() as session:
            upserted = 0
            for scraped in products:
                # Check if product exists by retailer + external_id
                result = await session.execute(
                    select(Product).where(
                        Product.retailer == retailer,
                        Product.external_id == scraped.external_id,
                    )
                )
                product = result.scalar_one_or_none()

                if product:
                    # Update existing
                    product.name = scraped.name
                    product.brand = scraped.brand
                    product.image_url = scraped.image_url
                    product.url = scraped.url
                    product.description = scraped.description
                    product.gtin = scraped.gtin
                    product.updated_at = datetime.utcnow()
                else:
                    # Create new
                    product = Product(
                        retailer=retailer,
                        external_id=scraped.external_id,
                        name=scraped.name,
                        brand=scraped.brand,
                        category=scraped.category,
                        gtin=scraped.gtin,
                        image_url=scraped.image_url,
                        url=scraped.url,
                        description=scraped.description,
                        is_active=True,
                    )
                    session.add(product)

                upserted += 1

            await session.commit()
            return upserted


# Singleton instance
scraper_service = ScraperService()