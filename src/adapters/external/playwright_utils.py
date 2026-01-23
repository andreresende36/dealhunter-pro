"""Utilitários compartilhados para Playwright."""

from __future__ import annotations

# Standard library
import os
import pathlib
from typing import Optional

# Third-party
from playwright.async_api import Route  # type: ignore

# Local
from shared.constants import (
    RESOURCE_BLOCK_TYPES,
    TIMEOUT_SHORT,
    TRACKER_HOST_SNIPPETS,
)


def resolve_storage_state_path() -> Optional[str]:
    """
    Resolve o caminho do arquivo de storage state do Playwright.

    Procura o arquivo na seguinte ordem:
    1. Variável de ambiente PLAYWRIGHT_STORAGE_STATE
    2. Arquivo padrão storage_state.json no diretório raiz do projeto

    Returns:
        Caminho absoluto do arquivo se encontrado, None caso contrário
    """
    env_path = os.getenv("PLAYWRIGHT_STORAGE_STATE", "").strip()
    if env_path:
        candidate = pathlib.Path(env_path).expanduser()
        if candidate.exists():
            return str(candidate)
        return None

    # Vai até o diretório raiz do projeto (4 níveis acima: external -> adapters -> src -> raiz)
    parent_dir = pathlib.Path(__file__).resolve().parent.parent.parent.parent
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


async def try_accept_cookies(page) -> None:
    """
    Tenta aceitar cookies na página com timeout curto.

    Procura por botões de aceitar cookies em português, espanhol e inglês.
    Se encontrar, clica no primeiro botão encontrado.

    Args:
        page: Página do Playwright onde procurar o botão de cookies

    Note:
        Esta função falha silenciosamente se não encontrar o botão ou
        se ocorrer algum erro durante a interação.
    """

    for label in ("Aceitar cookies", "Aceptar cookies", "Accept cookies"):
        try:
            btn = page.get_by_role("button", name=label).first
            # Verifica se o botão existe usando wait_for com timeout curto
            try:
                await btn.wait_for(state="visible", timeout=TIMEOUT_SHORT)
                await btn.click(timeout=TIMEOUT_SHORT)
                return
            except TimeoutError:
                # Botão não encontrado - continua tentando
                pass
        except Exception:
            # Outros erros - loga mas não interrompe
            pass
