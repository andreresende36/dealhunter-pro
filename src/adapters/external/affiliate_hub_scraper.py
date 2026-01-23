"""Scraper para a Central de Afiliados do Mercado Livre."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Optional, TypedDict

from playwright.async_api import async_playwright  # type: ignore

from shared.config.settings import AffiliateConfig, DatabaseConfig, MLConfig
from core.domain import ScrapedOffer
from shared.constants import (
    DEFAULT_ACCEPT_LANGUAGE,
    DEFAULT_USER_AGENT,
    DELAY_AFTER_SCROLL,
    DELAY_BETWEEN_ACTIONS,
    DELAY_INITIAL_RENDER,
    FINAL_WAIT_MULTIPLIER,
    SCROLL_PIXELS,
    TIMEOUT_NETWORK_IDLE,
    TIMEOUT_PAGE_LOAD,
    TIMEOUT_SELECTOR,
    TIMEOUT_SHORT,
)
from adapters.external.playwright_utils import (
    resolve_storage_state_path,
    route_block_heavy_resources,
    try_accept_cookies,
)
from shared.utils.price import (
    money_parts_to_cents,
    parse_commission_pct,
    price_to_cents,
)
from shared.utils.url import (
    ML_BASE_URL,
    ML_DOMAIN,
    external_id_from_url,
    normalize_ml_url,
)
from shared.utils.logging import log

DEBUG_DIR = pathlib.Path("debug")


def _build_card_extraction_js(selectors: AffiliateHubSelectors) -> str:
    """
    Constrói o código JavaScript para extração de dados dos cards.

    Os seletores são inseridos via f-strings para evitar problemas de serialização.
    """
    return f"""
        (cards) => {{
            const pick = (root, sel) => {{
                if (!sel) return '';
                const el = root.querySelector(sel);
                return el ? (el.textContent || '').trim() : '';
            }};
            const pickAttr = (root, sel, attr) => {{
                if (!sel) return '';
                const el = root.querySelector(sel);
                return el ? (el.getAttribute(attr) || '').trim() : '';
            }};
            // Tenta múltiplos seletores para price_cents se o primeiro falhar
            const pickPriceCents = (root) => {{
                const sel1 = '{selectors.price_cents}';
                let cents = pick(root, sel1);
                if (!cents) {{
                    const altSelectors = [
                        'span.andes-money-amount__cents',
                        '.andes-money-amount__cents',
                        '[class*="cents"]'
                    ];
                    for (const altSel of altSelectors) {{
                        cents = pick(root, altSel);
                        if (cents) break;
                    }}
                }}
                return cents || '';
            }};
            // Tenta múltiplos seletores para commission se o primeiro falhar
            const pickCommission = (root) => {{
                const sel1 = '{selectors.commission}';
                let commission = pick(root, sel1);
                if (!commission) {{
                    const altSelectors = [
                        'span.stripe-commission__percentage',
                        'div.stripe-commission__info span',
                        '[class*="commission"]',
                        '[class*="ganhos"]'
                    ];
                    for (const altSel of altSelectors) {{
                        commission = pick(root, altSel);
                        if (commission) break;
                    }}
                }}
                return commission || '';
            }};
            // Extrai porcentagem de desconto do texto
            const parseDiscountPct = (str) => {{
                if (!str) return '';
                const match = str.match(/(\\d{{1,3}})\\s*%+/);
                if (!match) return '';
                return match[1];
            }};

            return cards.map(card => {{
                const href = pickAttr(card, 'a[href]', 'href');
                const title = pick(card, '{selectors.title}');
                const image_url =
                    pickAttr(card, '{selectors.picture}', 'src') ||
                    pickAttr(card, '{selectors.picture}', 'data-src');
                const price_fraction_str = pick(card, '{selectors.price_fraction}');
                const price_cents_str = pickPriceCents(card);
                const old_fraction_str = pick(card, '{selectors.old_fraction}');
                const old_cents_str = pick(card, '{selectors.old_cents}');
                const discount_text = pick(card, '{selectors.discount}');
                const commission_text = pickCommission(card);
                const card_text = (card.innerText || '').trim();

                return {{
                    href, title, image_url,
                    price_fraction: price_fraction_str || '',
                    price_cents: price_cents_str || '',
                    old_fraction: old_fraction_str || '',
                    old_cents: old_cents_str || '',
                    discount_pct: parseDiscountPct(discount_text),
                    commission_text,
                    card_text
                }};
            }});
        }}
        """


class AffiliateCardRow(TypedDict):
    """Estrutura de dados de um card da Central de Afiliados."""

    href: str
    title: str
    image_url: str
    price_fraction: str
    price_cents: str
    old_fraction: str
    old_cents: str
    discount_pct: str
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
    old_fraction: str
    old_cents: str
    discount: str
    commission: str


async def _check_for_error_messages(page) -> bool:
    """Verifica se há mensagens de erro na página."""
    error_selectors = [
        ".ui-snackbar--error",
        '[class*="error"]',
        '[class*="erro"]',
    ]

    # Verifica seletores CSS
    for selector in error_selectors:
        try:
            error_elem = page.locator(selector).first
            # Verifica se o elemento existe usando wait_for com timeout curto
            try:
                await error_elem.wait_for(state="visible", timeout=TIMEOUT_SHORT)
                error_text = await error_elem.text_content()
                if error_text and len(error_text.strip()) > 0:
                    log(
                        f"[affiliate_hub] Mensagem de erro detectada: {error_text[:100]}"
                    )
                    return True
            except (TimeoutError, Exception) as e:
                # Timeout ou elemento não encontrado - comportamento esperado quando não há erro
                # Verifica se é realmente um timeout (comportamento normal) ou outro erro
                error_str = str(e).lower()
                if "timeout" in error_str:
                    # Timeout esperado - não há erro na página, continua procurando
                    continue
                # Outro tipo de erro - loga mas continua
                log(f"[affiliate_hub] Erro ao verificar seletor {selector}: {e}")
                continue
        except Exception as e:
            # Erros inesperados - loga mas continua
            error_str = str(e).lower()
            if "timeout" not in error_str:
                log(f"[affiliate_hub] Erro ao verificar seletor {selector}: {e}")
            continue

    # Verifica textos de erro comuns usando get_by_text
    error_texts = [
        "ocorreu um erro",
        "não foi possível",
        "tente novamente",
        "erro ao carregar",
        "sem resultados",
    ]

    for error_text in error_texts:
        try:
            error_elem = page.get_by_text(error_text, exact=False).first
            # Verifica se o elemento existe usando wait_for com timeout curto
            try:
                await error_elem.wait_for(state="visible", timeout=TIMEOUT_SHORT)
                visible_text = await error_elem.text_content()
                if visible_text:
                    log(
                        f"[affiliate_hub] Mensagem de erro detectada: {visible_text[:100]}"
                    )
                    return True
            except (TimeoutError, Exception) as e:
                # Timeout ou elemento não encontrado - comportamento esperado quando não há erro
                # Verifica se é realmente um timeout (comportamento normal) ou outro erro
                error_str = str(e).lower()
                if "timeout" in error_str:
                    # Timeout esperado - não há erro na página, continua procurando
                    continue
                # Outro tipo de erro - loga mas continua
                log(f"[affiliate_hub] Erro ao verificar texto '{error_text}': {e}")
                continue
        except Exception as e:
            # Erros inesperados - loga mas continua
            error_str = str(e).lower()
            if "timeout" not in error_str:
                log(f"[affiliate_hub] Erro ao verificar texto '{error_text}': {e}")
            continue

    return False


async def _extract_card_data(
    page,
    card_selector: str,
    selectors: AffiliateHubSelectors,
) -> list[AffiliateCardRow]:
    """Extrai dados de todos os cards visíveis no momento."""
    try:
        js_code = _build_card_extraction_js(selectors)
        items = await page.eval_on_selector_all(card_selector, js_code)
        return items
    except Exception as e:
        log(f"[affiliate_hub] Erro ao extrair dados dos cards: {e}")
        return []


def _collect_new_items(
    items: list[AffiliateCardRow],
    collected_items: list[AffiliateCardRow],
    seen_hrefs: set[str],
) -> int:
    """
    Coleta novos items de uma lista, evitando duplicatas.

    Otimizado para processar apenas items com href válido e normalizado.

    Returns:
        Número de novos items coletados.
    """
    new_count = 0
    for item in items:
        href = item.get("href", "").strip()
        if not href:
            continue

        normalized_href = normalize_ml_url(href)
        if normalized_href and normalized_href not in seen_hrefs:
            seen_hrefs.add(normalized_href)
            collected_items.append(item)
            new_count += 1
    return new_count


async def _perform_incremental_scroll(
    page,
    card_selector: str,
    selectors: AffiliateHubSelectors,
    scroll_delay_ms: int,
    collected_items: list[AffiliateCardRow],
    seen_hrefs: set[str],
) -> int:
    """
    Realiza scroll incremental coletando dados em cada incremento.

    Returns:
        Número de novos items coletados durante o scroll.
    """
    scroll_increment = SCROLL_PIXELS // 4
    total_new = 0

    for _ in range(4):
        await page.mouse.wheel(0, scroll_increment)
        await page.wait_for_timeout(scroll_delay_ms // 4)

        mid_items = await _extract_card_data(page, card_selector, selectors)
        total_new += _collect_new_items(mid_items, collected_items, seen_hrefs)

    return total_new


async def _recover_cards_after_dom_drop(
    page,
    card_selector: str,
    selectors: AffiliateHubSelectors,
    scroll_delay_ms: int,
    collected_items: list[AffiliateCardRow],
    seen_hrefs: set[str],
    previous_count: int,
    current_count: int,
) -> int:
    """
    Tenta recuperar cards após queda significativa no DOM.

    Returns:
        Número de novos items coletados durante a recuperação.
    """
    # Evita divisão por zero
    if previous_count == 0:
        return 0

    drop_percentage = ((previous_count - current_count) / previous_count) * 100
    if drop_percentage <= 30:
        return 0

    log(
        f"[affiliate_hub] Aviso: DOM caiu de {previous_count} para {current_count} cards "
        f"({drop_percentage:.0f}% de queda). Fazendo scroll adicional e coletas para recuperar cards..."
    )

    await page.mouse.wheel(0, SCROLL_PIXELS // 2)
    await page.wait_for_timeout(scroll_delay_ms)

    total_new = 0
    for retry_attempt in range(3):
        if retry_attempt > 0:
            await page.wait_for_timeout(scroll_delay_ms * retry_attempt)

        retry_items = await _extract_card_data(page, card_selector, selectors)
        retry_new = _collect_new_items(retry_items, collected_items, seen_hrefs)

        if retry_new > 0:
            log(
                f"[affiliate_hub] Coleta adicional (tentativa {retry_attempt + 1}): "
                f"{retry_new} novos cards coletados"
            )
            total_new += retry_new

    return total_new


async def _collect_final_items(
    page,
    card_selector: str,
    selectors: AffiliateHubSelectors,
    scroll_delay_s: float,
    collected_items: list[AffiliateCardRow],
    seen_hrefs: set[str],
) -> None:
    """Coleta dados finais após todos os scrolls."""
    final_wait = max(
        DELAY_INITIAL_RENDER, int(scroll_delay_s * 1000 * FINAL_WAIT_MULTIPLIER)
    )
    log(f"[affiliate_hub] Aguardando {final_wait}ms após scrolls finais...")
    await page.wait_for_timeout(final_wait)

    try:
        await page.wait_for_load_state("networkidle", timeout=TIMEOUT_NETWORK_IDLE)
    except Exception:
        pass

    log("[affiliate_hub] Coletando dados finais dos cards...")
    final_items = await _extract_card_data(page, card_selector, selectors)
    final_new = _collect_new_items(final_items, collected_items, seen_hrefs)

    if final_new > 0:
        log(
            f"[affiliate_hub] {final_new} novos cards coletados na coleta final "
            f"(total: {len(collected_items)})"
        )

    if await _check_for_error_messages(page):
        log("[affiliate_hub] Aviso: Mensagem de erro detectada após scrolls")

    await page.wait_for_timeout(DELAY_AFTER_SCROLL)


async def _scroll_until_no_growth(
    page,
    card_selector: str,
    max_scrolls: int,
    scroll_delay_s: float,
    selectors: AffiliateHubSelectors,
    collected_items: list[AffiliateCardRow],
    seen_hrefs: set[str],
) -> None:
    """
    Rola a página até não haver mais crescimento no número de cards.
    Coleta dados dos cards durante os scrolls para evitar perda de dados.
    """
    previous_dom_count = 0
    no_growth_count = 0
    scroll_delay_ms = max(500, int(scroll_delay_s * 1000))

    # Coleta dados iniciais
    log("[affiliate_hub] Coletando dados iniciais dos cards...")
    initial_items = await _extract_card_data(page, card_selector, selectors)
    initial_new = _collect_new_items(initial_items, collected_items, seen_hrefs)
    log(
        f"[affiliate_hub] {len(initial_items)} cards iniciais coletados "
        f"({initial_new} novos, total acumulado: {len(collected_items)})"
    )

    for scroll_num in range(max_scrolls):
        # Coleta antes do scroll
        pre_scroll_items = await _extract_card_data(page, card_selector, selectors)
        pre_scroll_new = _collect_new_items(
            pre_scroll_items, collected_items, seen_hrefs
        )

        # Scroll incremental com coleta durante
        mid_scroll_new = await _perform_incremental_scroll(
            page, card_selector, selectors, scroll_delay_ms, collected_items, seen_hrefs
        )

        await page.wait_for_timeout(scroll_delay_ms)

        if await _check_for_error_messages(page):
            log("[affiliate_hub] Erro detectado durante scroll. Parando...")
            break

        try:
            await page.wait_for_load_state("networkidle", timeout=scroll_delay_ms * 2)
        except Exception:
            pass

        # Coleta após o scroll
        post_scroll_items = await _extract_card_data(page, card_selector, selectors)
        post_scroll_new = _collect_new_items(
            post_scroll_items, collected_items, seen_hrefs
        )

        current_dom_count = await page.locator(card_selector).count()
        total_new_this_scroll = pre_scroll_new + mid_scroll_new + post_scroll_new

        # Recupera cards após queda no DOM
        recovery_new = await _recover_cards_after_dom_drop(
            page,
            card_selector,
            selectors,
            scroll_delay_ms,
            collected_items,
            seen_hrefs,
            previous_dom_count,
            current_dom_count,
        )
        total_new_this_scroll += recovery_new

        log(
            f"[affiliate_hub] Scroll {scroll_num + 1}/{max_scrolls}: {current_dom_count} cards no DOM, "
            f"{total_new_this_scroll} novos coletados ({pre_scroll_new} antes + {mid_scroll_new} durante + "
            f"{post_scroll_new} depois, total acumulado: {len(collected_items)})"
        )

        # Verifica crescimento
        dom_grew = current_dom_count > previous_dom_count
        collected_new = total_new_this_scroll > 0

        if not dom_grew and not collected_new:
            no_growth_count += 1
            if no_growth_count >= 3:
                log(
                    "[affiliate_hub] Nenhum novo card detectado no DOM nem coletado após 3 scrolls. Parando..."
                )
                break
        else:
            no_growth_count = 0

        previous_dom_count = current_dom_count

    # Coleta final
    await _collect_final_items(
        page, card_selector, selectors, scroll_delay_s, collected_items, seen_hrefs
    )


def _row_text(row: AffiliateCardRow, key: str) -> str:
    """Extrai texto de uma chave do row."""
    value = row.get(key) or ""
    return value.strip() if isinstance(value, str) else str(value)


async def _find_card_selector(page, default_selector: str) -> str | None:
    """Encontra o seletor de card que funciona na página."""
    possible_selectors = [
        default_selector,
        ".andes-card",
        "[class*='andes-card']",
        "[class*='poly-card']",
        "article",
        "[data-testid*='card']",
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
    await try_accept_cookies(page)

    # Aguarda a página carregar
    await page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT_PAGE_LOAD)
    await page.wait_for_timeout(DELAY_INITIAL_RENDER)  # Aguarda renderização inicial

    # Aguarda os cards serem renderizados dinamicamente
    # Tenta esperar pelo container ou pelos próprios cards
    try:
        # Aguarda o container aparecer
        await page.wait_for_selector(
            ".polycards__container, .recommendations-polycards",
            timeout=TIMEOUT_SELECTOR,
        )
        # Aguarda um pouco mais para os cards serem renderizados dentro do container
        await page.wait_for_timeout(DELAY_BETWEEN_ACTIONS)
        # Tenta aguardar pelo menos um card aparecer
        await page.wait_for_selector(
            f"{selectors.card}, .andes-card.poly-card, article",
            timeout=TIMEOUT_SELECTOR,
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

    # Realiza todos os scrolls coletando dados incrementalmente durante o processo
    # Isso evita perder cards que são removidos do DOM durante lazy loading
    log("[affiliate_hub] Iniciando scrolls e coleta incremental de dados dos cards...")
    collected_items: list[AffiliateCardRow] = []
    seen_hrefs: set[str] = set()

    await _scroll_until_no_growth(
        page,
        card_selector,
        max_scrolls,
        scroll_delay_s,
        selectors,
        collected_items,
        seen_hrefs,
    )

    log(
        f"[affiliate_hub] Scrolls concluídos. Total de {len(collected_items)} cards coletados."
    )

    # Verificação final de segurança: remove duplicatas usando URLs normalizadas
    # (A coleta já evita duplicatas, mas esta verificação garante consistência)
    final_unique_items: list[AffiliateCardRow] = []
    final_seen_hrefs: set[str] = set()
    duplicates_removed = 0

    for item in collected_items:
        href = item.get("href", "").strip()
        if not href:
            continue

        normalized_href = normalize_ml_url(href)
        if normalized_href and normalized_href not in final_seen_hrefs:
            final_seen_hrefs.add(normalized_href)
            final_unique_items.append(item)
        else:
            duplicates_removed += 1

    if duplicates_removed > 0:
        log(
            f"[affiliate_hub] Aviso: {duplicates_removed} duplicatas removidas na verificação final. "
            f"Total único: {len(final_unique_items)} cards."
        )

    return (final_unique_items, card_selector)


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

    # Calcula o preço total em centavos usando money_parts_to_cents (igual ao ml_scraper.py)
    price_cents = money_parts_to_cents(
        _row_text(row, "price_fraction"),
        _row_text(row, "price_cents") or None,
    )
    if price_cents is None:
        # Se não temos fraction/cents, tenta extrair do card_text como fallback
        price_cents = price_to_cents(_row_text(row, "card_text"))
    if price_cents is None:
        return None

    # Tenta extrair comissão do campo commission_text primeiro
    commission_pct = parse_commission_pct(_row_text(row, "commission_text"))
    # Se não encontrou, tenta extrair do card_text (ex: "GANHOS 16%")
    if commission_pct is None:
        card_text = _row_text(row, "card_text")
        # Procura por padrões como "GANHOS 16%", "16%", "GANHOS EXTRA 20%", etc.
        commission_pct = parse_commission_pct(card_text)

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
    debug: bool = False,
    database_config: DatabaseConfig | None = None,
) -> list[ScrapedOffer]:
    """
    Raspa produtos da Central de Afiliados do Mercado Livre.

    Args:
        ml_config: Configuração do ML
        affiliate_config: Configuração de afiliados
        max_scrolls: Número máximo de scrolls
        scroll_delay_s: Delay entre scrolls em segundos
        debug: Se True, salva arquivos de debug (HTML e JSON)
        database_config: DEPRECATED - O salvamento no banco é feito em scrape_service.py.
                        Este parâmetro será removido em versões futuras.

    Returns:
        Lista de ofertas coletadas
    """
    offers: list[ScrapedOffer] = []

    debug_dir = DEBUG_DIR
    if debug:
        from scripts.debug_utils import ensure_debug_dir

        ensure_debug_dir(debug_dir)

    selectors = AffiliateHubSelectors(
        card=ml_config.card_selector,
        title=ml_config.title_selector,
        picture=ml_config.picture_selector,
        price_fraction=ml_config.price_fraction_selector,
        price_cents=ml_config.price_cents_selector,
        old_fraction=ml_config.old_fraction_selector,
        old_cents=ml_config.old_cents_selector,
        discount=ml_config.discount_selector,
        commission=affiliate_config.commission_selector,
    )

    async with async_playwright() as p:
        # Abre navegador em modo visível quando debug está ativo
        if debug:
            from scripts.debug_utils import create_debug_browser

            browser = await create_debug_browser(p)
        else:
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

        # Salva dados de debug se solicitado
        if debug:
            from scripts.debug_utils import save_affiliate_hub_debug_data

            await save_affiliate_hub_debug_data(items, page, debug_dir)  # type: ignore[arg-type]

        # Processa items e cria ofertas
        seen_ids: set[str] = set()
        for row in items:
            # Cria oferta sem dados de afiliado (serão coletados posteriormente de forma assíncrona)
            offer = _build_offer_from_affiliate_row(row, seen_ids, None, None)
            if offer:
                offers.append(offer)

        # Aviso sobre database_config deprecado
        if database_config is not None:
            log(
                "[affiliate_hub] AVISO: O parâmetro database_config está deprecado. "
                "O salvamento no banco é feito automaticamente em scrape_service.py."
            )

        await context.close()
        await browser.close()

    log(f"[affiliate_hub] Total de {len(offers)} ofertas coletadas")
    return offers
