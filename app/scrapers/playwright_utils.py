"""Utilitários compartilhados para Playwright."""

from __future__ import annotations

import os
import pathlib
from typing import Optional

from playwright.async_api import Route  # type: ignore

from scrapers.constants import (
    RESOURCE_BLOCK_TYPES,
    TRACKER_HOST_SNIPPETS,
)


def resolve_storage_state_path() -> Optional[str]:
    """Resolve o caminho do arquivo de storage state do Playwright."""
    env_path = os.getenv("PLAYWRIGHT_STORAGE_STATE", "").strip()
    if env_path:
        candidate = pathlib.Path(env_path).expanduser()
        if candidate.exists():
            return str(candidate)
        return None

    parent_dir = pathlib.Path(__file__).resolve().parent.parent
    default_path = parent_dir / "storage_state.json"
    if default_path.exists():
        return str(default_path)
    return None


async def route_block_heavy_resources(route: Route, request) -> None:
    """
    Bloqueia recursos pesados e trackers para acelerar carregamento.

    Args:
        route: Rota do Playwright
        request: Requisição HTTP
    """
    rt = request.resource_type
    url = request.url.lower()

    # Bloqueia imagens, fontes e mídia
    if rt in RESOURCE_BLOCK_TYPES:
        await route.abort()
        return

    # Bloqueia trackers e analytics
    if any(token in url for token in TRACKER_HOST_SNIPPETS):
        await route.abort()
        return

    # Bloqueia CSS também (não necessário para scraping)
    if rt == "stylesheet":
        await route.abort()
        return

    await route.continue_()
