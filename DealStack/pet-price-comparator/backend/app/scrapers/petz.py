"""Petz scraper implementation (scaffold)."""
from typing import Optional
from urllib.parse import quote_plus

from playwright.async_api import Page

from app.scrapers.base import BaseScraper, ScrapedPrice, ScrapedProduct


class PetzScraper(BaseScraper):
    """Scraper for Petz (petz.com.br)."""

    retailer_name = "petz"
    base_url = "https://www.petz.com.br"
    search_path = "/busca"
    rate_limit = 1.0

    SELECTORS = {
        "search_results": ".product-card, .product-item, .vitrine-item",
        "product_link": "a[href*='/produto/'], a.product-link",
        "product_name": ".product-name, .name, h2.title",
        "product_price": ".price .sales, .best-price, [data-price]",
        "product_original_price": ".price .original, .old-price, .from-price",
        "product_image": ".product-image img, .image img",
        "product_brand": ".brand, .manufacturer",
        "availability": ".availability, .stock, .disponibilidade",
        "detail_name": "h1.product-name, h1.title, .product-title",
        "detail_price": ".price .sales, .best-price, [data-price]",
        "detail_original_price": ".price .original, .old-price, .from-price",
        "detail_image": ".product-gallery img, .product-image img",
        "detail_brand": ".brand, .manufacturer",
        "detail_description": ".description, .product-description, .descricao",
        "detail_gtin": ".gtin, .ean, .codigo-barras, .sku",
    }

    async def search_products(self, query: str, max_results: int = 20) -> list[ScrapedProduct]:
        search_url = f"{self.base_url}{self.search_path}?q={quote_plus(query)}"
        products = []

        page = await self._fetch_page(search_url, wait_for=self.SELECTORS["search_results"])

        try:
            await self._scroll_page(page)
            cards = await page.query_selector_all(self.SELECTORS["search_results"])

            for card in cards[:max_results]:
                try:
                    product = await self._parse_search_card(card)
                    if product:
                        products.append(product)
                except Exception:
                    continue

        finally:
            await self._close_page(page)

        return products

    async def get_price(self, product_url: str) -> Optional[ScrapedPrice]:
        page = await self._fetch_page(product_url, wait_for=self.SELECTORS["detail_price"])

        try:
            return await self._parse_price(page, product_url)
        finally:
            await self._close_page(page)

    async def get_product_detail(self, product_url: str) -> Optional[ScrapedProduct]:
        page = await self._fetch_page(product_url, wait_for=self.SELECTORS["detail_name"])

        try:
            return await self._parse_product_detail(page, product_url)
        finally:
            await self._close_page(page)

    async def _scroll_page(self, page: Page, scrolls: int = 3) -> None:
        for _ in range(scrolls):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(500)

    async def _parse_search_card(self, card) -> Optional[ScrapedProduct]:
        try:
            link_elem = await card.query_selector(self.SELECTORS["product_link"])
            if not link_elem:
                return None

            href = await link_elem.get_attribute("href")
            if not href:
                return None

            product_url = href if href.startswith("http") else f"{self.base_url}{href}"
            external_id = self._extract_external_id(product_url)
            if not external_id:
                return None

            name_elem = await card.query_selector(self.SELECTORS["product_name"])
            name = (await name_elem.inner_text()).strip() if name_elem else ""

            price_elem = await card.query_selector(self.SELECTORS["product_price"])
            price_str = await price_elem.inner_text() if price_elem else ""
            price = self._clean_price(price_str)

            orig_price_elem = await card.query_selector(self.SELECTORS["product_original_price"])
            orig_price_str = await orig_price_elem.inner_text() if orig_price_elem else ""
            original_price = self._clean_price(orig_price_str)

            img_elem = await card.query_selector(self.SELECTORS["product_image"])
            image_url = None
            if img_elem:
                image_url = await img_elem.get_attribute("src") or await img_elem.get_attribute("data-src")

            brand_elem = await card.query_selector(self.SELECTORS["product_brand"])
            brand = await brand_elem.inner_text() if brand_elem else None

            avail_elem = await card.query_selector(self.SELECTORS["availability"])
            availability = "in_stock"
            if avail_elem:
                avail_text = await avail_elem.inner_text()
                if any(word in avail_text.lower() for word in ["indisponível", "esgotado", "sem estoque"]):
                    availability = "out_of_stock"

            return ScrapedProduct(
                retailer=self.retailer_name,
                external_id=external_id,
                name=name,
                brand=brand.strip() if brand else None,
                image_url=image_url,
                url=product_url,
            )
        except Exception:
            return None

    async def _parse_price(self, page: Page, product_url: str) -> Optional[ScrapedPrice]:
        try:
            price_elem = await page.query_selector(self.SELECTORS["detail_price"])
            price_str = await price_elem.inner_text() if price_elem else ""
            price = self._clean_price(price_str)

            if price is None:
                return None

            orig_price_elem = await page.query_selector(self.SELECTORS["detail_original_price"])
            orig_price_str = await orig_price_elem.inner_text() if orig_price_elem else ""
            original_price = self._clean_price(orig_price_str)

            avail_elem = await page.query_selector(self.SELECTORS["availability"])
            availability = "in_stock"
            if avail_elem:
                avail_text = await avail_elem.inner_text()
                if any(word in avail_text.lower() for word in ["indisponível", "esgotado", "sem estoque"]):
                    availability = "out_of_stock"

            external_id = self._extract_external_id(product_url)

            return ScrapedPrice(
                retailer=self.retailer_name,
                sku=external_id,
                price=price,
                original_price=original_price,
                availability=availability,
                url=product_url,
            )
        except Exception:
            return None

    async def _parse_product_detail(self, page: Page, product_url: str) -> Optional[ScrapedProduct]:
        try:
            external_id = self._extract_external_id(product_url)

            name_elem = await page.query_selector(self.SELECTORS["detail_name"])
            name = (await name_elem.inner_text()).strip() if name_elem else ""

            price_elem = await page.query_selector(self.SELECTORS["detail_price"])
            price_str = await price_elem.inner_text() if price_elem else ""
            price = self._clean_price(price_str)

            orig_price_elem = await page.query_selector(self.SELECTORS["detail_original_price"])
            orig_price_str = await orig_price_elem.inner_text() if orig_price_elem else ""
            original_price = self._clean_price(orig_price_str)

            img_elem = await page.query_selector(self.SELECTORS["detail_image"])
            image_url = None
            if img_elem:
                image_url = await img_elem.get_attribute("src") or await img_elem.get_attribute("data-src")

            brand_elem = await page.query_selector(self.SELECTORS["detail_brand"])
            brand = await brand_elem.inner_text() if brand_elem else None

            desc_elem = await page.query_selector(self.SELECTORS["detail_description"])
            description = await desc_elem.inner_text() if desc_elem else None

            gtin_elem = await page.query_selector(self.SELECTORS["detail_gtin"])
            gtin = None
            if gtin_elem:
                gtin_text = await gtin_elem.inner_text()
                gtin = self._extract_gtin(gtin_text)
            if not gtin and description:
                gtin = self._extract_gtin(description)

            return ScrapedProduct(
                retailer=self.retailer_name,
                external_id=external_id,
                name=name,
                brand=brand.strip() if brand else None,
                image_url=image_url,
                url=product_url,
                description=description.strip() if description else None,
                gtin=gtin,
            )
        except Exception:
            return None

    def _extract_external_id(self, url: str) -> Optional[str]:
        import re
        match = re.search(r"/produto/(\d+)", url)
        return match.group(1) if match else None