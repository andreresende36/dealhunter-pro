"""Worker RQ para processar jobs de enriquecimento de ofertas."""

from __future__ import annotations

import signal
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path para imports
root_dir = Path(__file__).parent.parent.parent
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from shared.config.settings import get_config
from adapters.queues import get_queue
from rq import Worker
from shared.utils.logging import log

# Variável global para controlar shutdown
_shutdown_requested = False
_worker: Worker | None = None


def graceful_shutdown(signum: int, frame) -> None:
    """
    Handler para shutdown gracioso do worker.

    Args:
        signum: Número do sinal recebido
        frame: Frame atual
    """
    global _shutdown_requested, _worker

    signal_names = {
        signal.SIGTERM: "SIGTERM",
        signal.SIGINT: "SIGINT",
    }

    signal_name = signal_names.get(signum, f"Signal {signum}")
    log(f"[worker] Recebido {signal_name}. Iniciando shutdown gracioso...")

    _shutdown_requested = True

    if _worker:
        # Solicita que o worker pare graciosamente após terminar o job atual
        log("[worker] Aguardando conclusão do job atual...")
        _worker.request_stop(signum=signum)


def health_check() -> bool:
    """
    Verifica saúde do worker.

    Returns:
        True se o worker está saudável
    """
    global _worker

    if _worker is None:
        return False

    # Verifica se ainda está vivo e não foi interrompido
    return not _shutdown_requested and _worker.state != "stopped"


def main() -> None:
    """Inicia worker RQ para processar jobs de enriquecimento."""
    global _worker

    # Registra handlers de sinal para graceful shutdown
    signal.signal(signal.SIGTERM, graceful_shutdown)
    signal.signal(signal.SIGINT, graceful_shutdown)

    try:
        config = get_config()

        # Obtém conexão Redis e cria a fila
        from adapters.queues.enrichment_queue import get_redis_connection

        redis_conn = get_redis_connection(config.enrichment)
        queue = get_queue(config=config.enrichment, redis_conn=redis_conn)

        # Testa a conexão
        try:
            redis_conn.ping()
            log("[worker] ✅ Conexão Redis OK")
        except Exception as e:
            log(f"[worker] ❌ Erro ao conectar ao Redis: {e}")
            log(
                f"[worker] Verifique se o Redis está rodando em {config.enrichment.redis_url}"
            )
            raise

        log(
            f"[worker] Iniciando worker RQ para fila '{config.enrichment.queue_name}' "
            f"(Redis: {config.enrichment.redis_url})"
        )
        log(f"[worker] Concorrência: {config.enrichment.worker_concurrency} workers")

        # Cria worker com a conexão Redis
        _worker = Worker(
            [queue],
            connection=redis_conn,
            name=f"enrichment-worker-{config.enrichment.queue_name}",
        )

        log("[worker] ✅ Worker iniciado. Aguardando jobs...")
        log("[worker] Pressione Ctrl+C para parar graciosamente")

        # Inicia o worker (bloqueia até receber sinal de parada)
        _worker.work(with_scheduler=False)

        log("[worker] Worker finalizado normalmente")

    except KeyboardInterrupt:
        log("[worker] Worker interrompido pelo usuário")
        sys.exit(0)
    except Exception as e:
        log(f"[worker] ❌ ERRO ao iniciar worker: {type(e).__name__}: {e}")
        import traceback

        log(f"[worker] Traceback: {traceback.format_exc()}")
        sys.exit(1)
    finally:
        # Cleanup
        if _worker:
            log("[worker] Limpando recursos...")
            try:
                # Fecha browser pool se estiver aberto
                import asyncio
                from adapters.workers.browser_pool import close_browser_pool

                asyncio.run(close_browser_pool())
                log("[worker] Browser pool fechado")
            except Exception as e:
                log(f"[worker] Erro ao fechar browser pool: {e}")

        log("[worker] Shutdown completo")


if __name__ == "__main__":
    main()
