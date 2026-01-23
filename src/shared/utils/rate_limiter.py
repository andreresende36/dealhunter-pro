"""Rate limiter e circuit breaker para proteção contra sobrecarga."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from shared.utils.logging import log


class RateLimiter:
    """
    Rate limiter assíncrono baseado em janela deslizante.

    Controla o número máximo de requisições em uma janela de tempo.
    """

    def __init__(
        self,
        max_requests: int,
        time_window: timedelta,
        name: str = "rate_limiter",
    ) -> None:
        """
        Inicializa o rate limiter.

        Args:
            max_requests: Número máximo de requisições permitidas
            time_window: Janela de tempo para contagem
            name: Nome do limiter (para logs)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.name = name
        self.requests: list[datetime] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Aguarda até que uma requisição possa ser feita sem violar o limite.

        Bloqueia se necessário até que haja capacidade disponível.
        """
        async with self._lock:
            now = datetime.now()

            # Remove requisições antigas fora da janela
            cutoff = now - self.time_window
            self.requests = [r for r in self.requests if r > cutoff]

            # Se estamos no limite, aguarda
            if len(self.requests) >= self.max_requests:
                oldest = self.requests[0]
                wait_until = oldest + self.time_window
                wait_time = (wait_until - now).total_seconds()

                if wait_time > 0:
                    log(
                        f"[{self.name}] Rate limit atingido. "
                        f"Aguardando {wait_time:.2f}s..."
                    )
                    await asyncio.sleep(wait_time)

                    # Recalcula após o sleep
                    now = datetime.now()
                    cutoff = now - self.time_window
                    self.requests = [r for r in self.requests if r > cutoff]

            # Registra a requisição
            self.requests.append(now)

    def reset(self) -> None:
        """Reseta o contador de requisições."""
        self.requests = []


class CircuitState(Enum):
    """Estados possíveis do circuit breaker."""

    CLOSED = "closed"  # Funcionando normalmente
    OPEN = "open"  # Circuito aberto, rejeitando requisições
    HALF_OPEN = "half_open"  # Testando se o serviço recuperou


@dataclass
class CircuitBreakerConfig:
    """Configuração do circuit breaker."""

    failure_threshold: int = 5  # Número de falhas para abrir o circuito
    success_threshold: int = 2  # Número de sucessos para fechar o circuito
    timeout: timedelta = field(
        default_factory=lambda: timedelta(seconds=60)
    )  # Tempo que o circuito fica aberto
    half_open_max_calls: int = 1  # Máximo de chamadas no estado half-open


class CircuitBreakerError(Exception):
    """Exceção lançada quando o circuit breaker está aberto."""

    pass


class CircuitBreaker:
    """
    Circuit breaker para proteção contra falhas em cascata.

    Abre o circuito após um número de falhas consecutivas,
    rejeitando requisições por um período de tempo.
    """

    def __init__(
        self,
        config: Optional[CircuitBreakerConfig] = None,
        name: str = "circuit_breaker",
    ) -> None:
        """
        Inicializa o circuit breaker.

        Args:
            config: Configuração do circuit breaker
            name: Nome do breaker (para logs)
        """
        self.config = config or CircuitBreakerConfig()
        self.name = name
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0
        self._lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs):
        """
        Executa uma função protegida pelo circuit breaker.

        Args:
            func: Função a executar (pode ser sync ou async)
            *args: Argumentos posicionais
            **kwargs: Argumentos nomeados

        Returns:
            Resultado da função

        Raises:
            CircuitBreakerError: Se o circuito estiver aberto
        """
        await self._check_state()

        try:
            # Executa a função (suporta async e sync)
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            await self._on_success()
            return result

        except Exception as e:
            await self._on_failure()
            raise e

    async def _check_state(self) -> None:
        """Verifica e atualiza o estado do circuit breaker."""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                # Verifica se é hora de tentar novamente
                if self.last_failure_time is not None:
                    time_since_failure = time.time() - self.last_failure_time
                    if time_since_failure >= self.config.timeout.total_seconds():
                        log(
                            f"[{self.name}] Timeout expirado. "
                            f"Mudando para HALF_OPEN..."
                        )
                        self.state = CircuitState.HALF_OPEN
                        self.half_open_calls = 0
                    else:
                        remaining = (
                            self.config.timeout.total_seconds() - time_since_failure
                        )
                        raise CircuitBreakerError(
                            f"Circuit breaker aberto. "
                            f"Tentando novamente em {remaining:.1f}s"
                        )

            elif self.state == CircuitState.HALF_OPEN:
                # Limita chamadas no estado half-open
                if self.half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitBreakerError(
                        "Circuit breaker em HALF_OPEN. "
                        "Aguardando resultado de testes..."
                    )
                self.half_open_calls += 1

    async def _on_success(self) -> None:
        """Registra um sucesso."""
        async with self._lock:
            self.failure_count = 0

            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    log(
                        f"[{self.name}] Sucessos suficientes. "
                        f"Fechando circuito..."
                    )
                    self.state = CircuitState.CLOSED
                    self.success_count = 0

    async def _on_failure(self) -> None:
        """Registra uma falha."""
        async with self._lock:
            self.failure_count += 1
            self.success_count = 0
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                log(
                    f"[{self.name}] Falha em HALF_OPEN. "
                    f"Reabrindo circuito..."
                )
                self.state = CircuitState.OPEN

            elif self.failure_count >= self.config.failure_threshold:
                log(
                    f"[{self.name}] Limite de falhas atingido "
                    f"({self.failure_count}). Abrindo circuito..."
                )
                self.state = CircuitState.OPEN

    def get_state(self) -> CircuitState:
        """Retorna o estado atual do circuit breaker."""
        return self.state

    def reset(self) -> None:
        """Reseta o circuit breaker para o estado inicial."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0


# Instances globais para uso compartilhado
_ml_rate_limiter: Optional[RateLimiter] = None
_ml_circuit_breaker: Optional[CircuitBreaker] = None


def get_ml_rate_limiter() -> RateLimiter:
    """
    Obtém o rate limiter global para requisições ao Mercado Livre.

    Returns:
        RateLimiter configurado para ML (10 req/min)
    """
    global _ml_rate_limiter
    if _ml_rate_limiter is None:
        _ml_rate_limiter = RateLimiter(
            max_requests=10,
            time_window=timedelta(minutes=1),
            name="ml_rate_limiter",
        )
    return _ml_rate_limiter


def get_ml_circuit_breaker() -> CircuitBreaker:
    """
    Obtém o circuit breaker global para requisições ao Mercado Livre.

    Returns:
        CircuitBreaker configurado para ML
    """
    global _ml_circuit_breaker
    if _ml_circuit_breaker is None:
        _ml_circuit_breaker = CircuitBreaker(
            config=CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=2,
                timeout=timedelta(seconds=60),
            ),
            name="ml_circuit_breaker",
        )
    return _ml_circuit_breaker
