"""Jobs RQ para enriquecimento de ofertas."""

from __future__ import annotations

import asyncio

from shared.config.settings import get_config
from adapters.database import DatabaseService, get_session, init_db
from core.use_cases.enrichment_service import enrich_offer
from shared.utils.logging import log


async def _async_enrich_offer_job(
    offer_id: str, url: str, current_price_cents: int
) -> dict:
    """
    Job assíncrono para enriquecer uma oferta.

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
        # Executa o enriquecimento
        result = await enrich_offer(
            url=url,
            current_price_cents=current_price_cents,
            ml_config=config.ml,
            affiliate_config=config.affiliate,
            timeout_ms=60000,
            request_delay_s=config.enrichment.request_delay_s,
            use_browser_pool=True,  # Usa browser pool para melhor performance
        )

        # Atualiza o banco de dados
        init_db(config.database)

        async for client in get_session():
            try:
                db_service = DatabaseService(client)
                await db_service.offers.update_offer_enrichment(
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
                break  # Sai do loop após sucesso
            except Exception as e:
                log(f"[enrichment_job] Erro ao atualizar oferta {offer_id}: {e}")
                raise

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
    # Executa a função async com um único event loop
    return asyncio.run(_async_enrich_offer_job(offer_id, url, current_price_cents))
