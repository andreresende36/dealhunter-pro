"""Utilitários de logging."""

from __future__ import annotations


def log(msg: str) -> None:
    """Registra uma mensagem no console."""
    print(msg, flush=True)

