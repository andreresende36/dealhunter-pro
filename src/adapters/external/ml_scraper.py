"""Scraper principal do Mercado Livre."""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from typing import Optional, TypedDict

from playwright.async_api import async_playwright  # type: ignore

from shared.config.settings import MLConfig, ScrapeConfig
from core.domain import ScrapedOffer
from shared.constants import (
    DEFAULT_ACCEPT_LANGUAGE,
    DEFAULT_USER_AGENT,
    MAX_CARDS_PER_PAGE,
    SCROLL_DELAY_MULTIPLIER,
    SCROLL_PIXELS,
    TIMEOUT_MEDIUM,
    TIMEOUT_PAGE_LOAD,
    TIMEOUT_SELECTOR,
    TIMEOUT_SHORT,
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
    price_to_cents,
)
from shared.utils.url import (
    ML_BASE_URL,
    ML_DOMAIN,
    external_id_from_url,
    normalize_ml_url,
    url_with_page,
)


DEBUG_DIR = pathlib.Path("debug")


class CardRow(TypedDict):
    """Estrutura de dados de um card raspado."""

    href: str
    title: str
    image_url: str
    price_fraction: str
    price_cents: str
    old_fraction: str
    old_cents: str
    discount_text: str
    card_text: str


@dataclass(frozen=True)
class ScrapeSelectors:
    """Seletores CSS para scraping."""

    card: str
    title: str
    picture: str
    price_fraction: str
    price_cents: str
    old_fraction: str
    old_cents: str
    discount: str


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

        # Espera mínimo reduzido e usa wait_for_load_state quando possível
        min_delay = max(100, int(scroll_delay_s * 1000 * SCROLL_DELAY_MULTIPLIER))
        await page.wait_for_timeout(min_delay)

        # Espera estado de rede mais estável se ainda há scrolls disponíveis
        try:
            await page.wait_for_load_state("networkidle", timeout=min_delay * 2)
        except Exception:
            # Se timeout, continua mesmo assim
            pass

        cur = await page.locator(card_selector).count()
        if cur <= prev:
            no_growth_count += 1
            # Se não cresceu 2 vezes seguidas, pára
            if no_growth_count >= 2:
                break
        else:
            no_growth_count = 0
        prev = cur


def _row_text(row: CardRow, key: str) -> str:
    """Extrai texto de uma chave do row."""
    value = row.get(key) or ""
    return value.strip()


async def _collect_page_items(
    page,
    selectors: ScrapeSelectors,
    max_scrolls: int,
    scroll_delay_s: float,
    debug: bool,
    debug_dir: pathlib.Path,
    page_num: int,
) -> list[CardRow]:
    """Coleta itens de uma página."""
    await try_accept_cookies(page)
    # Timeout reduzido de 20s para 10s - mais agressivo
    await page.wait_for_selector(selectors.card, timeout=TIMEOUT_SELECTOR)
    await _scroll_until_no_growth(page, selectors.card, max_scrolls, scroll_delay_s)

    if debug:
        (debug_dir / f"ml_ofertas_rendered_p{page_num}.html").write_text(
            await page.content(),
            encoding="utf-8",
        )
        await page.screenshot(
            path=str(debug_dir / f"ml_ofertas_p{page_num}.png"), full_page=True
        )

    return await page.eval_on_selector_all(
        selectors.card,
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
            return cards.slice(0, {MAX_CARDS_PER_PAGE}).map(card => {{
                const href = pickAttr(card, 'a[href]', 'href');
                const title = pick(card, '{selectors.title}');
                const image_url =
                pickAttr(card, '{selectors.picture}', 'src') ||
                pickAttr(card, '{selectors.picture}', 'data-src');
                const price_fraction = pick(card,'{selectors.price_fraction}');
                const price_cents = pick(card,'{selectors.price_cents}');
                const old_fraction = pick(card,'{selectors.old_fraction}');
                const old_cents = pick(card,'{selectors.old_cents}');
                const discount_text = pick(card, '{selectors.discount}');
                const card_text = (card.innerText || '').trim();
                return {{
                    href, title, image_url,
                    price_fraction, price_cents,
                    old_fraction, old_cents,
                    discount_text,
                    card_text
                }};
            }});
        }}
        """,
    )


def _build_offer_from_row(row: CardRow, seen_ids: set[str]) -> Optional[ScrapedOffer]:
    """Constrói um ScrapedOffer a partir de um CardRow."""
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

    old_price_cents = money_parts_to_cents(
        _row_text(row, "old_fraction"),
        _row_text(row, "old_cents") or None,
    )
    if old_price_cents is None:
        old_price_cents = infer_old_price_from_card_text(
            _row_text(row, "card_text"), price_cents
        )

    discount_pct = discount_to_float(_row_text(row, "discount_text"))
    if discount_pct is None:
        discount_pct = calc_discount(old_price_cents, price_cents)

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
        old_price_cents=old_price_cents,
        discount_pct=discount_pct if discount_pct is not None else None,
        commission_pct=None,
        affiliate_link=None,
        affiliation_id=None,
        source="ml_offers_playwright",
    )


async def scrape_ml_offers_playwright(
    ml_config: MLConfig,
    scrape_config: ScrapeConfig,
) -> list[ScrapedOffer]:
    """Raspa ofertas do Mercado Livre usando Playwright."""
    offers: list[ScrapedOffer] = []
    seen_ids: set[str] = set()

    debug_dir = DEBUG_DIR
    debug_dir.mkdir(parents=True, exist_ok=True)

    selectors = ScrapeSelectors(
        card=ml_config.card_selector,
        title=ml_config.title_selector,
        picture=ml_config.picture_selector,
        price_fraction=ml_config.price_fraction_selector,
        price_cents=ml_config.price_cents_selector,
        old_fraction=ml_config.old_fraction_selector,
        old_cents=ml_config.old_cents_selector,
        discount=ml_config.discount_selector,
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context_kwargs = {
            "locale": "pt-BR",
            "user_agent": DEFAULT_USER_AGENT,
            "extra_http_headers": {"Accept-Language": DEFAULT_ACCEPT_LANGUAGE},
            # Desabilita imagens, fontes e CSS para acelerar carregamento
            "ignore_https_errors": True,
            "bypass_csp": True,
        }
        storage_state_path = resolve_storage_state_path()
        if storage_state_path:
            context_kwargs["storage_state"] = storage_state_path
        context = await browser.new_context(**context_kwargs)

        await context.route("**/*", route_block_heavy_resources)

        page = await context.new_page()

        for page_num in range(1, max(1, scrape_config.number_of_pages) + 1):
            page_url = url_with_page(ml_config.url, page_num)

            # wait_until="commit" é mais rápido que "domcontentloaded"
            # timeout reduzido de 60s para 30s
            resp = await page.goto(page_url, wait_until="commit", timeout=TIMEOUT_PAGE_LOAD)
            print(
                f"[ml] page={page_num} goto.status =",
                resp.status if resp else None,
                flush=True,
            )
            print(f"[ml] page={page_num} final.url   =", page.url, flush=True)
            print(f"[ml] page={page_num} title       =", await page.title(), flush=True)

            items = await _collect_page_items(
                page,
                selectors=selectors,
                max_scrolls=scrape_config.max_scrolls,
                scroll_delay_s=scrape_config.scroll_delay_s,
                debug=scrape_config.debug_dump,
                debug_dir=debug_dir,
                page_num=page_num,
            )

            if scrape_config.debug_dump:
                all_items_path = debug_dir / "items.json"
                if all_items_path.exists():
                    existing_items = json.loads(
                        all_items_path.read_text(encoding="utf-8")
                    )
                else:
                    existing_items = []
                existing_items.extend(items)
                all_items_path.write_text(
                    json.dumps(existing_items, indent=2, default=str),
                    encoding="utf-8",
                )

            print(f"[ml] page={page_num} cards =", len(items), flush=True)

            for row in items:
                offer = _build_offer_from_row(row, seen_ids)
                if not offer:
                    continue
                offers.append(offer)

            # respiro entre páginas (evita estresse/anti-bot)
            await page.wait_for_timeout(int(scrape_config.page_delay_s * 1000))

        await context.close()
        await browser.close()

    return offers
