"""Módulo de filas para processamento assíncrono."""

from adapters.queues.enrichment_queue import (
    enqueue_enrichment_job,
    get_queue,
    get_redis_connection,
)

__all__ = [
    "enqueue_enrichment_job",
    "get_queue",
    "get_redis_connection",
]
