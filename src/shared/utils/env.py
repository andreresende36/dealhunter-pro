"""Utilitários para leitura de variáveis de ambiente."""

from __future__ import annotations

import os


def env_string(name: str, default: str) -> str:
    """Lê uma variável de ambiente como string."""
    v = os.getenv(name, "").strip()
    return v if v else default


def env_int(name: str, default: int) -> int:
    """Lê uma variável de ambiente como inteiro."""
    v = os.getenv(name, "").strip()
    if not v:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    """Lê uma variável de ambiente como float."""
    v = os.getenv(name, "").strip()
    if not v:
        return default
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return default


def env_bool(name: str, default: bool = False) -> bool:
    """Lê uma variável de ambiente como booleano."""
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v in {"1", "true", "yes", "y", "on"}
