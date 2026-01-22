"""Worker RQ para processar jobs de enriquecimento de ofertas."""

from __future__ import annotations

import sys
from pathlib import Path

# Adiciona o diretório raiz ao path para imports
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from config import get_config
from queues import get_queue
from rq import Worker
from utils.logging import log


def main() -> None:
    """Inicia worker RQ para processar jobs de enriquecimento."""
    try:
        config = get_config()
        queue = get_queue(config=config.enrichment)

        log(
            f"[worker] Iniciando worker RQ para fila '{config.enrichment.queue_name}' "
            f"(Redis: {config.enrichment.redis_url})"
        )
        log(
            f"[worker] Concorrência: {config.enrichment.worker_concurrency} workers"
        )

        # Cria e inicia o worker
        worker = Worker(
            [queue],
            name=f"enrichment-worker-{config.enrichment.queue_name}",
        )

        log("[worker] Worker iniciado. Aguardando jobs...")
        worker.work(with_scheduler=False)

    except KeyboardInterrupt:
        log("[worker] Worker interrompido pelo usuário")
        sys.exit(0)
    except Exception as e:
        log(f"[worker] ❌ ERRO ao iniciar worker: {type(e).__name__}: {e}")
        import traceback

        log(f"[worker] Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
