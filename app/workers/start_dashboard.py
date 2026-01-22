"""Script para iniciar o RQ Dashboard para monitoramento de jobs."""

from __future__ import annotations

import sys
from pathlib import Path

# Adiciona o diretório raiz ao path para imports
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from config import get_config
from queues import get_redis_connection
from utils.logging import log


def main() -> None:
    """Inicia o RQ Dashboard."""
    try:
        config = get_config()
        redis_conn = get_redis_connection(config.enrichment)

        log(
            f"[dashboard] Iniciando RQ Dashboard para fila '{config.enrichment.queue_name}' "
            f"(Redis: {config.enrichment.redis_url})"
        )
        log("[dashboard] Dashboard acessível em: http://localhost:9181")
        log("[dashboard] Pressione Ctrl+C para parar o dashboard")

        # Inicia o dashboard usando o comando rq-dashboard
        import subprocess

        subprocess.run(
            [
                "rq-dashboard",
                "--redis-url",
                config.enrichment.redis_url,
                "--port",
                "9181",
            ]
        )

    except KeyboardInterrupt:
        log("[dashboard] Dashboard interrompido pelo usuário")
        sys.exit(0)
    except Exception as e:
        log(f"[dashboard] ❌ ERRO ao iniciar dashboard: {type(e).__name__}: {e}")
        import traceback

        log(f"[dashboard] Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
