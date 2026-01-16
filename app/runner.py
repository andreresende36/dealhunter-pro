# app/runner.py
from __future__ import annotations

import os
import time
from dataclasses import asdict
from typing import Any

from scraper_ml import scrape_ml_offers_playwright, ScrapedOffer

def _env_string(name: str, default: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        return default
    return v

def _env_float(name: str, default: float) -> float:
    v = os.getenv(name, "").strip()
    if not v:
        return default
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name, "").strip()
    if not v:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v in {"1", "true", "yes", "y", "on"}


def _format_brl(cents: int | None) -> str:
    if cents is None:
        return "-"
    val = cents / 100
    s = f"{val:,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def _format_pct(value: float | None) -> str:
    if value is None:
        return "-"
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def _log(msg: str) -> None:
    print(msg, flush=True)


def _offer_sort_key(o: ScrapedOffer) -> tuple:
    disc = o.discount_pct if o.discount_pct is not None else -1.0
    return (-disc, o.price_cents)


async def run_once() -> dict[str, Any]:
    """
    Executa 1 rodada de coleta (Playwright), filtra e imprime no console.
    Retorna um dict com métricas úteis para debug.
    """
    min_discount = _env_float("MIN_DISCOUNT_PCT", 50.0)
    max_scrolls = _env_int("ML_MAX_SCROLLS", 4)
    number_of_pages = _env_int("NUMBER_OF_PAGES", 1)
    scroll_delay_s = _env_float("ML_SCROLL_DELAY_S", 0.45)
    page_delay_s = _env_float("ML_PAGE_DELAY_S", 0.0)
    ml_url = _env_string("ML_URL", "https://www.mercadolivre.com.br/ofertas")
    card_selector= _env_string("CARD_SELECTOR", ".andes-card.poly-card.poly-card--grid-card.poly-card--xlarge.andes-card--flat.andes-card--padding-0.andes-card--animated")
    title_selector=_env_string("TITLE_SELECTOR", ".poly-component__title-wrapper")
    picture_selector= _env_string("PICTURE_SELECTOR", ".poly-component__picture")
    price_fraction_selector= _env_string("PRICE_FRACTION_SELECTOR", "span.andes-money-amount.andes-money-amount--cents-superscript span.andes-money-amount__fraction")
    price_cents_selector= _env_string("PRICE_CENTS_SELECTOR", "span.andes-money-amount.andes-money-amount--cents-superscript span.andes-money-amount__cents")
    old_fraction_selector= _env_string("OLD_FRACTION_SELECTOR", "s.andes-money-amount.andes-money-amount--previous span.andes-money-amount__fraction")
    old_cents_selector= _env_string("OLD_CENTS_SELECTOR", "s.andes-money-amount.andes-money-amount--previous span.andes-money-amount__cents")
    discount_selector= _env_string("DISCOUNT_SELECTOR", "span.andes-money-amount__discount.poly-price__disc--pill")
    commission_selector = _env_string("COMMISSION_SELECTOR", "span.stripe-commission__percentage")
    commission_selector_alternative = _env_string(
        "COMMISSION_SELECTOR_ALTERNATIVE",
        "div.stripe-commission__info span",
    )
    button_selector = _env_string("BUTTON_SELECTOR", "span.andes-button__text")
    affiliate_share_text = _env_string("AFFILIATE_SHARE_TEXT", "Compartilhar")
    affiliate_link_selector = _env_string(
        "AFFILIATE_LINK_SELECTOR",
        '[data-testid="text-field__label_link"]',
    )
    affiliation_id_selector = _env_string(
        "AFFILIATION_ID_SELECTOR",
        '[data-testid="text-field__label_id"]',
    )
    

    max_items_print = _env_int("MAX_ITEMS_PRINT", 20)
    only_with_old_price = _env_bool("ONLY_WITH_OLD_PRICE", default=False)
    debug_dump = _env_bool("DEBUG_DUMP", default=False)

    t0 = time.perf_counter()
    _log(f"[runner] Iniciando coleta Mercado Livre ({ml_url}) com Playwright...")
    _log(
        f"[runner] MIN_DISCOUNT_PCT={min_discount} | ML_MAX_SCROLLS={max_scrolls} | "
        f"NUMBER_OF_PAGES={number_of_pages} | ML_SCROLL_DELAY_S={scroll_delay_s} | ML_PAGE_DELAY_S={page_delay_s}"
    )

    try:
        offers = await scrape_ml_offers_playwright(
            max_scrolls=max_scrolls,
            number_of_pages=number_of_pages,
            scroll_delay_s=scroll_delay_s,
            page_delay_s=page_delay_s,
            url=ml_url,
            card_selector=card_selector,
            title_selector=title_selector,
            picture_selector=picture_selector,
            price_fraction_selector=price_fraction_selector,
            price_cents_selector=price_cents_selector,
            old_fraction_selector=old_fraction_selector,
            old_cents_selector=old_cents_selector,
            discount_selector=discount_selector,
            commission_selector=commission_selector,
            commission_selector_alternative=commission_selector_alternative,
            button_selector=button_selector,
            affiliate_share_text=affiliate_share_text,
            affiliate_link_selector=affiliate_link_selector,
            affiliation_id_selector=affiliation_id_selector,
            debug=debug_dump
        )
    except Exception as e:
        _log(f"[runner] ERRO: coleta falhou: {type(e).__name__}: {e}")
        raise

    t1 = time.perf_counter()
    _log(f"[runner] Coleta OK: {len(offers)} itens brutos em {t1 - t0:.2f}s")

    filtered: list[ScrapedOffer] = []
    for o in offers:
        if only_with_old_price and not o.old_price_cents:
            continue
        if o.discount_pct is None:
            continue
        if o.discount_pct < min_discount:
            continue
        filtered.append(o)

    filtered.sort(key=_offer_sort_key)

    _log(f"[runner] Após filtro: {len(filtered)} itens (>= {min_discount:.2f}% desconto)")

    show = filtered[:max_items_print]
    _log("-" * 90)
    for idx, o in enumerate(show, start=1):
        _log(
            f"[{idx:02d}] {o.title}"
            f"\n     De: {_format_brl(o.old_price_cents)}"
            f" | Agora: {_format_brl(o.price_cents)}"
            f" | Desc: {('-' if o.discount_pct is None else f'{o.discount_pct:.0f}%')}"
            f" | Comissão: {_format_pct(o.commission_pct)}"
            f"\n     URL: {o.url}"
            f"\n     Link afiliado: {o.affiliate_link or '-'}"
            f"\n     Código afiliação: {o.affiliation_id or '-'}"
            f"\n     MLB ID: {o.external_id}"
            f"\n     Image URL: {o.image_url}"
            f"\n     Marketplace: {o.marketplace}"
        )
        if debug_dump:
            _log(f"     DEBUG: {asdict(o)}\n")

    if not show:
        _log("[runner] Nenhum item passou no filtro. Sugestões:")
        _log("  - reduza MIN_DISCOUNT_PCT (ex.: 30)")
        _log("  - aumente ML_MAX_SCROLLS (ex.: 6)")
        _log("  - defina ONLY_WITH_OLD_PRICE=false para permitir itens sem preço antigo")

    t2 = time.perf_counter()
    metrics = {
        "raw_count": len(offers),
        "filtered_count": len(filtered),
        "shown_count": len(show),
        "min_discount_pct": min_discount,
        "max_scrolls": max_scrolls,
        "number_of_pages": number_of_pages,
        "seconds_total": round(t2 - t0, 2),
        "seconds_scrape": round(t1 - t0, 2),
        "seconds_filter_print": round(t2 - t1, 2),
    }
    _log(f"[runner] Métricas: {metrics}")
    return metrics
