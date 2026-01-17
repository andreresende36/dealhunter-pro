"""Utilitários para manipulação de URLs."""

from __future__ import annotations

import re
from typing import Literal, Tuple
from urllib.parse import (
    parse_qs,
    parse_qsl,
    unquote,
    urlencode,
    urlparse,
    urlsplit,
    urlunsplit,
)

ML_DOMAIN = "mercadolivre.com.br"
ML_BASE_URL = "https://www.mercadolivre.com.br"


def external_id_from_url(url: str) -> Tuple[str, Literal["p", "up", "produto"]] | None:
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


def normalize_ml_url(href: str) -> str:
    """
    Normaliza URLs do Mercado Livre:
    - Resolve URLs relativas
    - Desencapsula links de tracking tipo click1.mercadolivre.com.br
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


def url_with_page(base_url: str, page_num: int) -> str:
    """Garante que o parâmetro page seja aplicado corretamente na URL."""
    if page_num <= 1:
        return base_url

    parts = urlsplit(base_url)
    qs = dict(parse_qsl(parts.query, keep_blank_values=True))
    qs["page"] = str(page_num)
    new_query = urlencode(qs)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment)
    )
