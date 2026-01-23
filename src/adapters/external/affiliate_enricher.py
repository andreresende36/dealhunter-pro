"""Módulo para enriquecimento de ofertas com detalhes de afiliado."""

from __future__ import annotations

import asyncio
from typing import Optional

from playwright.async_api import async_playwright  # type: ignore

from shared.config.settings import AffiliateConfig
from core.domain import ScrapedOffer
from shared.constants import (
    DEFAULT_ACCEPT_LANGUAGE,
    DEFAULT_USER_AGENT,
)
from adapters.external.playwright_utils import (
    resolve_storage_state_path,
    route_block_heavy_resources,
)
from shared.utils.price import parse_commission_pct


async def _read_input_value(locator) -> Optional[str]:
    """Lê o valor de um input/locator de diferentes formas."""
    try:
        value = await locator.input_value()
        if value:
            return value.strip()
    except Exception:
        pass

    try:
        text = await locator.text_content()
        if text:
            return text.strip()
    except Exception:
        pass

    try:
        value = await locator.get_attribute("value")
        if value:
            return value.strip()
    except Exception:
        pass

    return None


async def _extract_affiliate_details(
    page,
    url: str,
    config: AffiliateConfig,
) -> tuple[Optional[int], Optional[str], Optional[str]]:
    """Extrai detalhes de afiliado de uma página de produto."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception:
        return (None, None, None)

    commission_pct = None
    if config.commission_selector:
        try:
            await page.wait_for_selector(config.commission_selector, timeout=15000)
            commission_text = await page.locator(
                config.commission_selector
            ).first.inner_text()
            commission_pct = parse_commission_pct(commission_text)
        except Exception:
            commission_pct = None

    if commission_pct is None and config.commission_selector_alternative:
        try:
            await page.wait_for_selector(
                config.commission_selector_alternative, timeout=8000
            )
            info_text = await page.locator(
                config.commission_selector_alternative
            ).first.inner_text()
            commission_pct = parse_commission_pct(info_text)
        except Exception:
            commission_pct = None

    if config.button_selector and config.affiliate_share_text:
        try:
            share_button = page.locator(
                config.button_selector, has_text=config.affiliate_share_text
            )
            if await share_button.count():
                await share_button.first.click(timeout=5000)
        except Exception:
            pass

    affiliate_link = None
    if config.affiliate_link_selector:
        try:
            await page.wait_for_selector(config.affiliate_link_selector, timeout=10000)
        except Exception:
            pass
        try:
            link_locator = page.locator(config.affiliate_link_selector)
            if await link_locator.count():
                affiliate_link = await _read_input_value(link_locator.first)
        except Exception:
            affiliate_link = None

    affiliation_id = None
    if config.affiliation_id_selector:
        try:
            await page.wait_for_selector(config.affiliation_id_selector, timeout=10000)
        except Exception:
            pass
        try:
            id_locator = page.locator(config.affiliation_id_selector)
            if await id_locator.count():
                affiliation_id = await _read_input_value(id_locator.first)
        except Exception:
            affiliation_id = None

    return (commission_pct, affiliate_link, affiliation_id)


async def enrich_offers_affiliate_details(
    offers: list[ScrapedOffer],
    config: AffiliateConfig,
    request_delay_s: float = 0.0,
) -> None:
    """Enriquece ofertas com detalhes de afiliado usando concorrência."""
    if not offers:
        return

    concurrency = max(1, config.concurrency)
    delay_s = max(0.0, request_delay_s)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context_kwargs = {
            "locale": "pt-BR",
            "user_agent": DEFAULT_USER_AGENT,
            "extra_http_headers": {"Accept-Language": DEFAULT_ACCEPT_LANGUAGE},
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
                        (
                            commission_pct,
                            affiliate_link,
                            affiliation_id,
                        ) = await _extract_affiliate_details(
                            page,
                            offer.url,
                            config,
                        )
                        offer.commission_pct = commission_pct
                        offer.affiliate_link = affiliate_link
                        offer.affiliation_id = affiliation_id
                    finally:
                        queue.task_done()

                    if delay_s > 0:
                        await asyncio.sleep(delay_s)
            finally:
                await page.close()

        await asyncio.gather(*(_worker() for _ in range(concurrency)))

        await context.close()
        await browser.close()
