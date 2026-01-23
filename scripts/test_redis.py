"""Script para testar conexão com Redis."""

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from config import get_config
from queues.enrichment_queue import get_redis_connection
from utils.logging import log


def main():
    """Testa conexão com Redis."""
    try:
        config = get_config()
        log(f"Testando conexão com Redis: {config.enrichment.redis_url}")

        redis_conn = get_redis_connection(config.enrichment)

        # Testa ping
        result = redis_conn.ping()
        log(f"✅ Redis está funcionando! Ping: {result}")

        # Testa algumas operações básicas
        redis_conn.set("test_key", "test_value")
        value = redis_conn.get("test_key")
        log(f"✅ Teste de escrita/leitura: {value}")

        redis_conn.delete("test_key")
        log("✅ Redis está pronto para uso!")

    except Exception as e:
        log(f"❌ Erro ao conectar ao Redis: {e}")
        import traceback

        log(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
