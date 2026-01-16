from __future__ import annotations

import asyncio
import os
import pathlib
import re
from dataclasses import dataclass
from typing import Literal, Optional, Tuple, TypedDict
from urllib.parse import parse_qs, parse_qsl, unquote, urlencode, urlparse, urlsplit, urlunsplit
import json

from playwright.async_api import async_playwright # type: ignore

_PRICE_RE = re.compile(r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})|\d+(?:,\d{2})?)")
ML_DOMAIN = "mercadolivre.com.br"
ML_BASE_URL = "https://www.mercadolivre.com.br"
RESOURCE_BLOCK_TYPES = {"image", "font", "media"}
TRACKER_HOST_SNIPPETS = ("doubleclick", "googletagmanager", "google-analytics", "facebook", "hotjar")
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
DEFAULT_ACCEPT_LANGUAGE = "pt-BR,pt;q=0.9,en;q=0.8"
DEBUG_DIR = pathlib.Path("debug")
MAX_CARDS_PER_PAGE = 300
SCROLL_PIXELS = 2400


def _resolve_storage_state_path() -> Optional[str]:
    env_path = os.getenv("PLAYWRIGHT_STORAGE_STATE", "").strip()
    if env_path:
        candidate = pathlib.Path(env_path).expanduser()
        if candidate.exists():
            return str(candidate)
        return None

    default_path = pathlib.Path(__file__).resolve().parent / "storage_state.json"
    if default_path.exists():
        return str(default_path)
    return None


@dataclass
class ScrapedOffer:
    marketplace: str
    external_id: str
    title: str
    url: str
    image_url: Optional[str]
    price_cents: int
    old_price_cents: Optional[int]
    discount_pct: Optional[float]
    commission_pct: Optional[float]
    affiliate_link: Optional[str]
    affiliation_id: Optional[str]
    source: str = "ml_offers_playwright"


@dataclass(frozen=True)
class ScrapeSelectors:
    card: str
    title: str
    picture: str
    price_fraction: str
    price_cents: str
    old_fraction: str
    old_cents: str
    discount: str


class CardRow(TypedDict):
    href: str
    title: str
    image_url: str
    price_fraction: str
    price_cents: str
    old_fraction: str
    old_cents: str
    discount_text: str
    card_text: str

def _parse_price_token(token: str) -> Optional[int]:
    if not token:
        return None
    normalized = token.strip().replace(".", "").replace(",", ".")
    try:
        return int(round(float(normalized) * 100))
    except ValueError:
        return None


def _price_to_cents(text: str) -> Optional[int]:
    if not text:
        return None
    match = _PRICE_RE.search(text)
    if not match:
        return None
    return _parse_price_token(match.group(1))
    
def _all_prices_to_cents(text: str) -> list[int]:
    """
    Extrai todos os valores monetários encontrados no texto e converte para centavos.
    Útil para fallback de preço antigo (que costuma ser o maior valor do card).
    """
    if not text:
        return []

    cents_list: list[int] = []
    for match in _PRICE_RE.finditer(text):
        cents = _parse_price_token(match.group(1))
        if cents is not None:
            cents_list.append(cents)

    return cents_list


def _discount_to_float(text: str) -> Optional[float]:
    if not text:
        return None
    m = re.search(r"(\d{1,3})\s*%+", text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _parse_commission_pct(text: str) -> Optional[float]:
    if not text:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


async def _read_input_value(locator) -> Optional[str]:
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


def _calc_discount(old_cents: Optional[int], price_cents: int) -> Optional[float]:
    if not old_cents or old_cents <= 0:
        return None
    if price_cents >= old_cents:
        return 0.0
    return ((old_cents - price_cents) / old_cents) * 100.0


def _external_id_from_url(url: str) -> Optional[Tuple[str, Literal["p", "up", "produto"]]]:
    """
    Extrai o código MLB/MLBU da URL do Mercado Livre.
    Retorna tupla (external_id, url_type) ou None.

    Tipo 1 (/p/): MLB16069584, "p"
    Tipo 2 (/up/): MLBU3491177949, "up"
    Tipo 3 (produto): MLB-5873070966, "produto"
    """
    if not url:
        return None

    try:
        parsed = urlparse(url)
    except Exception:
        parsed = None

    path = parsed.path if parsed else url

    # Tenta tipo 1: /p/MLB...
    match_p = re.search(r"/p/(MLB\d+)", path, re.IGNORECASE)
    if match_p:
        return (match_p.group(1), "p")

    # Tenta tipo 2: /up/MLBU...
    match_up = re.search(r"/up/(MLBU\d+)", path, re.IGNORECASE)
    if match_up:
        return (match_up.group(1), "up")

    # Tenta tipo 3: produto.mercadolivre.com.br/MLB-...
    host = (parsed.netloc or "").lower() if parsed else ""
    if host.startswith("produto.") and ML_DOMAIN in host:
        match_produto = re.search(r"/(MLB-\d+)", path, re.IGNORECASE)
        if match_produto:
            return (match_produto.group(1), "produto")

    return None


def _normalize_ml_url(href: str) -> str:
    """
    - Resolve URLs relativas
    - Tenta "desencapsular" links de tracking tipo click1.mercadolivre.com.br ... &url=https%3A%2F%2Fwww.mercadolivre.com.br%2F...
    """
    if not href:
        return ""

    if href.startswith("/"):
        href = ML_BASE_URL + href

    try:
        u = urlparse(href)
    except Exception:
        return href

    host = (u.netloc or "").lower()

    # Desencapsula links de tracking comuns (mercadoclics/click1)
    if ML_DOMAIN in host and ("click" in host or "mercadoclics" in host):
        qs = parse_qs(u.query)
        if "url" in qs and qs["url"]:
            try:
                return unquote(qs["url"][0])
            except Exception:
                return qs["url"][0]

    return href


def _digits_only(text: str) -> str:
    return re.sub(r"\D+", "", text or "")


def _money_parts_to_cents(fraction_text: str, cents_text: str | None) -> Optional[int]:
    fraction_digits = _digits_only(fraction_text)
    if not fraction_digits:
        return None

    cents_digits = _digits_only(cents_text or "")
    if not cents_digits:
        cents_digits = "00"
    elif len(cents_digits) == 1:
        cents_digits = cents_digits + "0"
    elif len(cents_digits) > 2:
        cents_digits = cents_digits[:2]

    try:
        return int(fraction_digits) * 100 + int(cents_digits)
    except ValueError:
        return None


def _row_text(row: CardRow, key: str) -> str:
    value = row.get(key) or ""
    return value.strip()


def _infer_old_price_from_card_text(card_text: str, price_cents: int) -> Optional[int]:
    if not card_text:
        return None
    all_prices = _all_prices_to_cents(card_text)
    if not all_prices:
        return None

    bigger_than_current = [p for p in all_prices if p > price_cents]
    if bigger_than_current:
        return max(bigger_than_current)
    return max(all_prices)


def _url_with_page(base_url: str, page_num: int) -> str:
    """
    Garante que o parâmetro page seja aplicado corretamente, mesmo se já existir querystring.
    """
    if page_num <= 1:
        return base_url

    parts = urlsplit(base_url)
    qs = dict(parse_qsl(parts.query, keep_blank_values=True))
    qs["page"] = str(page_num)
    new_query = urlencode(qs)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


async def _try_accept_cookies(page) -> None:
    for label in ("Aceitar cookies", "Aceptar cookies", "Accept cookies"):
        try:
            btn = page.get_by_role("button", name=label)
            if await btn.count():
                await btn.first.click(timeout=1500)
                await page.wait_for_timeout(300)
                return
        except Exception:
            pass


async def _route_block_heavy(route, request) -> None:
    rt = request.resource_type
    url = request.url.lower()

    if rt in RESOURCE_BLOCK_TYPES:
        return await route.abort()

    if any(token in url for token in TRACKER_HOST_SNIPPETS):
        return await route.abort()

    return await route.continue_()


async def _scroll_until_no_growth(
    page,
    card_selector: str,
    max_scrolls: int,
    scroll_delay_s: float,
) -> None:
    prev = 0
    for _ in range(max_scrolls):
        await page.mouse.wheel(0, SCROLL_PIXELS)
        await page.wait_for_timeout(int(scroll_delay_s * 1000))

        cur = await page.locator(card_selector).count()
        if cur <= prev:
            break
        prev = cur


async def _collect_page_items(
    page,
    selectors: ScrapeSelectors,
    max_scrolls: int,
    scroll_delay_s: float,
    debug: bool,
    debug_dir: pathlib.Path,
    page_num: int,
) -> list[CardRow]:
    await _try_accept_cookies(page)
    await page.wait_for_selector(selectors.card, timeout=20000)
    await _scroll_until_no_growth(page, selectors.card, max_scrolls, scroll_delay_s)

    if debug:
        (debug_dir / f"ml_ofertas_rendered_p{page_num}.html").write_text(
            await page.content(),
            encoding="utf-8",
        )
        await page.screenshot(path=str(debug_dir / f"ml_ofertas_p{page_num}.png"), full_page=True)

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
        """
    )


async def _extract_affiliate_details(
    page,
    url: str,
    commission_selector: str,
    button_selector: str,
    affiliate_share_text: str,
    affiliate_link_selector: str,
    affiliation_id_selector: str,
) -> tuple[Optional[float], Optional[str], Optional[str]]:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception:
        return (None, None, None)

    commission_pct = None
    if commission_selector:
        try:
            await page.wait_for_selector(commission_selector, timeout=15000)
            commission_text = await page.locator(commission_selector).first.inner_text()
            commission_pct = _parse_commission_pct(commission_text)
        except Exception:
            commission_pct = None

    if button_selector and affiliate_share_text:
        try:
            share_button = page.locator(button_selector, has_text=affiliate_share_text)
            if await share_button.count():
                await share_button.first.click(timeout=5000)
        except Exception:
            pass

    affiliate_link = None
    if affiliate_link_selector:
        try:
            await page.wait_for_selector(affiliate_link_selector, timeout=10000)
        except Exception:
            pass
        try:
            link_locator = page.locator(affiliate_link_selector)
            if await link_locator.count():
                affiliate_link = await _read_input_value(link_locator.first)
        except Exception:
            affiliate_link = None

    affiliation_id = None
    if affiliation_id_selector:
        try:
            await page.wait_for_selector(affiliation_id_selector, timeout=10000)
        except Exception:
            pass
        try:
            id_locator = page.locator(affiliation_id_selector)
            if await id_locator.count():
                affiliation_id = await _read_input_value(id_locator.first)
        except Exception:
            affiliation_id = None

    return (commission_pct, affiliate_link, affiliation_id)


def _build_offer_from_row(row: CardRow, seen_ids: set[str]) -> Optional[ScrapedOffer]:
    href = _normalize_ml_url(_row_text(row, "href"))
    if not href or ML_DOMAIN not in href:
        return None

    result = _external_id_from_url(href)
    if not result:
        return None
    ext_id, url_type = result
    if ext_id in seen_ids:
        return None

    title = _row_text(row, "title")
    if len(title) < 5:
        return None

    image_url = _row_text(row, "image_url") or None

    price_cents = _money_parts_to_cents(
        _row_text(row, "price_fraction"),
        _row_text(row, "price_cents") or None,
    )
    if price_cents is None:
        price_cents = _price_to_cents(_row_text(row, "card_text"))
    if price_cents is None:
        return None

    old_price_cents = _money_parts_to_cents(
        _row_text(row, "old_fraction"),
        _row_text(row, "old_cents") or None,
    )
    if old_price_cents is None:
        old_price_cents = _infer_old_price_from_card_text(_row_text(row, "card_text"), price_cents)

    discount_pct = _discount_to_float(_row_text(row, "discount_text"))
    if discount_pct is None:
        discount_pct = _calc_discount(old_price_cents, price_cents)

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
        discount_pct=round(discount_pct, 2) if discount_pct is not None else None,
        commission_pct=None,
        affiliate_link=None,
        affiliation_id=None,
        source="ml_offers_playwright",
    )


async def scrape_ml_offers_playwright(
    url: str,
    card_selector: str,
    title_selector: str,
    picture_selector: str,
    price_fraction_selector: str,
    price_cents_selector: str,
    old_fraction_selector: str,
    old_cents_selector: str,
    discount_selector: str,
    commission_selector: str,
    button_selector: str,
    affiliate_share_text: str,
    affiliate_link_selector: str,
    affiliation_id_selector: str,
    number_of_pages: int = 1,
    max_scrolls: int = 4,
    scroll_delay_s: float = 1.2,
    page_delay_s: float = 0.8,
    debug: bool = False,
) -> list[ScrapedOffer]:
    offers: list[ScrapedOffer] = []
    seen_ids: set[str] = set()

    debug_dir = DEBUG_DIR
    debug_dir.mkdir(parents=True, exist_ok=True)

    selectors = ScrapeSelectors(
        card=card_selector,
        title=title_selector,
        picture=picture_selector,
        price_fraction=price_fraction_selector,
        price_cents=price_cents_selector,
        old_fraction=old_fraction_selector,
        old_cents=old_cents_selector,
        discount=discount_selector,
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context_kwargs = {
            "locale": "pt-BR",
            "user_agent": DEFAULT_USER_AGENT,
            "extra_http_headers": {"Accept-Language": DEFAULT_ACCEPT_LANGUAGE},
        }
        storage_state_path = _resolve_storage_state_path()
        if storage_state_path:
            context_kwargs["storage_state"] = storage_state_path
        context = await browser.new_context(**context_kwargs)

        await context.route("**/*", _route_block_heavy)

        page = await context.new_page()

        for page_num in range(1, max(1, number_of_pages) + 1):
            page_url = _url_with_page(url, page_num)

            resp = await page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
            print(f"[ml] page={page_num} goto.status =", resp.status if resp else None, flush=True)
            print(f"[ml] page={page_num} final.url   =", page.url, flush=True)
            print(f"[ml] page={page_num} title       =", await page.title(), flush=True)

            items = await _collect_page_items(
                page,
                selectors=selectors,
                max_scrolls=max_scrolls,
                scroll_delay_s=scroll_delay_s,
                debug=debug,
                debug_dir=debug_dir,
                page_num=page_num,
            )

            if debug:
                all_items_path = debug_dir / "items.json"
                if all_items_path.exists():
                    existing_items = json.loads(all_items_path.read_text(encoding="utf-8"))
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
            await page.wait_for_timeout(int(page_delay_s * 1000))

        for idx, offer in enumerate(offers, start=1):
            commission_pct, affiliate_link, affiliation_id = await _extract_affiliate_details(
                page,
                offer.url,
                commission_selector=commission_selector,
                button_selector=button_selector,
                affiliate_share_text=affiliate_share_text,
                affiliate_link_selector=affiliate_link_selector,
                affiliation_id_selector=affiliation_id_selector,
            )
            offer.commission_pct = commission_pct
            offer.affiliate_link = affiliate_link
            offer.affiliation_id = affiliation_id
            if page_delay_s > 0:
                await page.wait_for_timeout(int(page_delay_s * 1000))

        await context.close()
        await browser.close()

    return offers


if __name__ == "__main__":
    async def _main():
        items = await scrape_ml_offers_playwright(number_of_pages=2)
        print("items =", len(items))
        for it in items[:5]:
            print(it)

    asyncio.run(_main())
