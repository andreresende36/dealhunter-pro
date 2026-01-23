"""Configuração por ambiente (development, staging, production)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from shared.utils.env import env_string


@dataclass(frozen=True)
class EnvironmentConfig:
    """Configuração específica de cada ambiente."""

    name: str
    debug: bool
    log_level: str
    redis_url: str
    enrichment_worker_concurrency: int
    browser_pool_size: int
    rate_limit_max_requests: int
    rate_limit_window_seconds: int
    circuit_breaker_failure_threshold: int
    circuit_breaker_timeout_seconds: int
    metrics_enabled: bool
    metrics_port: int
    sentry_dsn: Optional[str] = None


# ============================================================================
# AMBIENTES PREDEFINIDOS
# ============================================================================

DEVELOPMENT = EnvironmentConfig(
    name="development",
    debug=True,
    log_level="DEBUG",
    redis_url="redis://localhost:6379/0",
    enrichment_worker_concurrency=1,
    browser_pool_size=2,
    rate_limit_max_requests=5,  # Mais conservador em dev
    rate_limit_window_seconds=60,
    circuit_breaker_failure_threshold=3,
    circuit_breaker_timeout_seconds=30,
    metrics_enabled=False,  # Desabilitado em dev
    metrics_port=8000,
    sentry_dsn=None,
)

STAGING = EnvironmentConfig(
    name="staging",
    debug=False,
    log_level="INFO",
    redis_url=env_string("REDIS_URL", "redis://localhost:6379/0"),
    enrichment_worker_concurrency=3,
    browser_pool_size=3,
    rate_limit_max_requests=10,
    rate_limit_window_seconds=60,
    circuit_breaker_failure_threshold=5,
    circuit_breaker_timeout_seconds=60,
    metrics_enabled=True,
    metrics_port=8000,
    sentry_dsn=env_string("SENTRY_DSN", None),
)

PRODUCTION = EnvironmentConfig(
    name="production",
    debug=False,
    log_level="WARNING",
    redis_url=env_string("REDIS_URL", ""),
    enrichment_worker_concurrency=10,
    browser_pool_size=5,
    rate_limit_max_requests=15,
    rate_limit_window_seconds=60,
    circuit_breaker_failure_threshold=10,
    circuit_breaker_timeout_seconds=120,
    metrics_enabled=True,
    metrics_port=8000,
    sentry_dsn=env_string("SENTRY_DSN", None),
)


def get_environment() -> str:
    """
    Retorna o nome do ambiente atual.

    Lê da variável de ambiente ENVIRONMENT.
    Padrão: development

    Returns:
        Nome do ambiente (development, staging, production)
    """
    return os.getenv("ENVIRONMENT", "development").lower()


def get_environment_config() -> EnvironmentConfig:
    """
    Retorna a configuração do ambiente atual.

    Returns:
        EnvironmentConfig para o ambiente atual
    """
    env = get_environment()

    configs = {
        "development": DEVELOPMENT,
        "dev": DEVELOPMENT,
        "staging": STAGING,
        "stage": STAGING,
        "stg": STAGING,
        "production": PRODUCTION,
        "prod": PRODUCTION,
        "prd": PRODUCTION,
    }

    config = configs.get(env)

    if config is None:
        # Fallback para development se ambiente desconhecido
        from utils.logging import log

        log(f"[config] Ambiente desconhecido: {env}. Usando development.")
        return DEVELOPMENT

    return config


def is_development() -> bool:
    """Verifica se está em ambiente de desenvolvimento."""
    return get_environment() in ["development", "dev"]


def is_staging() -> bool:
    """Verifica se está em ambiente de staging."""
    return get_environment() in ["staging", "stage", "stg"]


def is_production() -> bool:
    """Verifica se está em ambiente de produção."""
    return get_environment() in ["production", "prod", "prd"]
