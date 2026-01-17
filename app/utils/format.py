"""Utilitários de formatação."""

from __future__ import annotations


def format_brl(cents: int | None) -> str:
    """Formata centavos como moeda brasileira (R$)."""
    if cents is None:
        return "-"
    val = cents / 100
    s = f"{val:,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def format_pct(value: float | None) -> str:
    """Formata porcentagem."""
    if value is None:
        return "-"
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"

