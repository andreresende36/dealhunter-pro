"""Serviço para enriquecimento de ofertas com dados faltantes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from playwright.async_api import async_playwright  # type: ignore

from shared.config.settings import AffiliateConfig, MLConfig
from shared.constants import (
    DEFAULT_ACCEPT_LANGUAGE,
    DEFAULT_USER_AGENT,
)
from adapters.external.playwright_utils import (
    resolve_storage_state_path,
    route_block_heavy_resources,
)
from shared.utils.price import (
    calc_discount,
    discount_to_float,
    infer_old_price_from_card_text,
    money_parts_to_cents,
    parse_commission_pct,
)
from shared.utils.logging import log
from shared.utils.rate_limiter import get_ml_circuit_breaker, get_ml_rate_limiter
from shared.utils.retry import retry_with_backoff


@dataclass
class EnrichmentResult:
    """Resultado do enriquecimento de uma oferta."""

    old_fraction: Optional[str] = None
    old_cents: Optional[str] = None
    old_price_cents: Optional[int] = None
    discount_pct: Optional[int] = None
    affiliate_link: Optional[str] = None
    affiliation_id: Optional[str] = None


async def _enrich_with_page(
    page,
    url: str,
    current_price_cents: int,
    ml_config: MLConfig,
    affiliate_config: AffiliateConfig,
    timeout_ms: int,
    request_delay_s: float,
    result: EnrichmentResult,
) -> EnrichmentResult:
    """
    Executa o enriquecimento usando uma página já criada.

    Args:
        page: Página do Playwright
        url: URL para acessar
        current_price_cents: Preço atual
        ml_config: Configuração ML
        affiliate_config: Configuração de afiliados
        timeout_ms: Timeout
        request_delay_s: Delay após processar
        result: Objeto de resultado para preencher

    Returns:
        EnrichmentResult preenchido
    """
    # Aplica rate limiting para não sobrecarregar o ML
    rate_limiter = get_ml_rate_limiter()
    await rate_limiter.acquire()

    # Usa circuit breaker para proteção contra falhas em cascata
    circuit_breaker = get_ml_circuit_breaker()

    try:
        # Tenta acessar a página com retry e proteção de circuit breaker
        async def _fetch_with_protection():
            await retry_with_backoff(
                lambda: page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms),
                max_retries=3,
                initial_delay=1.0,
                max_delay=10.0,
                retryable_exceptions=(Exception,),
            )

        await circuit_breaker.call(_fetch_with_protection)

    except Exception as e:
        log(f"[enrichment] Erro ao acessar {url}: {e}")
        return result

    try:
        # Aguarda carregamento dos elementos
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    # Extrai old_fraction e old_cents
    try:
        old_fraction_elem = page.locator(ml_config.old_fraction_selector).first
        old_cents_elem = page.locator(ml_config.old_cents_selector).first

        if await old_fraction_elem.count() > 0:
            old_fraction_text = await old_fraction_elem.text_content() or ""
            old_cents_text = ""
            if await old_cents_elem.count() > 0:
                old_cents_text = await old_cents_elem.text_content() or ""

            result.old_fraction = old_fraction_text.strip()
            result.old_cents = old_cents_text.strip() if old_cents_text else None

            # Calcula old_price_cents
            result.old_price_cents = money_parts_to_cents(
                result.old_fraction,
                result.old_cents,
            )
    except Exception as e:
        log(f"[enrichment] Erro ao extrair old_price de {url}: {e}")

    # Se não encontrou preço antigo pelos seletores, tenta inferir do texto
    if result.old_price_cents is None:
        try:
            page_text = await page.locator("body").text_content() or ""
            result.old_price_cents = infer_old_price_from_card_text(
                page_text, current_price_cents
            )
        except Exception:
            pass

    # Extrai discount_pct
    try:
        discount_elem = page.locator(ml_config.discount_selector).first
        if await discount_elem.count() > 0:
            discount_text = await discount_elem.text_content() or ""
            result.discount_pct = discount_to_float(discount_text)
    except Exception:
        pass

    # Se não encontrou desconto, calcula a partir dos preços
    if result.discount_pct is None and result.old_price_cents:
        result.discount_pct = calc_discount(
            result.old_price_cents, current_price_cents
        )

    # Extrai dados de afiliado (commission_pct, affiliate_link, affiliation_id)
    # Primeiro tenta extrair commission_pct
    commission_pct = None
    if affiliate_config.commission_selector:
        try:
            await page.wait_for_selector(
                affiliate_config.commission_selector, timeout=15000
            )
            commission_text = await page.locator(
                affiliate_config.commission_selector
            ).first.inner_text()
            commission_pct = parse_commission_pct(commission_text)
        except Exception:
            pass

    if commission_pct is None and affiliate_config.commission_selector_alternative:
        try:
            await page.wait_for_selector(
                affiliate_config.commission_selector_alternative, timeout=8000
            )
            info_text = await page.locator(
                affiliate_config.commission_selector_alternative
            ).first.inner_text()
            commission_pct = parse_commission_pct(info_text)
        except Exception:
            pass

    # Clica no botão de compartilhar se necessário
    if affiliate_config.button_selector and affiliate_config.affiliate_share_text:
        try:
            share_button = page.locator(
                affiliate_config.button_selector,
                has_text=affiliate_config.affiliate_share_text,
            )
            if await share_button.count():
                await share_button.first.click(timeout=5000)
        except Exception:
            pass

    # Extrai affiliate_link
    if affiliate_config.affiliate_link_selector:
        try:
            await page.wait_for_selector(
                affiliate_config.affiliate_link_selector, timeout=10000
            )
        except Exception:
            pass
        try:
            link_locator = page.locator(affiliate_config.affiliate_link_selector)
            if await link_locator.count():
                result.affiliate_link = await _read_input_value(link_locator.first)
        except Exception as e:
            log(f"[enrichment] Erro ao extrair affiliate_link de {url}: {e}")

    # Extrai affiliation_id
    if affiliate_config.affiliation_id_selector:
        try:
            await page.wait_for_selector(
                affiliate_config.affiliation_id_selector, timeout=10000
            )
        except Exception:
            pass
        try:
            id_locator = page.locator(affiliate_config.affiliation_id_selector)
            if await id_locator.count():
                result.affiliation_id = await _read_input_value(id_locator.first)
        except Exception as e:
            log(f"[enrichment] Erro ao extrair affiliation_id de {url}: {e}")

    # Delay opcional para rate limiting
    if request_delay_s > 0:
        import asyncio

        await asyncio.sleep(request_delay_s)

    return result


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


async def enrich_offer(
    url: str,
    current_price_cents: int,
    ml_config: MLConfig,
    affiliate_config: AffiliateConfig,
    timeout_ms: int = 60000,
    request_delay_s: float = 0.0,
    use_browser_pool: bool = True,
) -> EnrichmentResult:
    """
    Enriquece uma oferta individual acessando a página do produto.

    Args:
        url: URL da oferta
        current_price_cents: Preço atual em centavos (para validação)
        ml_config: Configuração do ML com seletores
        affiliate_config: Configuração de afiliados
        timeout_ms: Timeout para carregar a página
        request_delay_s: Delay após processar (para rate limiting)
        use_browser_pool: Se True, usa o browser pool (mais rápido). Se False, cria browser dedicado.

    Returns:
        EnrichmentResult com dados extraídos
    """
    result = EnrichmentResult()

    async def _fetch_page(page) -> None:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

    # Usa browser pool se disponível (mais rápido e eficiente)
    if use_browser_pool:
        try:
            from adapters.workers.browser_pool import get_browser_pool

            pool = await get_browser_pool(size=3)
            async with pool.get_page() as page:
                return await _enrich_with_page(
                    page=page,
                    url=url,
                    current_price_cents=current_price_cents,
                    ml_config=ml_config,
                    affiliate_config=affiliate_config,
                    timeout_ms=timeout_ms,
                    request_delay_s=request_delay_s,
                    result=result,
                )
        except Exception as e:
            log(f"[enrichment] Erro ao usar browser pool, fallback para browser dedicado: {e}")
            # Fallback para browser dedicado

    # Modo legacy: cria browser dedicado (mais lento mas mais seguro)
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

        page = await context.new_page()

        try:
            result = await _enrich_with_page(
                page=page,
                url=url,
                current_price_cents=current_price_cents,
                ml_config=ml_config,
                affiliate_config=affiliate_config,
                timeout_ms=timeout_ms,
                request_delay_s=request_delay_s,
                result=result,
            )
        finally:
            await page.close()
            await context.close()
            await browser.close()

    return result
