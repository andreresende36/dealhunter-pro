"""Configuração e conexão com o banco de dados usando Supabase."""

from __future__ import annotations

import threading
from typing import AsyncGenerator, Optional

from supabase import Client, create_client

from shared.config.settings import DatabaseConfig, get_config

# Thread-local storage para clientes Supabase
# Cada thread terá sua própria instância do cliente
_thread_local = threading.local()


def init_db(config: DatabaseConfig | None = None) -> None:
    """
    Inicializa a conexão com o banco de dados usando Supabase.

    Thread-safe: cada thread terá sua própria conexão.

    Args:
        config: Configuração do banco de dados (opcional)
    """
    if config is None:
        config = get_config().database

    # Armazena no thread-local storage
    _thread_local.client = create_client(config.supabase_url, config.supabase_key)
    _thread_local.config = config


def get_client() -> Client:
    """
    Retorna o cliente Supabase para a thread atual.

    Thread-safe: cada thread obtém sua própria instância.

    Returns:
        Cliente Supabase da thread atual
    """
    # Verifica se o cliente já existe para esta thread
    if not hasattr(_thread_local, 'client') or _thread_local.client is None:
        init_db()

    if not hasattr(_thread_local, 'client') or _thread_local.client is None:
        raise RuntimeError(
            "Database not initialized. Call init_db() before using get_client()."
        )

    return _thread_local.client


# Mantém compatibilidade com código antigo (get_session)
async def get_session() -> AsyncGenerator[Client, None]:
    """Mantém compatibilidade com código que usa get_session()."""
    # Para supabase-py não precisamos de sessões async como SQLAlchemy
    # Mas mantemos a interface para não quebrar o código existente
    yield get_client()


async def close_db() -> None:
    """
    Fecha a conexão com o banco de dados para a thread atual.

    Thread-safe: fecha apenas a conexão da thread atual.
    """
    if hasattr(_thread_local, 'client'):
        _thread_local.client = None
    if hasattr(_thread_local, 'config'):
        _thread_local.config = None
