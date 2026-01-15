from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal, Tuple
import re
import asyncio
import pathlib
from urllib.parse import urlparse, parse_qs, unquote, urlsplit, urlunsplit, parse_qsl, urlencode

from playwright.async_api import async_playwright

_PRICE_RE = re.compile(r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})|\d+(?:,\d{2})?)")


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
    source: str = "ml_offers_playwright"

def _price_to_cents(text: str) -> Optional[int]:
    if not text:
        return None
    m = _PRICE_RE.search(text)
    if not m:
        return None
    raw = m.group(1).replace(".", "").replace(",", ".")
    try:
        return int(round(float(raw) * 100))
    except ValueError:
        return None
    
def _all_prices_to_cents(text: str) -> list[int]:
    """
    Extrai todos os valores monetários encontrados no texto e converte para centavos.
    Útil para fallback de preço antigo (que costuma ser o maior valor do card).
    """
    if not text:
        return []

    cents_list: list[int] = []
    for m in _PRICE_RE.finditer(text):
        raw = m.group(1).replace(".", "").replace(",", ".")
        try:
            cents_list.append(int(round(float(raw) * 100)))
        except ValueError:
            continue

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


def _calc_discount(old_cents: Optional[int], price_cents: int) -> Optional[float]:
    if not old_cents or old_cents <= 0:
        return None
    if price_cents >= old_cents:
        return 0.0
    return ((old_cents - price_cents) / old_cents) * 100.0


def _external_id_from_url(url: str) -> Optional[Tuple[str, Literal["p", "up"]]]:
    """
    Extrai o código MLB/MLBU da URL do Mercado Livre.
    Retorna tupla (external_id, url_type) ou None.

    Tipo 1 (/p/): MLB16069584, "p"
    Tipo 2 (/up/): MLBU3491177949, "up"
    """
    # Tenta tipo 1: /p/MLB...
    match_p = re.search(r"/p/(MLB\d+)", url, re.IGNORECASE)
    if match_p:
        return (match_p.group(1), "p")

    # Tenta tipo 2: /up/MLBU...
    match_up = re.search(r"/up/(MLBU\d+)", url, re.IGNORECASE)
    if match_up:
        return (match_up.group(1), "up")

    return None


def _normalize_ml_url(href: str) -> str:
    """
    - Resolve URLs relativas
    - Tenta "desencapsular" links de tracking tipo click1.mercadolivre.com.br ... &url=https%3A%2F%2Fwww.mercadolivre.com.br%2F...
    """
    if not href:
        return ""

    if href.startswith("/"):
        href = "https://www.mercadolivre.com.br" + href

    try:
        u = urlparse(href)
    except Exception:
        return href

    host = (u.netloc or "").lower()

    # Desencapsula links de tracking comuns (mercadoclics/click1)
    if "mercadolivre.com.br" in host and ("click" in host or "mercadoclics" in host):
        qs = parse_qs(u.query)
        if "url" in qs and qs["url"]:
            try:
                return unquote(qs["url"][0])
            except Exception:
                return qs["url"][0]

    return href


def _money_parts_to_cents(fraction_text: str, cents_text: str | None) -> Optional[int]:
    if not fraction_text:
        return None
    frac = (fraction_text or "").strip().replace(".", "")
    if not frac.isdigit():
        frac_digits = re.sub(r"\D+", "", frac)
        if not frac_digits:
            return None
        frac = frac_digits

    cents = (cents_text or "").strip()
    cents = re.sub(r"\D+", "", cents) if cents else ""
    if cents == "":
        cents = "00"
    if len(cents) == 1:
        cents = cents + "0"
    if len(cents) > 2:
        cents = cents[:2]

    try:
        return int(frac) * 100 + int(cents)
    except ValueError:
        return None


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
    number_of_pages: int = 1,
    max_scrolls: int = 4,
    scroll_delay_s: float = 1.2,
    page_delay_s: float = 0.8,
    debug: bool = False,
) -> list[ScrapedOffer]:
    offers: list[ScrapedOffer] = []
    seen_ids: set[str] = set()

    out = pathlib.Path("debug")
    out.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="pt-BR",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            extra_http_headers={"Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"},
        )

        # Teste
        async def _route_block_heavy(route, request):
            rt = request.resource_type
            url = request.url.lower()

            if rt in {"image", "font", "media"}:
                return await route.abort()

            # trackers comuns (opcional, mas ajuda)
            if any(x in url for x in ["doubleclick", "googletagmanager", "google-analytics", "facebook", "hotjar"]):
                return await route.abort()

            return await route.continue_()

        await context.route("**/*", _route_block_heavy)
        # Teste

        page = await context.new_page()

        for page_num in range(1, max(1, number_of_pages) + 1):
            page_url = _url_with_page(url, page_num)

            resp = await page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
            print(f"[ml] page={page_num} goto.status =", resp.status if resp else None, flush=True)
            print(f"[ml] page={page_num} final.url   =", page.url, flush=True)
            print(f"[ml] page={page_num} title       =", await page.title(), flush=True)

            # =========================
            # ALTERAÇÃO (ITEM 3)
            # - remove sleep fixo
            # - espera os cards aparecerem
            # =========================
            await _try_accept_cookies(page)
            await page.wait_for_selector(card_selector, timeout=20000)

            # =========================
            # ALTERAÇÃO (ITEM 4)
            # - scroll adaptativo (para cedo se não aumentar a qtd de cards)
            # =========================
            prev = 0
            for _ in range(max_scrolls):
                await page.mouse.wheel(0, 2400)
                await page.wait_for_timeout(int(scroll_delay_s * 1000))

                cur = await page.locator(card_selector).count()
                if cur <= prev:
                    break
                prev = cur

            if debug:
                (out / f"ml_ofertas_rendered_p{page_num}.html").write_text(await page.content(), encoding="utf-8")
                await page.screenshot(path=str(out / f"ml_ofertas_p{page_num}.png"), full_page=True)

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
                    return cards.slice(0, 300).map(card => {{
                        const href = pickAttr(card, 'a[href]', 'href');
                        const title = pick(card, '{title_selector}');
                        const image_url =
                        pickAttr(card, '{picture_selector}', 'src') ||
                        pickAttr(card, '{picture_selector}', 'data-src');
                        const price_fraction = pick(card,'{price_fraction_selector}');
                        const price_cents = pick(card,'{price_cents_selector}');
                        const old_fraction = pick(card,'{old_fraction_selector}');
                        const old_cents = pick(card,'{old_cents_selector}');
                        const discount_text = pick(card, '{discount_selector}');
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

            print(f"[ml] page={page_num} cards =", len(items), flush=True)

            for row in items:
                href = _normalize_ml_url((row.get("href") or "").strip())
                if not href or "mercadolivre.com.br" not in href:
                    continue

                result = _external_id_from_url(href)
                if not result or result[0] in seen_ids:
                    continue
                ext_id, url_type = result

                title = (row.get("title") or "").strip()
                if len(title) < 5:
                    continue

                image_url = (row.get("image_url") or "").strip() or None

                # preço atual (sem round-trip extra)
                price_cents = _money_parts_to_cents(
                    (row.get("price_fraction") or "").strip(),
                    (row.get("price_cents") or "").strip() or None,
                )

                # FALLBACK: regex no texto completo do card (sem round-trip)
                if price_cents is None:
                    card_text = (row.get("card_text") or "").strip()
                    price_cents = _price_to_cents(card_text)

                if price_cents is None:
                    continue

                old_price_cents = _money_parts_to_cents(
                    (row.get("old_fraction") or "").strip(),
                    (row.get("old_cents") or "").strip() or None,
                )

                # FALLBACK do preço antigo: pega o maior preço do texto do card
                # (ou o maior acima do preço atual, quando possível)
                if old_price_cents is None:
                    card_text = (row.get("card_text") or "").strip()
                    all_prices = _all_prices_to_cents(card_text)

                    if all_prices:
                        # preferível: maior valor acima do preço atual
                        bigger_than_current = [p for p in all_prices if p > price_cents]
                        if bigger_than_current:
                            old_price_cents = max(bigger_than_current)
                        else:
                            # fallback final: maior valor encontrado (às vezes só existe o atual)
                            old_price_cents = max(all_prices)

                discount_pct = _discount_to_float((row.get("discount_text") or "").strip())
                if discount_pct is None:
                    discount_pct = _calc_discount(old_price_cents, price_cents)

                offers.append(
                    ScrapedOffer(
                        marketplace="Mercado Livre",
                        external_id=ext_id,
                        title=title,
                        url=f"https://www.mercadolivre.com.br/{url_type}/{ext_id}",
                        image_url=image_url,
                        price_cents=price_cents,
                        old_price_cents=old_price_cents,
                        discount_pct=round(discount_pct, 2) if discount_pct is not None else None,
                        source="ml_offers_playwright",
                    )
                )
                seen_ids.add(ext_id)

            # respiro entre páginas (evita estresse/anti-bot)
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
