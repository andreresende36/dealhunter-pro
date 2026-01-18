"""Módulo de banco de dados."""

from database.connection import get_session, init_db
from database.models import (
    AffiliateInfo,
    Offer,
    OfferScrapeRun,
    PriceHistory,
    ScrapeRun,
)
from database.repositories import DatabaseService

__all__ = [
    "get_session",
    "init_db",
    "Offer",
    "ScrapeRun",
    "OfferScrapeRun",
    "PriceHistory",
    "AffiliateInfo",
    "DatabaseService",
]
