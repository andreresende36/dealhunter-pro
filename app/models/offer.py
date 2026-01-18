"""Modelo de oferta raspada."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ScrapedOffer:
    """Representa uma oferta raspada do Mercado Livre."""

    marketplace: str
    external_id: str
    title: str
    url: str
    image_url: str | None
    price_cents: int
    old_price_cents: int | None
    discount_pct: float | None
    commission_pct: float | None
    affiliate_link: str | None
    affiliation_id: str | None
    source: str = "ml_offers_playwright"
