"""Base scraper infrastructure with Playwright, rate limiting, and error handling."""
import asyncio
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urljoin

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.core.config import settings


@dataclass
class ScrapedPrice:
    """Result of a price scrape."""
    retailer: str
    sku: str
    price: float
    original_price: Optional[float] = None
    currency: str = "BRL"
    availability: str = "in_stock"
    url: str = ""
    scraped_at: datetime = None

    def __post_init__(self):
        if self.scraped_at is None:
            self.scraped_at = datetime.utcnow()


@dataclass
class ScrapedProduct:
    """Result of a product scrape."""
    retailer: str
    external_id: str
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    gtin: Optional[str] = None
    image_url: Optional[str] = None
    url: str = ""
    description: Optional[str] = None
    scraped_at: datetime = None

    def __post_init__(self):
        if self.scraped_at is None:
            self.scraped_at = datetime.utcnow()


class RateLimiter:
    """Token bucket rate limiter for polite scraping."""

    def __init__(self, requests_per_second: float = 1.0, burst: int = 3):
        self.rate = requests_per_second
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = asyncio.get_event_loop().time()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= 1:
                self.tokens -= 1
                return

            wait_time = (1 - self.tokens) / self.rate
            self.tokens = 0
        await asyncio.sleep(wait_time)


class BrowserPool:
    """Manages a pool of browser contexts for concurrent scraping."""

    def __init__(self, max_contexts: int = 3):
        self.max_contexts = max_contexts
        self._browser: Optional[Browser] = None
        self._playwright = None
        self._contexts: list[BrowserContext] = []
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )

    async def get_context(self) -> BrowserContext:
        async with self._lock:
            if self._contexts:
                return self._contexts.pop()

            if not self._browser:
                await self.start()

            context = await self._browser.new_context(
                user_agent=self._random_user_agent(),
                viewport={"width": 1920, "height": 1080},
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
            )
            # Stealth: hide webdriver property
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            return context

    async def release_context(self, context: BrowserContext) -> None:
        async with self._lock:
            if len(self._contexts) < self.max_contexts:
                await context.clear_cookies()
                self._contexts.append(context)
            else:
                await context.close()

    async def close(self) -> None:
        for ctx in self._contexts:
            await ctx.close()
        self._contexts.clear()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    def _random_user_agent(self) -> str:
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        ]
        return random.choice(agents)


class BaseScraper(ABC):
    """Abstract base class for all retailer scrapers."""

    retailer_name: str
    base_url: str
    search_path: str = "/busca"
    rate_limit: float = 1.0  # requests per second

    def __init__(self):
        self.rate_limiter = RateLimiter(requests_per_second=self.rate_limit)
        self.browser_pool = BrowserPool(max_contexts=2)

    async def __aenter__(self):
        await self.browser_pool.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.browser_pool.close()

    @abstractmethod
    async def search_products(self, query: str, max_results: int = 20) -> list[ScrapedProduct]:
        """Search for products by query. Returns list of ScrapedProduct."""
        pass

    @abstractmethod
    async def get_price(self, product_url: str) -> Optional[ScrapedPrice]:
        """Get current price for a specific product URL. Returns ScrapedPrice or None."""
        pass

    @abstractmethod
    async def get_product_detail(self, product_url: str) -> Optional[ScrapedProduct]:
        """Get full product details from product page. Returns ScrapedProduct or None."""
        pass

    async def _fetch_page(self, url: str, wait_for: Optional[str] = None) -> Page:
        """Fetch a page with rate limiting and error handling."""
        await self.rate_limiter.acquire()

        context = await self.browser_pool.get_context()
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if wait_for:
                await page.wait_for_selector(wait_for, timeout=10000)
            return page
        except Exception as e:
            await page.close()
            await self.browser_pool.release_context(context)
            raise

    async def _close_page(self, page: Page) -> None:
        """Close page and return context to pool."""
        context = page.context
        await page.close()
        await self.browser_pool.release_context(context)

    def _clean_price(self, price_str: str) -> Optional[float]:
        """Extract float price from string like 'R$ 129,90' or '129.90'."""
        if not price_str:
            return None
        # Remove currency symbols, spaces, replace comma with dot
        cleaned = price_str.replace("R$", "").replace("R$", "").replace(".", "").replace(",", ".").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _extract_gtin(self, text: str) -> Optional[str]:
        """Extract GTIN/EAN from text (13 digits)."""
        import re
        match = re.search(r"\b(\d{13})\b", text)
        return match.group(1) if match else None