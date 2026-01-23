"""Módulo de banco de dados."""

from adapters.database.connection import get_client, get_session, init_db
from adapters.database.repositories import DatabaseService

__all__ = [
    "get_client",
    "get_session",
    "init_db",
    "DatabaseService",
]
