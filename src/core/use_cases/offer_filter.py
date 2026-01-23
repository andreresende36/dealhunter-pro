"""Serviço para filtragem de ofertas."""

from __future__ import annotations

from shared.config.settings import ScrapeConfig
from core.domain import ScrapedOffer


class OfferFilter:
    """
    Serviço para filtrar ofertas de acordo com critérios configurados.

    Filtra ofertas baseado em:
    - Desconto mínimo (min_discount_pct)
    - Presença de preço antigo (only_with_old_price)
    - Ordenação por desconto e preço
    """

    def __init__(self, config: ScrapeConfig) -> None:
        """
        Inicializa o filtro com a configuração fornecida.

        Args:
            config: Configuração de scraping com critérios de filtro
        """
        self.config = config

    def filter_offers(self, offers: list[ScrapedOffer]) -> list[ScrapedOffer]:
        """
        Filtra ofertas de acordo com os critérios configurados.

        Args:
            offers: Lista de ofertas para filtrar

        Returns:
            Lista de ofertas filtradas e ordenadas
        """
        filtered: list[ScrapedOffer] = []

        for offer in offers:
            # Filtra ofertas sem preço antigo se necessário
            if self.config.only_with_old_price and not offer.old_price_cents:
                continue

            # Filtra ofertas sem desconto
            if offer.discount_pct is None:
                continue

            # Filtra ofertas com desconto menor que o mínimo
            if offer.discount_pct < self.config.min_discount_pct:
                continue

            filtered.append(offer)

        # Ordena por desconto decrescente, depois preço crescente
        filtered.sort(key=self._offer_sort_key)

        return filtered

    @staticmethod
    def _offer_sort_key(offer: ScrapedOffer) -> tuple[int, int]:
        """
        Chave de ordenação para ofertas.
        Ordena por desconto decrescente, depois preço crescente.
        """
        discount = offer.discount_pct if offer.discount_pct is not None else -1
        return (-discount, offer.price_cents)
