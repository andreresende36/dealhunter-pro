"""Serviço principal de scraping."""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from config import Config
from database import DatabaseService, get_session, init_db
from models import ScrapedOffer
from scrapers import enrich_offers_affiliate_details, scrape_ml_offers_playwright
from services.offer_filter import OfferFilter
from utils.format import format_brl, format_pct
from utils.logging import log


class ScrapeService:
    """Serviço principal para execução de scraping."""

    def __init__(self, config: Config) -> None:
        """Inicializa o serviço com a configuração fornecida."""
        self.config = config
        self.filter_service = OfferFilter(config.scrape)

    async def run_scrape(self) -> dict[str, Any]:
        """
        Executa uma rodada completa de scraping.

        Returns:
            Dicionário com métricas da execução
        """
        t0 = time.perf_counter()

        log(
            f"[scrape] Iniciando coleta Mercado Livre "
            f"({self.config.ml.url}) com Playwright..."
        )
        log(
            f"[scrape] MIN_DISCOUNT_PCT={self.config.scrape.min_discount_pct} | "
            f"ML_MAX_SCROLLS={self.config.scrape.max_scrolls} | "
            f"NUMBER_OF_PAGES={self.config.scrape.number_of_pages} | "
            f"ML_SCROLL_DELAY_S={self.config.scrape.scroll_delay_s} | "
            f"ML_PAGE_DELAY_S={self.config.scrape.page_delay_s}"
        )

        try:
            offers = await scrape_ml_offers_playwright(
                ml_config=self.config.ml,
                scrape_config=self.config.scrape,
            )
        except Exception as e:
            log(f"[scrape] ERRO: coleta falhou: {type(e).__name__}: {e}")
            raise

        t1 = time.perf_counter()
        log(f"[scrape] Coleta OK: {len(offers)} itens brutos em {t1 - t0:.2f}s")

        # Filtra ofertas
        filtered = self.filter_service.filter_offers(offers)

        log(
            f"[scrape] Após filtro: {len(filtered)} itens "
            f"(>= {self.config.scrape.min_discount_pct:.2f}% desconto)"
        )

        # Enriquece ofertas selecionadas com detalhes de afiliado
        show = filtered[: self.config.max_items_print]
        if show and self.config.affiliate.concurrency > 0:
            await enrich_offers_affiliate_details(show, config=self.config.affiliate)

        t2 = time.perf_counter()

        # Salva no banco de dados se configurado
        scrape_run_id = await self._save_to_database(filtered)

        metrics = {
            "raw_count": len(offers),
            "filtered_count": len(filtered),
            "shown_count": len(show),
            "min_discount_pct": self.config.scrape.min_discount_pct,
            "max_scrolls": self.config.scrape.max_scrolls,
            "number_of_pages": self.config.scrape.number_of_pages,
            "seconds_total": round(t2 - t0, 2),
            "seconds_scrape": round(t1 - t0, 2),
            "seconds_filter_print": round(t2 - t1, 2),
            "scrape_run_id": scrape_run_id,
        }
        log(f"[scrape] Métricas: {metrics}")

        return {"metrics": metrics, "filtered_offers": filtered, "shown_offers": show}

    async def _save_to_database(self, offers: list[ScrapedOffer]) -> int | None:
        """
        Salva ofertas no banco de dados se configurado.

        Args:
            offers: Lista de ofertas para salvar

        Returns:
            ID do ScrapeRun criado ou None
        """
        if not self.config.database.url or "postgresql" not in self.config.database.url:
            log("[scrape] DATABASE_URL não configurada. Pulando salvamento no banco.")
            return None

        try:
            init_db(self.config.database)
            async for session in get_session():
                db_service = DatabaseService(session)
                config_snapshot = {
                    "min_discount_pct": self.config.scrape.min_discount_pct,
                    "max_scrolls": self.config.scrape.max_scrolls,
                    "number_of_pages": self.config.scrape.number_of_pages,
                    "only_with_old_price": self.config.scrape.only_with_old_price,
                }
                scrape_run = await db_service.save_scrape_run_with_offers(
                    offers=offers,
                    min_discount_pct=self.config.scrape.min_discount_pct,
                    max_scrolls=self.config.scrape.max_scrolls,
                    number_of_pages=self.config.scrape.number_of_pages,
                    config_snapshot=config_snapshot,
                    save_price_history=True,
                    save_affiliate_info=True,
                )
                scrape_run_id = scrape_run.id
                log(f"[scrape] Dados salvos no banco. ScrapeRun ID: {scrape_run_id}")
                return scrape_run_id
        except Exception as e:
            log(f"[scrape] ERRO ao salvar no banco: {type(e).__name__}: {e}")
            return None

    def print_offers(self, offers: list[ScrapedOffer]) -> None:
        """
        Imprime ofertas no console formatadas.

        Args:
            offers: Lista de ofertas para imprimir
        """
        log("-" * 90)
        for idx, offer in enumerate(offers, start=1):
            log(
                f"[{idx:02d}] {offer.title}"
                f"\n     De: {format_brl(offer.old_price_cents)}"
                f" | Agora: {format_brl(offer.price_cents)}"
                f" | Desc: {('-' if offer.discount_pct is None else f'{offer.discount_pct:.0f}%')}"  # noqa: E501
                f" | Comissão: {format_pct(offer.commission_pct)}"
                f"\n     URL: {offer.url}"
                f"\n     Link afiliado: {offer.affiliate_link or '-'}"
                f"\n     Código afiliação: {offer.affiliation_id or '-'}"
                f"\n     MLB ID: {offer.external_id}"
                f"\n     Image URL: {offer.image_url}"
                f"\n     Marketplace: {offer.marketplace}"
            )
            if self.config.scrape.debug_dump:
                log(f"     DEBUG: {asdict(offer)}\n")

        if not offers:
            log("[scrape] Nenhum item passou no filtro. Sugestões:")
            log("  - reduza MIN_DISCOUNT_PCT (ex.: 30)")
            log("  - aumente ML_MAX_SCROLLS (ex.: 6)")
            log(
                "  - defina ONLY_WITH_OLD_PRICE=false para "
                "permitir itens sem preço antigo"
            )
