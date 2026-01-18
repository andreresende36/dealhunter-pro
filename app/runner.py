"""Runner principal do scraping."""

from __future__ import annotations

from typing import Any

from config import get_config
from services.scrape_service import ScrapeService


async def run_once() -> dict[str, Any]:
    """
    Executa 1 rodada de coleta (Playwright), filtra e imprime no console.
    Retorna um dict com métricas úteis para debug.
    """
    config = get_config()
    service = ScrapeService(config)

    result = await service.run_scrape()

    # Imprime ofertas
    service.print_offers(result["shown_offers"])

    return result["metrics"]
