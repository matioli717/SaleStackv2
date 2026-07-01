"""Scrapers package - exports all retailer scrapers."""
from app.scrapers.base import BaseScraper, ScrapedPrice, ScrapedProduct, BrowserPool, RateLimiter
from app.scrapers.petlove import PetloveScraper
from app.scrapers.cobasi import CobasiScraper
from app.scrapers.petz import PetzScraper
from app.scrapers.zooplus import ZooPlusScraper

__all__ = [
    "BaseScraper",
    "ScrapedPrice",
    "ScrapedProduct",
    "BrowserPool",
    "RateLimiter",
    "PetloveScraper",
    "CobasiScraper",
    "PetzScraper",
    "ZooPlusScraper",
]

# Registry of available scrapers
SCRAPERS = {
    "petlove": PetloveScraper,
    "cobasi": CobasiScraper,
    "petz": PetzScraper,
    "zooplus": ZooPlusScraper,
}


def get_scraper(retailer: str) -> BaseScraper:
    """Get scraper instance for a retailer."""
    scraper_class = SCRAPERS.get(retailer.lower())
    if not scraper_class:
        raise ValueError(f"Unknown retailer: {retailer}. Available: {list(SCRAPERS.keys())}")
    return scraper_class()


def get_all_scrapers() -> list[BaseScraper]:
    """Get instances of all available scrapers."""
    return [cls() for cls in SCRAPERS.values()]