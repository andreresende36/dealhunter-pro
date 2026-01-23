"""Testes para utilitários."""

from __future__ import annotations

import pytest

import sys
from pathlib import Path

# Adiciona o diretório src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from shared.utils.price import calc_discount, money_parts_to_cents, parse_commission_pct
from shared.utils.url import external_id_from_url, normalize_ml_url


class TestPriceUtils:
    """Testes para utilitários de preço."""

    def test_money_parts_to_cents_with_cents(self):
        """Testa conversão com fração e centavos."""
        result = money_parts_to_cents("1.234", "56")
        assert result == 123456

    def test_money_parts_to_cents_without_cents(self):
        """Testa conversão apenas com fração."""
        result = money_parts_to_cents("100", None)
        assert result == 10000

    def test_calc_discount(self):
        """Testa cálculo de desconto."""
        result = calc_discount(10000, 5000)  # De 100 por 50 = 50% de desconto
        assert result == 50

    def test_calc_discount_no_discount(self):
        """Testa quando não há desconto."""
        result = calc_discount(5000, 5000)
        assert result == 0

    def test_parse_commission_pct_with_percent(self):
        """Testa parsing de comissão com %."""
        assert parse_commission_pct("16%") == 16
        assert parse_commission_pct("5.5%") == 5

    def test_parse_commission_pct_without_percent(self):
        """Testa parsing de comissão sem %."""
        assert parse_commission_pct("GANHOS 16") == 16


class TestUrlUtils:
    """Testes para utilitários de URL."""

    def test_external_id_from_url_mlb(self):
        """Testa extração de ID externo de URL MLB."""
        result = external_id_from_url(
            "https://produto.mercadolivre.com.br/MLB-123456789-produto"
        )
        assert result == ("MLB-123456789", "produto")

    def test_external_id_from_url_short(self):
        """Testa extração de ID de URL curta."""
        result = external_id_from_url("https://www.mercadolivre.com.br/p/MLB-123")
        assert result == ("MLB-123", "p")

    def test_normalize_ml_url(self):
        """Testa normalização de URL do ML."""
        url = "https://produto.mercadolivre.com.br/MLB-123?param=value"
        normalized = normalize_ml_url(url)
        assert "?param=value" not in normalized
        assert "MLB-123" in normalized


class TestRateLimiter:
    """Testes para rate limiter."""

    @pytest.mark.asyncio
    async def test_rate_limiter_basic(self):
        """Testa funcionamento básico do rate limiter."""
        from datetime import timedelta
        from shared.utils.rate_limiter import RateLimiter

        limiter = RateLimiter(max_requests=2, time_window=timedelta(seconds=1))

        # Primeira requisição deve passar
        await limiter.acquire()
        assert len(limiter.requests) == 1

        # Segunda requisição deve passar
        await limiter.acquire()
        assert len(limiter.requests) == 2


class TestCircuitBreaker:
    """Testes para circuit breaker."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        """Testa que o circuit breaker abre após falhas consecutivas."""
        from shared.utils.rate_limiter import CircuitBreaker, CircuitBreakerConfig, CircuitState
        from datetime import timedelta

        config = CircuitBreakerConfig(
            failure_threshold=3,
            timeout=timedelta(seconds=1),
        )
        breaker = CircuitBreaker(config=config)

        # Simula 3 falhas
        for _ in range(3):
            try:
                await breaker.call(lambda: 1 / 0)  # Sempre falha
            except ZeroDivisionError:
                pass

        # Circuit deve estar aberto
        assert breaker.state == CircuitState.OPEN
