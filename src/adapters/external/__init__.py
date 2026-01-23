"""Módulos de scraping."""

from adapters.external.ml_scraper import scrape_ml_offers_playwright
from adapters.external.affiliate_enricher import enrich_offers_affiliate_details
from adapters.external.affiliate_hub_scraper import scrape_affiliate_hub
from adapters.external.discount_validator import validate_discounts_parallel

__all__ = [
    "scrape_ml_offers_playwright",
    "enrich_offers_affiliate_details",
    "scrape_affiliate_hub",
    "validate_discounts_parallel",
]
