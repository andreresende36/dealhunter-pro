"""Validador assíncrono de desconto para ofertas."""

from __future__ import annotations

import asyncio
from typing import Optional

from playwright.async_api import async_playwright  # type: ignore

from config import MLConfig
from models import ScrapedOffer
from scrapers.constants import (
    DEFAULT_ACCEPT_LANGUAGE,
    DEFAULT_USER_AGENT,
)
from scrapers.playwright_utils import (
    resolve_storage_state_path,
    route_block_heavy_resources,
)
from utils.price import (
    calc_discount,
    discount_to_float,
    infer_old_price_from_card_text,
    money_parts_to_cents,
)
from utils.logging import log
from utils.retry import retry_with_backoff


async def _validate_discount_for_offer(
    page,
    offer: ScrapedOffer,
    ml_config: MLConfig,
    timeout_ms: int = 30000,
) -> tuple[Optional[int], Optional[int]]:
    """
    Valida desconto de uma oferta acessando a página do produto.

    Args:
        page: Página do Playwright
        offer: Oferta a ser validada
        ml_config: Configuração do ML com seletores

    Returns:
        Tupla (old_price_cents, discount_pct)
    """

    async def _fetch_page() -> None:
        await page.goto(offer.url, wait_until="domcontentloaded", timeout=timeout_ms)

    try:
        # Usa retry com backoff para acessar a página
        await retry_with_backoff(
            _fetch_page,
            max_retries=3,
            initial_delay=1.0,
            max_delay=10.0,
            retryable_exceptions=(Exception,),
        )
    except Exception as e:
        log(f"[discount_validator] Erro ao acessar {offer.url}: {e}")
        return (None, None)

    try:
        # Aguarda carregamento dos elementos de preço
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    # Extrai preço atual (já temos, mas pode validar)
    current_price_cents = offer.price_cents

    # Extrai preço antigo
    old_price_cents = None
    try:
        old_fraction_elem = page.locator(ml_config.old_fraction_selector).first
        old_cents_elem = page.locator(ml_config.old_cents_selector).first

        if await old_fraction_elem.count() > 0:
            old_fraction_text = await old_fraction_elem.text_content() or ""
            old_cents_text = ""
            if await old_cents_elem.count() > 0:
                old_cents_text = await old_cents_elem.text_content() or ""

            old_price_cents = money_parts_to_cents(
                old_fraction_text.strip(),
                old_cents_text.strip() if old_cents_text else None,
            )
    except Exception:
        pass

    # Se não encontrou preço antigo pelos seletores, tenta inferir do texto da página
    if old_price_cents is None:
        try:
            page_text = await page.locator("body").text_content() or ""
            old_price_cents = infer_old_price_from_card_text(
                page_text, current_price_cents
            )
        except Exception:
            pass

    # Extrai desconto do texto
    discount_pct = None
    try:
        discount_elem = page.locator(ml_config.discount_selector).first
        if await discount_elem.count() > 0:
            discount_text = await discount_elem.text_content() or ""
            discount_pct = discount_to_float(discount_text)
    except Exception:
        pass

    # Se não encontrou desconto, calcula a partir dos preços
    if discount_pct is None and old_price_cents:
        discount_pct = calc_discount(old_price_cents, current_price_cents)

    return (old_price_cents, discount_pct)


async def validate_discounts_parallel(
    offers: list[ScrapedOffer],
    ml_config: MLConfig,
    concurrency: int = 5,
    timeout_ms: int = 30000,
) -> dict[str, tuple[Optional[int], Optional[int]]]:
    """
    Valida descontos de múltiplas ofertas em paralelo.

    Args:
        offers: Lista de ofertas para validar
        ml_config: Configuração do ML
        concurrency: Número máximo de requisições paralelas
        timeout_ms: Timeout por requisição em milissegundos

    Returns:
        Dicionário mapeando external_id para (old_price_cents, discount_pct)
    """
    if not offers:
        return {}

    results: dict[str, tuple[Optional[int], Optional[int]]] = {}
    concurrency = max(1, concurrency)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context_kwargs = {
            "locale": "pt-BR",
            "user_agent": DEFAULT_USER_AGENT,
            "extra_http_headers": {"Accept-Language": DEFAULT_ACCEPT_LANGUAGE},
            "ignore_https_errors": True,
            "bypass_csp": True,
        }
        storage_state_path = resolve_storage_state_path()
        if storage_state_path:
            context_kwargs["storage_state"] = storage_state_path
        context = await browser.new_context(**context_kwargs)
        await context.route("**/*", route_block_heavy_resources)

        queue: asyncio.Queue[ScrapedOffer] = asyncio.Queue()
        for offer in offers:
            queue.put_nowait(offer)

        async def _worker() -> None:
            page = await context.new_page()
            try:
                while True:
                    try:
                        offer = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                    try:
                        old_price, discount = await _validate_discount_for_offer(
                            page, offer, ml_config, timeout_ms
                        )
                        results[offer.external_id] = (old_price, discount)
                    except Exception as e:
                        log(
                            f"[discount_validator] Erro ao processar {offer.external_id}: {e}"
                        )
                        results[offer.external_id] = (None, None)
                    finally:
                        queue.task_done()
            finally:
                await page.close()

        log(
            f"[discount_validator] Validando descontos de {len(offers)} ofertas "
            f"com concorrência {concurrency}..."
        )
        await asyncio.gather(*(_worker() for _ in range(concurrency)))

        await context.close()
        await browser.close()

    success_count = sum(
        1 for v in results.values() if v[0] is not None or v[1] is not None
    )
    log(
        f"[discount_validator] Validação concluída: {success_count}/{len(offers)} "
        f"ofertas validadas com sucesso"
    )

    return results
