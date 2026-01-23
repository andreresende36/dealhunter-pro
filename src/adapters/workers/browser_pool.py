"""Pool de browsers reutilizáveis para otimizar performance de scraping."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from shared.constants import DEFAULT_ACCEPT_LANGUAGE, DEFAULT_USER_AGENT
from adapters.external.playwright_utils import (
    resolve_storage_state_path,
    route_block_heavy_resources,
)
from shared.utils.logging import log


class BrowserPool:
    """Pool de contextos de browser reutilizáveis."""

    def __init__(self, size: int = 3) -> None:
        """
        Inicializa o pool de browsers.

        Args:
            size: Número de contextos no pool
        """
        self.size = size
        self.playwright = None  # Mantém playwright vivo
        self.browser: Optional[Browser] = None
        self.contexts: list[BrowserContext] = []
        self._semaphore = asyncio.Semaphore(size)
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Inicializa o pool de browsers."""
        async with self._lock:
            if self._initialized:
                return

            log(f"[browser_pool] Inicializando pool com {self.size} contextos...")

            # Mantém playwright vivo (não usa context manager)
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)

            storage_state_path = resolve_storage_state_path()
            context_kwargs = {
                "locale": "pt-BR",
                "user_agent": DEFAULT_USER_AGENT,
                "extra_http_headers": {"Accept-Language": DEFAULT_ACCEPT_LANGUAGE},
                "ignore_https_errors": True,
                "bypass_csp": True,
            }

            if storage_state_path:
                context_kwargs["storage_state"] = storage_state_path

            for i in range(self.size):
                ctx = await self.browser.new_context(**context_kwargs)
                await ctx.route("**/*", route_block_heavy_resources)
                self.contexts.append(ctx)
                log(f"[browser_pool] Contexto {i+1}/{self.size} criado")

            self._initialized = True
            log("[browser_pool] Pool inicializado com sucesso")

    async def close(self) -> None:
        """Fecha todos os contextos e o browser."""
        async with self._lock:
            if not self._initialized:
                return

            log("[browser_pool] Fechando pool...")

            for ctx in self.contexts:
                try:
                    await ctx.close()
                except Exception as e:
                    log(f"[browser_pool] Erro ao fechar contexto: {e}")

            if self.browser:
                try:
                    await self.browser.close()
                except Exception as e:
                    log(f"[browser_pool] Erro ao fechar browser: {e}")

            if self.playwright:
                try:
                    await self.playwright.stop()
                except Exception as e:
                    log(f"[browser_pool] Erro ao fechar playwright: {e}")

            self.contexts = []
            self.browser = None
            self.playwright = None
            self._initialized = False

            log("[browser_pool] Pool fechado")

    @asynccontextmanager
    async def get_page(self):
        """
        Obtém uma página do pool de forma thread-safe.

        Yields:
            Page: Página do Playwright pronta para uso
        """
        if not self._initialized:
            await self.initialize()

        async with self._semaphore:
            # Seleciona contexto de forma round-robin
            ctx_index = id(asyncio.current_task()) % self.size
            ctx = self.contexts[ctx_index]

            page = await ctx.new_page()
            try:
                yield page
            finally:
                try:
                    await page.close()
                except Exception as e:
                    log(f"[browser_pool] Erro ao fechar página: {e}")


# Pool global singleton
_global_pool: Optional[BrowserPool] = None
_global_pool_lock = asyncio.Lock()


async def get_browser_pool(size: int = 3) -> BrowserPool:
    """
    Obtém ou cria o pool global de browsers.

    Args:
        size: Tamanho do pool (usado apenas na criação)

    Returns:
        BrowserPool global
    """
    global _global_pool

    async with _global_pool_lock:
        if _global_pool is None:
            _global_pool = BrowserPool(size=size)
            await _global_pool.initialize()

        return _global_pool


async def close_browser_pool() -> None:
    """Fecha o pool global de browsers."""
    global _global_pool

    async with _global_pool_lock:
        if _global_pool is not None:
            await _global_pool.close()
            _global_pool = None
