"""Configuração e conexão com o banco de dados."""

from __future__ import annotations

import ssl
from typing import AsyncGenerator
from urllib.parse import urlparse, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from config import DatabaseConfig, get_config

Base = declarative_base()

# Engine e sessionmaker globais
_engine = None
_sessionmaker = None


def _clean_database_url(url: str) -> str:
    """Remove parâmetros SSL da URL que asyncpg não suporta."""
    parsed = urlparse(url)
    # Remove query string (onde está ?sslmode=require)
    # O asyncpg não suporta esses parâmetros via URL
    cleaned = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            "",  # Remove query string
            parsed.fragment,
        )
    )
    return cleaned


def init_db(config: DatabaseConfig | None = None) -> None:
    """Inicializa a conexão com o banco de dados."""
    global _engine, _sessionmaker

    if config is None:
        config = get_config().database

    # Remove parâmetros SSL da URL (asyncpg não os suporta via URL)
    cleaned_url = _clean_database_url(config.url)

    # Configura SSL para Supabase (requer SSL)
    # Cria contexto SSL sem verificação de certificado (equivale a sslmode=require)
    # O Supabase usa certificados que podem não estar na cadeia de confiança padrão
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    # Configuração específica para Supabase + asyncpg
    # Desabilita prepared statements cache (incompatível com pooler do Supabase)
    # pool_pre_ping detecta conexões fechadas antes de usá-las
    _engine = create_async_engine(
        cleaned_url,
        echo=config.echo,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_pre_ping=True,  # Detecta conexões fechadas antes de usar
        connect_args={
            "ssl": ssl_context,
            "statement_cache_size": 0,  # Desabilita cache de prepared statements
        },
    )

    _sessionmaker = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Retorna uma sessão do banco de dados."""
    global _sessionmaker

    if _sessionmaker is None:
        init_db()

    # Guarda referência local para type checking
    session_maker = _sessionmaker
    if session_maker is None:
        raise RuntimeError(
            "Database not initialized. Call init_db() before using get_session()."
        )

    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db() -> None:
    """Fecha a conexão com o banco de dados."""
    global _engine, _sessionmaker

    if _engine:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
