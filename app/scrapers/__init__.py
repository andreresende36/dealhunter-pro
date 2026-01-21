"""Módulos de scraping."""

from scrapers.ml_scraper import scrape_ml_offers_playwright
from scrapers.affiliate_enricher import enrich_offers_affiliate_details
from scrapers.affiliate_hub_scraper import scrape_affiliate_hub
from scrapers.discount_validator import validate_discounts_parallel

__all__ = [
    "scrape_ml_offers_playwright",
    "enrich_offers_affiliate_details",
    "scrape_affiliate_hub",
    "validate_discounts_parallel",
]
