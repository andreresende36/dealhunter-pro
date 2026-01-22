"""Serviço principal de scraping."""

from __future__ import annotations

import traceback
import time
from dataclasses import asdict
from typing import Any

from config import Config
from database import DatabaseService, get_session, init_db
from models import ScrapedOffer
from scrapers import scrape_affiliate_hub
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
        Executa uma rodada completa de scraping:
        1. Coleta produtos da Central de Afiliados
        2. Filtra por desconto mínimo (se aplicável)

        Returns:
            Dicionário com métricas da execução
        """
        t0 = time.perf_counter()

        log(
            f"[scrape] Iniciando coleta da Central de Afiliados "
            f"({self.config.ml.url})..."
        )
        log(
            f"[scrape] MIN_DISCOUNT_PCT={self.config.scrape.min_discount_pct} | "
            f"ML_MAX_SCROLLS={self.config.scrape.max_scrolls} | "
            f"ML_SCROLL_DELAY_S={self.config.scrape.scroll_delay_s} | "
            f"AFFILIATE_CONCURRENCY={self.config.affiliate.concurrency}"
        )

        # Etapa 1: Coleta produtos da Central de Afiliados
        try:
            offers = await scrape_affiliate_hub(
                ml_config=self.config.ml,
                affiliate_config=self.config.affiliate,
                max_scrolls=self.config.scrape.max_scrolls,
                scroll_delay_s=self.config.scrape.scroll_delay_s,
                debug=self.config.scrape.debug_dump,
            )
        except Exception as e:
            log(
                f"[scrape] ERRO: coleta da Central de Afiliados falhou: {type(e).__name__}: {e}"
            )
            log(f"[scrape] Traceback: {traceback.format_exc()}")
            raise

        t1 = time.perf_counter()
        log(f"[scrape] Coleta OK: {len(offers)} produtos coletados em {t1 - t0:.2f}s")

        # Filtra ofertas por desconto mínimo
        filtered = self.filter_service.filter_offers(offers)

        log(
            f"[scrape] Após filtro: {len(filtered)} itens "
            f"(>= {self.config.scrape.min_discount_pct}% desconto)"
        )

        # Prepara ofertas para exibição
        show = filtered[: self.config.max_items_print]

        t2 = time.perf_counter()

        # Salva no banco de dados se configurado (salva TODAS as ofertas coletadas)
        scrape_run_id = await self._save_to_database(offers)

        metrics = {
            "collected_count": len(offers),
            "filtered_count": len(filtered),
            "shown_count": len(show),
            "min_discount_pct": self.config.scrape.min_discount_pct,
            "max_scrolls": self.config.scrape.max_scrolls,
            "seconds_total": round(t2 - t0, 2),
            "seconds_collect": round(t1 - t0, 2),
            "seconds_filter_save": round(t2 - t1, 2),
            "scrape_run_id": scrape_run_id,
        }
        log(f"[scrape] Métricas: {metrics}")

        return {"metrics": metrics, "filtered_offers": filtered, "shown_offers": show}

    async def _save_to_database(self, offers: list[ScrapedOffer]) -> str | None:
        """
        Salva ofertas no banco de dados se configurado.

        Args:
            offers: Lista de ofertas para salvar

        Returns:
            ID do ScrapeRun criado ou None
        """
        # Verifica se há configuração do Supabase
        if (
            not self.config.database.supabase_url
            or not self.config.database.supabase_key
        ):
            log(
                "[scrape] SUPABASE_URL ou chave de API não configuradas. "
                "Pulando salvamento no banco."
            )
            return None

        if not offers:
            log("[scrape] Nenhuma oferta para salvar no banco.")
            return None

        try:
            log(
                f"[scrape] Inicializando conexão com banco para salvar {len(offers)} ofertas..."
            )
            init_db(self.config.database)

            scrape_run_id = None
            async for client in get_session():
                try:
                    db_service = DatabaseService(client)
                    config_snapshot = {
                        "min_discount_pct": self.config.scrape.min_discount_pct,
                        "max_scrolls": self.config.scrape.max_scrolls,
                        "number_of_pages": self.config.scrape.number_of_pages,
                        "only_with_old_price": self.config.scrape.only_with_old_price,
                    }

                    log(f"[scrape] Salvando {len(offers)} ofertas no banco...")
                    scrape_run = await db_service.save_scrape_run_with_offers(
                        offers=offers,
                        min_discount_pct=self.config.scrape.min_discount_pct,
                        max_scrolls=self.config.scrape.max_scrolls,
                        number_of_pages=self.config.scrape.number_of_pages,
                        config_snapshot=config_snapshot,
                        save_price_history=True,
                        save_affiliate_info=True,
                    )

                    scrape_run_id = scrape_run["id"]
                    log(
                        f"[scrape] ✅ Dados salvos no banco com sucesso! "
                        f"ScrapeRun ID: {scrape_run_id}, "
                        f"Ofertas salvas: {len(offers)}"
                    )
                    break  # Sair do loop após salvar com sucesso
                except Exception as e:
                    log(
                        f"[scrape] ❌ ERRO ao salvar ofertas no banco: "
                        f"{type(e).__name__}: {e}"
                    )
                    log(f"[scrape] Traceback: {traceback.format_exc()}")
                    raise

            return scrape_run_id
        except Exception as e:
            log(
                f"[scrape] ❌ ERRO ao conectar/salvar no banco: "
                f"{type(e).__name__}: {e}"
            )
            log(f"[scrape] Traceback completo: {traceback.format_exc()}")
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
                f" | Desc: {(
                    '-' if offer.discount_pct is None
                    else f'{offer.discount_pct}%'
                )}"
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
