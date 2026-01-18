"""Configuração e conexão com o banco de dados usando Supabase."""

from __future__ import annotations

from typing import AsyncGenerator, Optional

from supabase import Client, create_client

from config import DatabaseConfig, get_config

# Cliente Supabase global
_client: Optional[Client] = None


def init_db(config: DatabaseConfig | None = None) -> None:
    """Inicializa a conexão com o banco de dados usando Supabase."""
    global _client

    if config is None:
        config = get_config().database

    _client = create_client(config.supabase_url, config.supabase_key)


def get_client() -> Client:
    """Retorna o cliente Supabase."""
    global _client

    if _client is None:
        init_db()

    if _client is None:
        raise RuntimeError(
            "Database not initialized. Call init_db() before using get_client()."
        )

    return _client


# Mantém compatibilidade com código antigo (get_session)
async def get_session() -> AsyncGenerator[Client, None]:
    """Mantém compatibilidade com código que usa get_session()."""
    # Para supabase-py não precisamos de sessões async como SQLAlchemy
    # Mas mantemos a interface para não quebrar o código existente
    yield get_client()


async def close_db() -> None:
    """Fecha a conexão com o banco de dados (no-op para Supabase)."""
    global _client
    _client = None
