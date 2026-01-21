"""Utilitários para retry com backoff exponencial."""

from __future__ import annotations

import asyncio
import random
from typing import Callable, TypeVar

from utils.logging import log

T = TypeVar("T")


async def retry_with_backoff(
    func: Callable[[], T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """
    Executa uma função assíncrona com retry e backoff exponencial.

    Args:
        func: Função assíncrona a ser executada
        max_retries: Número máximo de tentativas (incluindo a primeira)
        initial_delay: Delay inicial em segundos
        max_delay: Delay máximo em segundos
        exponential_base: Base exponencial para o backoff
        jitter: Se deve adicionar jitter aleatório ao delay
        retryable_exceptions: Tupla de exceções que devem ser retentadas

    Returns:
        Resultado da função

    Raises:
        A última exceção se todas as tentativas falharem
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries):
        try:
            # Verifica se é uma coroutine ou uma função assíncrona
            if asyncio.iscoroutine(func):
                return await func
            elif asyncio.iscoroutinefunction(func):
                return await func()
            else:
                result = func()
                # Se retornou uma coroutine, await ela
                if asyncio.iscoroutine(result):
                    return await result
                return result
        except retryable_exceptions as e:
            last_exception = e
            if attempt == max_retries - 1:
                # Última tentativa falhou
                log(
                    f"[retry] Tentativa {attempt + 1}/{max_retries} falhou: {type(e).__name__}: {e}"
                )
                raise

            # Calcula delay com backoff exponencial
            delay = min(initial_delay * (exponential_base**attempt), max_delay)

            # Adiciona jitter se habilitado
            if jitter:
                jitter_amount = delay * 0.1 * random.random()
                delay = delay + jitter_amount

            log(
                f"[retry] Tentativa {attempt + 1}/{max_retries} falhou: "
                f"{type(e).__name__}: {e}. Retentando em {delay:.2f}s..."
            )
            await asyncio.sleep(delay)

    # Não deveria chegar aqui, mas por segurança
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry falhou sem exceção capturada")
