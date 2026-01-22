"""Jobs RQ para enriquecimento de ofertas."""

from __future__ import annotations

import asyncio

from config import get_config
from database import DatabaseService, get_session, init_db
from services.enrichment_service import enrich_offer
from utils.logging import log


def enrich_offer_job(offer_id: str, url: str, current_price_cents: int) -> dict:
    """
    Job RQ para enriquecer uma oferta.

    Esta função é executada pelos workers RQ e não deve ser chamada diretamente.
    Use enqueue_enrichment_job() para enfileirar jobs.

    Args:
        offer_id: ID da oferta no banco de dados
        url: URL da oferta para scraping
        current_price_cents: Preço atual em centavos

    Returns:
        Dicionário com resultado do enriquecimento
    """
    config = get_config()

    log(f"[enrichment_job] Iniciando enriquecimento de oferta {offer_id} ({url})")

    try:
        # Executa o enriquecimento de forma assíncrona
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                enrich_offer(
                    url=url,
                    current_price_cents=current_price_cents,
                    ml_config=config.ml,
                    affiliate_config=config.affiliate,
                    timeout_ms=60000,
                    request_delay_s=config.enrichment.request_delay_s,
                )
            )
        finally:
            loop.close()

        # Atualiza o banco de dados
        init_db(config.database)

        async def _update_database() -> dict:
            async for client in get_session():
                try:
                    db_service = DatabaseService(client)
                    updated_offer = await db_service.offers.update_offer_enrichment(
                        offer_id=offer_id,
                        old_price_cents=result.old_price_cents,
                        discount_pct=result.discount_pct,
                        affiliate_link=result.affiliate_link,
                        affiliation_id=result.affiliation_id,
                    )
                    log(
                        f"[enrichment_job] Oferta {offer_id} atualizada com sucesso: "
                        f"old_price={result.old_price_cents}, "
                        f"discount={result.discount_pct}%, "
                        f"affiliate_link={'sim' if result.affiliate_link else 'não'}, "
                        f"affiliation_id={'sim' if result.affiliation_id else 'não'}"
                    )
                    return updated_offer
                except Exception as e:
                    log(f"[enrichment_job] Erro ao atualizar oferta {offer_id}: {e}")
                    raise

        update_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(update_loop)

        try:
            updated_offer = update_loop.run_until_complete(_update_database())
        finally:
            update_loop.close()

        return {
            "success": True,
            "offer_id": offer_id,
            "old_price_cents": result.old_price_cents,
            "discount_pct": result.discount_pct,
            "affiliate_link": result.affiliate_link is not None,
            "affiliation_id": result.affiliation_id is not None,
        }

    except Exception as e:
        log(f"[enrichment_job] Erro ao enriquecer oferta {offer_id}: {e}")
        import traceback

        log(f"[enrichment_job] Traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "offer_id": offer_id,
            "error": str(e),
        }
