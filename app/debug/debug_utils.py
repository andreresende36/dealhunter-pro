"""Utilitários de debug para scrapers."""

from __future__ import annotations

import json
import pathlib
from collections.abc import Sequence
from typing import Any

from playwright.async_api import Page  # type: ignore

from utils.logging import log
from utils.price import parse_commission_pct
from utils.url import ML_DOMAIN, external_id_from_url, normalize_ml_url


def _row_text(row: dict, key: str) -> str:
    """Extrai texto de uma chave do row."""
    value = row.get(key) or ""
    return value.strip() if isinstance(value, str) else str(value)


def ensure_debug_dir(debug_dir: pathlib.Path) -> None:
    """Garante que o diretório de debug existe."""
    debug_dir.mkdir(parents=True, exist_ok=True)


async def create_debug_browser(playwright, slow_mo: int = 100):
    """
    Cria um navegador em modo debug (visível com slow_mo).

    Args:
        playwright: Instância do async_playwright
        slow_mo: Delay em milissegundos entre ações (padrão: 100ms)

    Returns:
        Browser configurado para debug
    """
    log("[affiliate_hub] Modo debug ativo: navegador visível com slow_mo=100ms")
    return await playwright.chromium.launch(headless=False, slow_mo=slow_mo)


async def save_affiliate_hub_debug_data(
    items: Sequence[dict[str, Any]],
    page: Page,
    debug_dir: pathlib.Path,
) -> None:
    """
    Salva dados de debug da Central de Afiliados (HTML e JSON).

    Args:
        items: Lista de AffiliateCardRow coletados
        page: Página do Playwright
        debug_dir: Diretório onde salvar os arquivos de debug
    """
    # Salva HTML da página
    html_content = await page.content()
    html_path = debug_dir / "affiliate_hub_after_scroll.html"
    html_path.write_text(html_content, encoding="utf-8")
    log(f"[affiliate_hub] HTML após scroll salvo em {html_path}")

    # Salva enumeração dos AffiliateCardRow
    debug_affiliate_rows_path = debug_dir / "affiliate_rows.json"
    enumerated_rows = []

    for idx, row in enumerate(items):
        debug_row = dict(row)
        # Remove chaves que não devem aparecer no JSON de debug
        debug_row.pop("commission_text", None)
        debug_row.pop("card_text", None)

        # Calcula commission_pct processado
        commission_pct = parse_commission_pct(_row_text(row, "commission_text"))
        if commission_pct is None:
            commission_pct = parse_commission_pct(_row_text(row, "card_text"))
        debug_row["commission_pct"] = commission_pct

        # Extrai external_id
        href = normalize_ml_url(_row_text(row, "href"))
        external_id = None
        if href and ML_DOMAIN in href:
            result = external_id_from_url(href)
            if result:
                external_id, url_type = result
                debug_row["external_id"] = external_id
                debug_row["url_type"] = url_type

        enumerated_rows.append({"idx": idx, "row": debug_row})

    debug_affiliate_rows_path.write_text(
        json.dumps(enumerated_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log(
        f"[affiliate_hub] Enumeração dos AffiliateCardRow salva em {debug_affiliate_rows_path}"
    )
