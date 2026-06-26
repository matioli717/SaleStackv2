"""Petlove scraper implementation."""
import re
from typing import Optional
from urllib.parse import quote_plus

from playwright.async_api import Page

from app.scrapers.base import BaseScraper, ScrapedPrice, ScrapedProduct


class PetloveScraper(BaseScraper):
    """Scraper for Petlove (petlove.com.br)."""

    retailer_name = "petlove"
    base_url = "https://www.petlove.com.br"
    search_path = "/busca"
    rate_limit = 1.0  # 1 request/second

    # CSS selectors for Petlove (updated from live inspection 2026-06-15)
    SELECTORS = {
        "search_results": '[datatest-id="product"]',
        "product_link": '[datatest-id^="product-"]',
        "product_name": ".product-card__name, h2.product-card__name",
        "product_price": '[datatest-id="price"]',
        "product_original_price": '[datatest-id="subscriber-price"]',
        "product_image": ".product-card__thumbnail img",
        "product_brand": ".product-card__brand, [datatest-id='brand']",
        "availability": ".availability, .stock",
        # Product detail page
        "detail_name": "h1[data-testid='product-name'], h1.product-name, h1.title",
        "detail_price": '[datatest-id="price"]',
        "detail_original_price": '[datatest-id="subscriber-price"]',
        "detail_image": 'img[data-testid="product-image"], .product-gallery img',
        "detail_brand": "[data-testid='brand'], .brand, .product-brand",
        "detail_description": "[data-testid='description'], .description, .product-description",
        "detail_gtin": "[data-testid='gtin'], .gtin, .ean, .sku",
    }

    async def search_products(self, query: str, max_results: int = 20) -> list[ScrapedProduct]:
        """Search for products on Petlove."""
        search_url = f"{self.base_url}{self.search_path}?q={quote_plus(query)}"
        products = []

        page = await self._fetch_page(search_url, wait_for=self.SELECTORS["search_results"])

        try:
            # Scroll to load more results
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
        """Get current price for a product URL."""
        page = await self._fetch_page(product_url, wait_for=self.SELECTORS["detail_price"])

        try:
            price = await self._parse_price(page, product_url)
            return price
        finally:
            await self._close_page(page)

    async def get_product_detail(self, product_url: str) -> Optional[ScrapedProduct]:
        """Get full product details from product page."""
        page = await self._fetch_page(product_url, wait_for=self.SELECTORS["detail_name"])

        try:
            product = await self._parse_product_detail(page, product_url)
            return product
        finally:
            await self._close_page(page)

    async def _scroll_page(self, page: Page, scrolls: int = 3) -> None:
        """Scroll page to trigger lazy loading."""
        for _ in range(scrolls):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await page.wait_for_timeout(500)

    async def _parse_search_card(self, card) -> Optional[ScrapedProduct]:
        """Parse a product card from search results."""
        try:
            # Get product link - the link is a div with datatest-id starting with "product-" and href attribute
            link_elem = await card.query_selector(self.SELECTORS["product_link"])
            if not link_elem:
                return None

            # Extract product ID from datatest-id (format: "product-3108224-3")
            datatest_id = await link_elem.get_attribute("datatest-id")
            if not datatest_id:
                return None

            import re
            match = re.search(r"product-(\d+)", datatest_id)
            if not match:
                return None

            product_id = match.group(1)
            external_id = product_id

            # Construct product URL
            product_url = f"{self.base_url}/produto/{product_id}"

            # Name - h2 with class product-card__name
            name_elem = await card.query_selector(self.SELECTORS["product_name"])
            name = await name_elem.inner_text() if name_elem else ""
            name = name.strip()

            # Price - element with datatest-id="price"
            price_elem = await card.query_selector(self.SELECTORS["product_price"])
            price_str = await price_elem.inner_text() if price_elem else ""
            price = self._clean_price(price_str)

            # Original price (subscriber price) - element with datatest-id="subscriber-price"
            orig_price_elem = await card.query_selector(self.SELECTORS["product_original_price"])
            orig_price_str = await orig_price_elem.inner_text() if orig_price_elem else ""
            original_price = self._clean_price(orig_price_str)

            # Image - img inside product-card__thumbnail
            img_elem = await card.query_selector(self.SELECTORS["product_image"])
            image_url = None
            if img_elem:
                image_url = await img_elem.get_attribute("src") or await img_elem.get_attribute("data-src")

            # Brand - might not be visible in search results, skip for now
            brand_elem = await card.query_selector(self.SELECTORS["product_brand"])
            brand = await brand_elem.inner_text() if brand_elem else None

            # Availability
            avail_elem = await card.query_selector(self.SELECTORS["availability"])
            availability = "in_stock"
            if avail_elem:
                avail_text = await avail_elem.inner_text()
                if any(word in avail_text.lower() for word in ["indisponível", "esgotado", "unavailable"]):
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
        """Parse price from product detail page."""
        try:
            price_elem = await page.query_selector(self.SELECTORS["detail_price"])
            price_str = await price_elem.inner_text() if price_elem else ""
            price = self._clean_price(price_str)

            if price is None:
                return None

            orig_price_elem = await page.query_selector(self.SELECTORS["detail_original_price"])
            orig_price_str = await orig_price_elem.inner_text() if orig_price_elem else ""
            original_price = self._clean_price(orig_price_str)

            # Availability
            avail_elem = await page.query_selector(self.SELECTORS["availability"])
            availability = "in_stock"
            if avail_elem:
                avail_text = await avail_elem.inner_text()
                if any(word in avail_text.lower() for word in ["indisponível", "esgotado", "unavailable"]):
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
        """Parse full product detail page."""
        try:
            external_id = self._extract_external_id(product_url)

            # Name
            name_elem = await page.query_selector(self.SELECTORS["detail_name"])
            name = await name_elem.inner_text() if name_elem else ""
            name = name.strip()

            # Price
            price_elem = await page.query_selector(self.SELECTORS["detail_price"])
            price_str = await price_elem.inner_text() if price_elem else ""
            price = self._clean_price(price_str)

            # Original price
            orig_price_elem = await page.query_selector(self.SELECTORS["detail_original_price"])
            orig_price_str = await orig_price_elem.inner_text() if orig_price_elem else ""
            original_price = self._clean_price(orig_price_str)

            # Image
            img_elem = await page.query_selector(self.SELECTORS["detail_image"])
            image_url = None
            if img_elem:
                image_url = await img_elem.get_attribute("src") or await img_elem.get_attribute("data-src")

            # Brand
            brand_elem = await page.query_selector(self.SELECTORS["detail_brand"])
            brand = await brand_elem.inner_text() if brand_elem else None

            # Description
            desc_elem = await page.query_selector(self.SELECTORS["detail_description"])
            description = await desc_elem.inner_text() if desc_elem else None

            # GTIN
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
        """Extract product ID from Petlove URL or datatest-id like product-3108224-3."""
        # First try URL pattern /produto/12345
        match = re.search(r"/produto/(\d+)", url)
        if match:
            return match.group(1)
        # Then try datatest-id pattern product-12345-6 (get just the first number)
        match = re.search(r"product-(\d+)", url)
        if match:
            return match.group(1)
        return None

    def _build_product_url(self, external_id: str) -> str:
        """Build product URL from external ID."""
        return f"https://www.petlove.com.br/produto/{external_id}"