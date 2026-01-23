"""Sistema de métricas Prometheus para monitoramento da aplicação."""

from __future__ import annotations

from functools import wraps
from typing import Callable

from prometheus_client import Counter, Gauge, Histogram, start_http_server
from shared.utils.logging import log

# ============================================================================
# MÉTRICAS DE SCRAPING
# ============================================================================

# Duração do scraping
scrape_duration_seconds = Histogram(
    'dealhunter_scrape_duration_seconds',
    'Duração total do scraping em segundos',
    buckets=[10, 30, 60, 120, 300, 600, 1800],  # 10s até 30min
)

# Ofertas coletadas
offers_collected_total = Counter(
    'dealhunter_offers_collected_total',
    'Número total de ofertas coletadas',
    ['source'],  # ml_affiliate_hub, etc
)

# Ofertas filtradas
offers_filtered_total = Counter(
    'dealhunter_offers_filtered_total',
    'Número total de ofertas após filtros',
)

# Scrolls realizados
scrolls_performed_total = Counter(
    'dealhunter_scrolls_performed_total',
    'Número total de scrolls realizados',
)

# Erros de scraping
scraping_errors_total = Counter(
    'dealhunter_scraping_errors_total',
    'Número total de erros durante scraping',
    ['error_type'],  # timeout, network, parse, etc
)

# ============================================================================
# MÉTRICAS DE ENRIQUECIMENTO
# ============================================================================

# Duração do enriquecimento
enrichment_duration_seconds = Histogram(
    'dealhunter_enrichment_duration_seconds',
    'Duração do enriquecimento de uma oferta em segundos',
    buckets=[1, 2, 5, 10, 30, 60, 120],  # 1s até 2min
)

# Enriquecimentos bem-sucedidos
enrichment_success_total = Counter(
    'dealhunter_enrichment_success_total',
    'Número total de enriquecimentos bem-sucedidos',
)

# Erros de enriquecimento
enrichment_errors_total = Counter(
    'dealhunter_enrichment_errors_total',
    'Número total de erros durante enriquecimento',
    ['error_type'],  # timeout, network, parse, circuit_breaker, etc
)

# Jobs enfileirados
jobs_enqueued_total = Counter(
    'dealhunter_jobs_enqueued_total',
    'Número total de jobs enfileirados para enriquecimento',
)

# Jobs processados
jobs_processed_total = Counter(
    'dealhunter_jobs_processed_total',
    'Número total de jobs processados',
    ['status'],  # success, failed, retried
)

# ============================================================================
# MÉTRICAS DE WORKERS
# ============================================================================

# Workers ativos
active_workers = Gauge(
    'dealhunter_active_workers',
    'Número de workers ativos processando jobs',
)

# Fila de jobs
queue_size = Gauge(
    'dealhunter_queue_size',
    'Tamanho da fila de jobs pendentes',
    ['queue_name'],
)

# ============================================================================
# MÉTRICAS DE BANCO DE DADOS
# ============================================================================

# Queries executadas
database_queries_total = Counter(
    'dealhunter_database_queries_total',
    'Número total de queries executadas',
    ['operation'],  # select, insert, update, delete
)

# Duração de queries
database_query_duration_seconds = Histogram(
    'dealhunter_database_query_duration_seconds',
    'Duração de queries em segundos',
    ['operation'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5],  # 10ms até 5s
)

# Erros de banco
database_errors_total = Counter(
    'dealhunter_database_errors_total',
    'Número total de erros de banco de dados',
    ['error_type'],
)

# ============================================================================
# MÉTRICAS DE RATE LIMITING
# ============================================================================

# Rate limit atingido
rate_limit_hit_total = Counter(
    'dealhunter_rate_limit_hit_total',
    'Número de vezes que o rate limit foi atingido',
    ['limiter_name'],
)

# Tempo aguardando rate limit
rate_limit_wait_seconds = Histogram(
    'dealhunter_rate_limit_wait_seconds',
    'Tempo aguardando rate limit em segundos',
    ['limiter_name'],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60],
)

# ============================================================================
# MÉTRICAS DE CIRCUIT BREAKER
# ============================================================================

# Estado do circuit breaker
circuit_breaker_state = Gauge(
    'dealhunter_circuit_breaker_state',
    'Estado do circuit breaker (0=closed, 1=open, 2=half_open)',
    ['breaker_name'],
)

# Falhas do circuit breaker
circuit_breaker_failures_total = Counter(
    'dealhunter_circuit_breaker_failures_total',
    'Número total de falhas registradas pelo circuit breaker',
    ['breaker_name'],
)

# Rejeições do circuit breaker
circuit_breaker_rejections_total = Counter(
    'dealhunter_circuit_breaker_rejections_total',
    'Número total de requisições rejeitadas pelo circuit breaker',
    ['breaker_name'],
)

# ============================================================================
# MÉTRICAS DE BROWSER POOL
# ============================================================================

# Browsers disponíveis no pool
browser_pool_available = Gauge(
    'dealhunter_browser_pool_available',
    'Número de browsers disponíveis no pool',
)

# Browsers em uso
browser_pool_in_use = Gauge(
    'dealhunter_browser_pool_in_use',
    'Número de browsers em uso no pool',
)

# Tempo aguardando browser do pool
browser_pool_wait_seconds = Histogram(
    'dealhunter_browser_pool_wait_seconds',
    'Tempo aguardando browser do pool em segundos',
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10],
)

# ============================================================================
# HELPERS E DECORATORS
# ============================================================================


def track_scrape_duration(func: Callable) -> Callable:
    """Decorator para rastrear duração de scraping."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        with scrape_duration_seconds.time():
            return await func(*args, **kwargs)

    return wrapper


def track_enrichment_duration(func: Callable) -> Callable:
    """Decorator para rastrear duração de enriquecimento."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        with enrichment_duration_seconds.time():
            return await func(*args, **kwargs)

    return wrapper


def start_metrics_server(port: int = 8000) -> None:
    """
    Inicia servidor HTTP para expor métricas Prometheus.

    Args:
        port: Porta para o servidor de métricas
    """
    try:
        start_http_server(port)
        log(f"[metrics] Servidor de métricas iniciado na porta {port}")
    except Exception as e:
        log(f"[metrics] Erro ao iniciar servidor de métricas: {e}")


# ============================================================================
# MÉTRICAS CUSTOMIZADAS PARA RATE LIMITER
# ============================================================================


def track_rate_limit_wait(limiter_name: str, wait_time: float) -> None:
    """
    Registra tempo aguardando rate limit.

    Args:
        limiter_name: Nome do rate limiter
        wait_time: Tempo aguardado em segundos
    """
    rate_limit_hit_total.labels(limiter_name=limiter_name).inc()
    rate_limit_wait_seconds.labels(limiter_name=limiter_name).observe(wait_time)


def update_circuit_breaker_state(breaker_name: str, state: int) -> None:
    """
    Atualiza estado do circuit breaker.

    Args:
        breaker_name: Nome do circuit breaker
        state: Estado (0=closed, 1=open, 2=half_open)
    """
    circuit_breaker_state.labels(breaker_name=breaker_name).set(state)


def track_circuit_breaker_failure(breaker_name: str) -> None:
    """
    Registra falha no circuit breaker.

    Args:
        breaker_name: Nome do circuit breaker
    """
    circuit_breaker_failures_total.labels(breaker_name=breaker_name).inc()


def track_circuit_breaker_rejection(breaker_name: str) -> None:
    """
    Registra rejeição pelo circuit breaker.

    Args:
        breaker_name: Nome do circuit breaker
    """
    circuit_breaker_rejections_total.labels(breaker_name=breaker_name).inc()
