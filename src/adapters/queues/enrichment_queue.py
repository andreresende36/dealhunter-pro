"""Módulo de fila para enriquecimento assíncrono de ofertas."""

from __future__ import annotations

from typing import Optional

import redis
from rq import Queue

from shared.config.settings import EnrichmentConfig
from shared.utils.logging import log


def get_redis_connection(config: EnrichmentConfig) -> redis.Redis:
    """
    Cria conexão com Redis a partir da configuração.

    Args:
        config: Configuração de enriquecimento

    Returns:
        Cliente Redis
    """
    try:
        # Parse da URL do Redis
        # Formato: redis://localhost:6379/0 ou redis://:password@host:port/db
        conn = redis.from_url(config.redis_url, decode_responses=False)

        # Testa a conexão
        conn.ping()

        return conn
    except redis.ConnectionError as e:
        log(f"[queue] ❌ Erro de conexão com Redis: {e}")
        log(f"[queue] Verifique se o Redis está rodando em {config.redis_url}")
        raise
    except Exception as e:
        log(f"[queue] ❌ Erro ao conectar ao Redis: {e}")
        raise


def get_queue(
    config: Optional[EnrichmentConfig] = None,
    redis_conn: Optional[redis.Redis] = None,
) -> Queue:
    """
    Obtém ou cria uma fila RQ.

    Args:
        config: Configuração de enriquecimento (opcional se redis_conn for fornecido)
        redis_conn: Conexão Redis (opcional, será criada se não fornecida)

    Returns:
        Fila RQ configurada
    """
    if redis_conn is None:
        if config is None:
            from config import get_config

            config = get_config().enrichment
        redis_conn = get_redis_connection(config)

    if redis_conn is None:
        raise ValueError("Não foi possível criar conexão Redis")

    queue_name = config.queue_name if config else "enrichment"
    return Queue(queue_name, connection=redis_conn)


def enqueue_enrichment_job(
    offer_id: str,
    url: str,
    current_price_cents: int,
    config: Optional[EnrichmentConfig] = None,
    redis_conn: Optional[redis.Redis] = None,
) -> str:
    """
    Enfileira um job de enriquecimento para uma oferta.

    Args:
        offer_id: ID da oferta no banco de dados
        url: URL da oferta para scraping
        current_price_cents: Preço atual em centavos
        config: Configuração de enriquecimento (opcional)
        redis_conn: Conexão Redis (opcional)

    Returns:
        ID do job enfileirado
    """
    # Import local para evitar circular
    import queues.enrichment_jobs as enrichment_jobs_module

    queue = get_queue(config=config, redis_conn=redis_conn)
    job_timeout = config.job_timeout if config else "10m"

    job = queue.enqueue(
        enrichment_jobs_module.enrich_offer_job,
        offer_id,
        url,
        current_price_cents,
        job_timeout=job_timeout,
    )

    log(f"[queue] Job {job.id} enfileirado para oferta {offer_id} ({url})")
    return job.id
