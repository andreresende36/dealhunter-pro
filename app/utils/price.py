"""Utilitários para parsing de preços."""

from __future__ import annotations

import re

_PRICE_RE = re.compile(r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})|\d+(?:,\d{2})?)")


def parse_price_token(token: str) -> int | None:
    """Converte um token de preço (ex: '1.234,56') para centavos."""
    if not token:
        return None
    normalized = token.strip().replace(".", "").replace(",", ".")
    try:
        return int(round(float(normalized) * 100))
    except ValueError:
        return None


def price_to_cents(text: str) -> int | None:
    """Extrai o primeiro preço encontrado no texto e converte para centavos."""
    if not text:
        return None
    match = _PRICE_RE.search(text)
    if not match:
        return None
    return parse_price_token(match.group(1))


def all_prices_to_cents(text: str) -> list[int]:
    """Extrai todos os preços encontrados no texto e converte para centavos."""
    if not text:
        return []

    cents_list: list[int] = []
    for match in _PRICE_RE.finditer(text):
        cents = parse_price_token(match.group(1))
        if cents is not None:
            cents_list.append(cents)

    return cents_list


def discount_to_float(text: str) -> int | None:
    """Extrai porcentagem de desconto do texto como inteiro."""
    if not text:
        return None
    m = re.search(r"(\d{1,3})\s*%+", text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def parse_commission_pct(text: str) -> int | None:
    """Extrai porcentagem de comissão do texto como inteiro."""
    if not text:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)", text)
    if not m:
        return None
    try:
        value = float(m.group(1).replace(",", "."))
        return int(round(value))
    except ValueError:
        return None


def calc_discount(old_cents: int | None, price_cents: int) -> int | None:
    """Calcula o desconto percentual entre preço antigo e novo."""
    if not old_cents or old_cents <= 0:
        return None
    if price_cents >= old_cents:
        return 0
    discount = ((old_cents - price_cents) / old_cents) * 100.0
    return int(round(discount))


def digits_only(text: str) -> str:
    """Remove todos os caracteres não numéricos."""
    return re.sub(r"\D+", "", text or "")


def money_parts_to_cents(fraction_text: str, cents_text: str | None) -> int | None:
    """Combina fração e centavos em um valor total em centavos."""
    fraction_digits = digits_only(fraction_text)
    if not fraction_digits:
        return None

    cents_digits = digits_only(cents_text or "")
    if not cents_digits:
        cents_digits = "00"
    elif len(cents_digits) == 1:
        cents_digits = cents_digits + "0"
    elif len(cents_digits) > 2:
        cents_digits = cents_digits[:2]

    try:
        return int(fraction_digits) * 100 + int(cents_digits)
    except ValueError:
        return None


def infer_old_price_from_card_text(card_text: str, price_cents: int) -> int | None:
    """Infere o preço antigo do texto do card (maior valor encontrado)."""
    if not card_text:
        return None
    all_prices = all_prices_to_cents(card_text)
    if not all_prices:
        return None

    bigger_than_current = [p for p in all_prices if p > price_cents]
    if bigger_than_current:
        return max(bigger_than_current)
    return max(all_prices)
