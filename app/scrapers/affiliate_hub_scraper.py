"""Scraper para a Central de Afiliados do Mercado Livre."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Optional, TypedDict

from playwright.async_api import async_playwright  # type: ignore

from config import AffiliateConfig, MLConfig
from models import ScrapedOffer
from scrapers.constants import (
    DEFAULT_ACCEPT_LANGUAGE,
    DEFAULT_USER_AGENT,
    SCROLL_PIXELS,
)
from scrapers.playwright_utils import (
    resolve_storage_state_path,
    route_block_heavy_resources,
)
from utils.price import (
    money_parts_to_cents,
    parse_commission_pct,
    price_to_cents,
)
from utils.url import (
    ML_BASE_URL,
    ML_DOMAIN,
    external_id_from_url,
    normalize_ml_url,
)
from utils.logging import log


DEBUG_DIR = pathlib.Path("debug")


class AffiliateCardRow(TypedDict):
    """Estrutura de dados de um card da Central de Afiliados."""

    href: str
    title: str
    image_url: str
    price_fraction: str
    price_cents: str
    commission_text: str
    card_text: str


@dataclass(frozen=True)
class AffiliateHubSelectors:
    """Seletores CSS para scraping da Central de Afiliados."""

    card: str
    title: str
    picture: str
    price_fraction: str
    price_cents: str
    commission: str


async def _try_accept_cookies(page) -> None:
    """Tenta aceitar cookies na página com timeout curto."""
    for label in ("Aceitar cookies", "Aceptar cookies", "Accept cookies"):
        try:
            btn = page.get_by_role("button", name=label)
            if await btn.count(timeout=500):
                await btn.first.click(timeout=1000)
                return
        except Exception:
            pass


async def _scroll_until_no_growth(
    page,
    card_selector: str,
    max_scrolls: int,
    scroll_delay_s: float,
) -> None:
    """Rola a página até não haver mais crescimento no número de cards."""
    prev = 0
    no_growth_count = 0

    for _ in range(max_scrolls):
        await page.mouse.wheel(0, SCROLL_PIXELS)

        min_delay = max(100, int(scroll_delay_s * 1000 * 0.5))
        await page.wait_for_timeout(min_delay)

        try:
            await page.wait_for_load_state("networkidle", timeout=min_delay * 2)
        except Exception:
            pass

        cur = await page.locator(card_selector).count()
        if cur <= prev:
            no_growth_count += 1
            if no_growth_count >= 2:
                break
        else:
            no_growth_count = 0
        prev = cur


def _row_text(row: AffiliateCardRow, key: str) -> str:
    """Extrai texto de uma chave do row."""
    value = row.get(key) or ""
    return value.strip()


async def _find_card_selector(page, default_selector: str) -> str | None:
    """Encontra o seletor de card que funciona na página."""
    print("DEFAUT-------------------------------------", default_selector)
    possible_selectors = [
        default_selector,
        # ".andes-card",
        # "[class*='andes-card']",
        # "[class*='poly-card']",
        # "article",
        # "[data-testid*='card']",
    ]

    for selector in possible_selectors:
        try:
            count = await page.locator(selector).count()
            if count > 0:
                log(
                    f"[affiliate_hub] Encontrados {count} cards com seletor: {selector}"
                )
                return selector
        except Exception:
            continue

    return None


async def _collect_affiliate_hub_items(
    page,
    selectors: AffiliateHubSelectors,
    max_scrolls: int,
    scroll_delay_s: float,
) -> tuple[list[AffiliateCardRow], str | None]:
    """
    Coleta itens da Central de Afiliados.

    Returns:
        Tupla (lista de items, card_selector usado ou None se não encontrado)
    """
    await _try_accept_cookies(page)

    # Aguarda a página carregar
    await page.wait_for_load_state("domcontentloaded", timeout=30000)
    await page.wait_for_timeout(2000)  # Aguarda renderização inicial

    # Aguarda os cards serem renderizados dinamicamente
    # Tenta esperar pelo container ou pelos próprios cards
    try:
        # Aguarda o container aparecer
        await page.wait_for_selector(
            ".polycards__container, .recommendations-polycards", timeout=10000
        )
        # Aguarda um pouco mais para os cards serem renderizados dentro do container
        await page.wait_for_timeout(3000)
        # Tenta aguardar pelo menos um card aparecer
        await page.wait_for_selector(
            f"{selectors.card}, .andes-card.poly-card, article",
            timeout=10000,
            state="visible",
        )
    except Exception:
        # Se não encontrar, continua mesmo assim (pode estar vazio)
        pass

    # Tenta encontrar o seletor de card
    card_selector = await _find_card_selector(page, selectors.card)

    if not card_selector:
        # Debug: informações da página
        log(
            f"[affiliate_hub] Nenhum card encontrado. Título da página: {await page.title()}"
        )
        log(f"[affiliate_hub] URL atual: {page.url}")
        # Tenta encontrar qualquer elemento que possa ser um card
        try:
            all_elements = await page.locator("body > *").count()
            log(f"[affiliate_hub] Total de elementos filhos do body: {all_elements}")
        except Exception:
            pass
        # Retorna lista vazia em vez de falhar
        return ([], None)

    await _scroll_until_no_growth(page, card_selector, max_scrolls, scroll_delay_s)

    items = await page.eval_on_selector_all(
        card_selector,
        f"""
        (cards) => {{
            const pick = (root, sel) => {{
                const el = root.querySelector(sel);
                return el ? (el.textContent || '').trim() : '';
            }};
            const pickAttr = (root, sel, attr) => {{
                const el = root.querySelector(sel);
                return el ? (el.getAttribute(attr) || '').trim() : '';
            }};
            return cards.map(card => {{
                const href = pickAttr(card, 'a[href]', 'href');
                const title = pick(card, '{selectors.title}');
                const image_url =
                    pickAttr(card, '{selectors.picture}', 'src') ||
                    pickAttr(card, '{selectors.picture}', 'data-src');
                const price_fraction = pick(card, '{selectors.price_fraction}');
                const price_cents = pick(card, '{selectors.price_cents}');
                const commission_text = pick(card, '{selectors.commission}');
                const card_text = (card.innerText || '').trim();
                return {{
                    href, title, image_url,
                    price_fraction, price_cents,
                    commission_text,
                    card_text
                }};
            }});
        }}
        """,
    )

    return (items, card_selector)


async def _read_input_or_textarea_value(locator) -> Optional[str]:
    """Lê o valor de um input ou textarea."""
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


async def _extract_affiliate_data_from_card(
    page,
    card_locator,
    affiliate_link_selector: str,
    affiliate_id_selector: str,
) -> tuple[Optional[str], Optional[str]]:
    """
    Extrai link de afiliado e código do produto clicando nos botões de compartilhar.

    Args:
        page: Página do Playwright
        card_locator: Locator do card do produto
        affiliate_link_selector: ID ou seletor do botão/elemento para link (copy_link)
        affiliate_id_selector: ID ou seletor do botão/elemento para código (copy_id)

    Returns:
        Tupla (affiliate_link, affiliation_id)
    """
    try:
        # Encontra o botão "Compartilhar" dentro do card
        share_button = card_locator.locator(
            'button.share-button, [class*="share"], button:has-text("Compartilhar")'
        ).first

        if await share_button.count() == 0:
            return (None, None)

        # Clica no botão Compartilhar
        await share_button.click(timeout=5000)
        await page.wait_for_timeout(800)  # Aguarda modal/menu abrir

        affiliate_link = None
        affiliation_id = None

        # Tenta extrair o link de afiliado
        # Primeiro tenta ler diretamente do input/textarea
        try:
            # Tenta vários seletores possíveis
            link_selectors = [
                f"#{affiliate_link_selector}",
                f'[id="{affiliate_link_selector}"]',
                f'[data-testid="{affiliate_link_selector}"]',
                affiliate_link_selector,
            ]

            for selector in link_selectors:
                try:
                    link_elem = page.locator(selector).first
                    if await link_elem.count() > 0:
                        # Tenta ler como input/textarea primeiro
                        value = await _read_input_or_textarea_value(link_elem)
                        if value:
                            affiliate_link = value
                            break

                        # Se não funcionou, tenta clicar no botão e ler do clipboard
                        try:
                            await link_elem.click(timeout=2000)
                            await page.wait_for_timeout(500)
                            # Tenta ler do clipboard (pode não funcionar em todos os contextos)
                            try:
                                clipboard_text = await page.evaluate(
                                    "async () => await navigator.clipboard.readText()"
                                )
                                if clipboard_text:
                                    affiliate_link = clipboard_text.strip()
                                    break
                            except Exception:
                                pass
                        except Exception:
                            pass
                except Exception:
                    continue
        except Exception as e:
            log(f"[affiliate_hub] Erro ao extrair link: {e}")

        # Tenta extrair o código do produto
        try:
            id_selectors = [
                f"#{affiliate_id_selector}",
                f'[id="{affiliate_id_selector}"]',
                f'[data-testid="{affiliate_id_selector}"]',
                affiliate_id_selector,
            ]

            for selector in id_selectors:
                try:
                    id_elem = page.locator(selector).first
                    if await id_elem.count() > 0:
                        # Tenta ler como input/textarea primeiro
                        value = await _read_input_or_textarea_value(id_elem)
                        if value:
                            affiliation_id = value
                            break

                        # Se não funcionou, tenta clicar no botão e ler do clipboard
                        try:
                            await id_elem.click(timeout=2000)
                            await page.wait_for_timeout(500)
                            # Tenta ler do clipboard
                            try:
                                clipboard_text = await page.evaluate(
                                    "async () => await navigator.clipboard.readText()"
                                )
                                if clipboard_text:
                                    affiliation_id = clipboard_text.strip()
                                    break
                            except Exception:
                                pass
                        except Exception:
                            pass
                except Exception:
                    continue
        except Exception as e:
            log(f"[affiliate_hub] Erro ao extrair código: {e}")

        # Fecha o modal/menu se necessário
        try:
            close_btn = page.locator(
                'button[aria-label="Fechar"], button:has-text("Fechar"), [class*="close"], button[aria-label="Close"]'
            ).first
            if await close_btn.count() > 0:
                await close_btn.click(timeout=1000)
                await page.wait_for_timeout(200)
        except Exception:
            pass

        return (affiliate_link, affiliation_id)
    except Exception as e:
        log(f"[affiliate_hub] Erro ao extrair dados de afiliado: {e}")
        return (None, None)


def _build_offer_from_affiliate_row(
    row: AffiliateCardRow,
    seen_ids: set[str],
    affiliate_link: Optional[str],
    affiliation_id: Optional[str],
) -> Optional[ScrapedOffer]:
    """Constrói um ScrapedOffer a partir de um AffiliateCardRow."""
    href = normalize_ml_url(_row_text(row, "href"))
    if not href or ML_DOMAIN not in href:
        return None

    result = external_id_from_url(href)
    if not result:
        return None
    ext_id, url_type = result
    if ext_id in seen_ids:
        return None

    title = _row_text(row, "title")
    if len(title) < 5:
        return None

    image_url = _row_text(row, "image_url") or None

    price_cents = money_parts_to_cents(
        _row_text(row, "price_fraction"),
        _row_text(row, "price_cents") or None,
    )
    if price_cents is None:
        price_cents = price_to_cents(_row_text(row, "card_text"))
    if price_cents is None:
        return None

    commission_pct = parse_commission_pct(_row_text(row, "commission_text"))

    if url_type == "produto":
        canonical_url = f"https://produto.{ML_DOMAIN}/{ext_id}"
    else:
        canonical_url = f"{ML_BASE_URL}/{url_type}/{ext_id}"

    seen_ids.add(ext_id)
    return ScrapedOffer(
        marketplace="Mercado Livre",
        external_id=ext_id,
        title=title,
        url=canonical_url,
        image_url=image_url,
        price_cents=price_cents,
        old_price_cents=None,  # Será preenchido na validação assíncrona
        discount_pct=None,  # Será calculado na validação assíncrona
        commission_pct=commission_pct,
        affiliate_link=affiliate_link,
        affiliation_id=affiliation_id,
        source="ml_affiliate_hub",
    )


async def scrape_affiliate_hub(
    ml_config: MLConfig,
    affiliate_config: AffiliateConfig,
    max_scrolls: int,
    scroll_delay_s: float,
    concurrency: int = 3,
    debug: bool = False,
) -> list[ScrapedOffer]:
    """
    Raspa produtos da Central de Afiliados do Mercado Livre.

    Args:
        ml_config: Configuração do ML
        affiliate_config: Configuração de afiliados
        max_scrolls: Número máximo de scrolls
        scroll_delay_s: Delay entre scrolls em segundos
        concurrency: Número de requisições paralelas para extrair dados de afiliado
        debug: Se True, salva arquivos de debug (HTML)

    Returns:
        Lista de ofertas coletadas
    """
    offers: list[ScrapedOffer] = []
    seen_ids: set[str] = set()

    debug_dir = DEBUG_DIR
    if debug:
        debug_dir.mkdir(parents=True, exist_ok=True)

    selectors = AffiliateHubSelectors(
        card=ml_config.card_selector,
        title=ml_config.title_selector,
        picture=ml_config.picture_selector,
        price_fraction=ml_config.price_fraction_selector,
        price_cents=ml_config.price_cents_selector,
        commission=affiliate_config.commission_selector,
    )

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

        # Acessa a Central de Afiliados
        log(f"[affiliate_hub] Acessando {ml_config.url}...")
        resp = await page.goto(ml_config.url, wait_until="commit", timeout=30000)
        log(
            f"[affiliate_hub] Status: {resp.status if resp else None}, "
            f"URL final: {page.url}"
        )

        # Coleta todos os cards
        log("[affiliate_hub] Coletando produtos da Central de Afiliados...")
        items, card_selector_used = await _collect_affiliate_hub_items(
            page,
            selectors=selectors,
            max_scrolls=max_scrolls,
            scroll_delay_s=scroll_delay_s,
        )

        if not card_selector_used:
            log("[affiliate_hub] Nenhum produto encontrado na página")
            await context.close()
            await browser.close()
            return []

        log(f"[affiliate_hub] {len(items)} produtos coletados")

        # HTML de debug após coletar os cards
        if debug:
            # Salva o HTML da página
            html_content = await page.content()
            html_path = debug_dir / "affiliate_hub_after_scroll.html"
            html_path.write_text(html_content, encoding="utf-8")
            log(f"[affiliate_hub] HTML após scroll salvo em {html_path}")

        # Extrai dados de afiliado para cada produto
        # Processa sequencialmente na mesma página para evitar conflitos com modais
        log(f"[affiliate_hub] Extraindo dados de afiliado de {len(items)} produtos...")

        for idx, row in enumerate(items):
            try:
                # Localiza o card específico usando nth()
                card_locator = page.locator(card_selector_used).nth(idx)

                # Verifica se o card existe
                if await card_locator.count() == 0:
                    log(
                        f"[affiliate_hub] Card {idx} não encontrado, criando oferta sem dados de afiliado"
                    )
                    offer = _build_offer_from_affiliate_row(row, seen_ids, None, None)
                    if offer:
                        offers.append(offer)
                    continue

                # Extrai dados de afiliado
                affiliate_link, affiliation_id = (
                    await _extract_affiliate_data_from_card(
                        page,
                        card_locator,
                        affiliate_config.affiliate_link_selector,
                        affiliate_config.affiliation_id_selector,
                    )
                )

                offer = _build_offer_from_affiliate_row(
                    row, seen_ids, affiliate_link, affiliation_id
                )
                if offer:
                    offers.append(offer)
            except Exception as e:
                log(f"[affiliate_hub] Erro ao processar produto {idx}: {e}")
                # Tenta criar oferta sem dados de afiliado
                offer = _build_offer_from_affiliate_row(row, seen_ids, None, None)
                if offer:
                    offers.append(offer)

        await context.close()
        await browser.close()

    log(f"[affiliate_hub] Total de {len(offers)} ofertas coletadas")
    return offers
