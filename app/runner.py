"""Runner principal do scraping."""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from config import get_config
from models import ScrapedOffer
from scrapers import (
    enrich_offers_affiliate_details,
    scrape_ml_offers_playwright,
)
from utils.format import format_brl, format_pct
from utils.logging import log


def _offer_sort_key(o: ScrapedOffer) -> tuple:
    """
    Chave de ordenação para ofertas.
    Ordena por desconto decrescente, depois preço crescente.
    """
    disc = o.discount_pct if o.discount_pct is not None else -1.0
    return (-disc, o.price_cents)


async def run_once() -> dict[str, Any]:
    """
    Executa 1 rodada de coleta (Playwright), filtra e imprime no console.
    Retorna um dict com métricas úteis para debug.
    """
    config = get_config()

    t0 = time.perf_counter()
    log(
        f"[runner] Iniciando coleta Mercado Livre "
        f"({config.ml.url}) com Playwright..."
    )
    log(
        f"[runner] MIN_DISCOUNT_PCT={config.scrape.min_discount_pct} | "
        f"ML_MAX_SCROLLS={config.scrape.max_scrolls} | "
        f"NUMBER_OF_PAGES={config.scrape.number_of_pages} | "
        f"ML_SCROLL_DELAY_S={config.scrape.scroll_delay_s} | "
        f"ML_PAGE_DELAY_S={config.scrape.page_delay_s}"
    )

    try:
        offers = await scrape_ml_offers_playwright(
            ml_config=config.ml,
            scrape_config=config.scrape,
        )
    except Exception as e:
        log(f"[runner] ERRO: coleta falhou: {type(e).__name__}: {e}")
        raise

    t1 = time.perf_counter()
    log(f"[runner] Coleta OK: {len(offers)} itens brutos em {t1 - t0:.2f}s")

    filtered: list[ScrapedOffer] = []
    for o in offers:
        if config.scrape.only_with_old_price and not o.old_price_cents:
            continue
        if o.discount_pct is None:
            continue
        if o.discount_pct < config.scrape.min_discount_pct:
            continue
        filtered.append(o)

    filtered.sort(key=_offer_sort_key)

    log(
        f"[runner] Após filtro: {len(filtered)} itens "
        f"(>= {config.scrape.min_discount_pct:.2f}% desconto)"
    )

    show = filtered[: config.max_items_print]
    if show and config.affiliate.concurrency > 0:
        await enrich_offers_affiliate_details(
            show,
            config=config.affiliate,
        )
    log("-" * 90)
    for idx, o in enumerate(show, start=1):
        log(
            f"[{idx:02d}] {o.title}"
            f"\n     De: {format_brl(o.old_price_cents)}"
            f" | Agora: {format_brl(o.price_cents)}"
            f" | Desc: {('-' if o.discount_pct is None else f'{o.discount_pct:.0f}%')}"  # noqa: E501
            f" | Comissão: {format_pct(o.commission_pct)}"
            f"\n     URL: {o.url}"
            f"\n     Link afiliado: {o.affiliate_link or '-'}"
            f"\n     Código afiliação: {o.affiliation_id or '-'}"
            f"\n     MLB ID: {o.external_id}"
            f"\n     Image URL: {o.image_url}"
            f"\n     Marketplace: {o.marketplace}"
        )
        if config.scrape.debug_dump:
            log(f"     DEBUG: {asdict(o)}\n")

    if not show:
        log("[runner] Nenhum item passou no filtro. Sugestões:")
        log("  - reduza MIN_DISCOUNT_PCT (ex.: 30)")
        log("  - aumente ML_MAX_SCROLLS (ex.: 6)")
        log(
            "  - defina ONLY_WITH_OLD_PRICE=false para "
            "permitir itens sem preço antigo"
        )

    t2 = time.perf_counter()
    metrics = {
        "raw_count": len(offers),
        "filtered_count": len(filtered),
        "shown_count": len(show),
        "min_discount_pct": config.scrape.min_discount_pct,
        "max_scrolls": config.scrape.max_scrolls,
        "number_of_pages": config.scrape.number_of_pages,
        "seconds_total": round(t2 - t0, 2),
        "seconds_scrape": round(t1 - t0, 2),
        "seconds_filter_print": round(t2 - t1, 2),
    }
    log(f"[runner] Métricas: {metrics}")
    return metrics
