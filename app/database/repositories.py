"""Repositórios para operações de banco de dados usando Supabase."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from supabase import Client

from models.offer import ScrapedOffer


class OfferRepository:
    """Repositório para operações com ofertas."""

    def __init__(self, client: Client) -> None:
        self.client = client
        self._marketplace_cache: dict[str, str] = {}

    async def _get_marketplace_id(self, marketplace_name: str) -> str:
        """Obtém (ou cria) o marketplace pelo nome e retorna o ID."""
        name = (marketplace_name or "").strip()
        if not name:
            raise ValueError("Marketplace inválido para salvar oferta.")

        cached = self._marketplace_cache.get(name)
        if cached:
            return cached

        response = (
            self.client.table("marketplaces")
            .select("id")
            .eq("name", name)
            .execute()
        )
        if response.data:
            marketplace_id = response.data[0]["id"]
            self._marketplace_cache[name] = marketplace_id
            return marketplace_id

        insert_response = (
            self.client.table("marketplaces").insert({"name": name}).execute()
        )
        marketplace_id = insert_response.data[0]["id"]
        self._marketplace_cache[name] = marketplace_id
        return marketplace_id

    async def get_by_external_id(
        self, external_id: str, marketplace_id: str
    ) -> dict[str, Any] | None:
        """Busca uma oferta pelo ID externo."""
        response = (
            self.client.table("offers")
            .select("*")
            .eq("external_id", external_id)
            .eq("marketplace_id", marketplace_id)
            .execute()
        )
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None

    async def create_or_update_from_scraped(
        self, scraped: ScrapedOffer
    ) -> tuple[dict[str, Any], bool]:
        """
        Cria ou atualiza uma oferta a partir de um ScrapedOffer.
        Retorna (offer_dict, is_new).
        """
        marketplace_id = await self._get_marketplace_id(scraped.marketplace)
        existing = await self.get_by_external_id(scraped.external_id, marketplace_id)

        offer_data = {
            "marketplace_id": marketplace_id,
            "external_id": scraped.external_id,
            "title": scraped.title,
            "url": scraped.url,
            "image_url": scraped.image_url,
            "price_cents": scraped.price_cents,
            "old_price_cents": scraped.old_price_cents,
            "discount_pct": (
                int(scraped.discount_pct)
                if scraped.discount_pct is not None
                else None
            ),
            "source": scraped.source,
        }

        if existing:
            # Atualiza oferta existente
            response = (
                self.client.table("offers")
                .update(offer_data)
                .eq("id", existing["id"])
                .execute()
            )
            return (response.data[0], False)

        # Cria nova oferta
        response = self.client.table("offers").insert(offer_data).execute()
        return (response.data[0], True)

    async def add_price_history(
        self, offer: dict[str, Any], scrape_run_id: str | None = None
    ) -> dict[str, Any]:
        """Adiciona um registro ao histórico de preços."""
        price_history_data = {
            "offer_id": offer["id"],
            "price_cents": offer["price_cents"],
            "old_price_cents": offer.get("old_price_cents"),
            "discount_pct": (
                int(offer["discount_pct"])
                if offer.get("discount_pct") is not None
                else None
            ),
            "scrape_run_id": scrape_run_id,
        }
        response = (
            self.client.table("price_history").insert(price_history_data).execute()
        )
        return response.data[0]

    async def add_affiliate_info(
        self,
        offer_id: str,
        scraped: ScrapedOffer,
        scrape_run_id: str | None = None,
    ) -> dict[str, Any]:
        """Adiciona um registro de informações de afiliação."""
        affiliate_info_data = {
            "offer_id": offer_id,
            "commission_pct": (
                int(scraped.commission_pct)
                if scraped.commission_pct is not None
                else None
            ),
            "affiliate_link": scraped.affiliate_link,
            "affiliation_id": scraped.affiliation_id,
            "scrape_run_id": scrape_run_id,
        }
        response = (
            self.client.table("affiliate_info").insert(affiliate_info_data).execute()
        )
        affiliate_info = response.data[0]
        self.client.table("offers").update(
            {"affiliate_info_id": affiliate_info["id"]}
        ).eq("id", offer_id).execute()
        return affiliate_info


class ScrapeRunRepository:
    """Repositório para operações com execuções de scraping."""

    def __init__(self, client: Client) -> None:
        self.client = client

    async def create(
        self,
        min_discount_pct: int | None = None,
        max_scrolls: int | None = None,
        number_of_pages: int | None = None,
        config_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Cria uma nova execução de scraping."""
        scrape_run_data = {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "min_discount_pct": (
                int(min_discount_pct) if min_discount_pct is not None else None
            ),
            "max_scrolls": max_scrolls,
            "number_of_pages": number_of_pages,
            "config_snapshot": config_snapshot,
        }
        response = self.client.table("scrape_runs").insert(scrape_run_data).execute()
        return response.data[0]

    async def update_status(
        self,
        scrape_run: dict[str, Any],
        status: str,
        filtered_count: int | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        """Atualiza o status de uma execução."""
        update_data: dict[str, Any] = {"status": status}
        if filtered_count is not None:
            update_data["filtered_count"] = filtered_count
        if error_message is not None:
            update_data["error_message"] = error_message
        if status in ("completed", "failed"):
            update_data["finished_at"] = datetime.now(timezone.utc).isoformat()

        response = (
            self.client.table("scrape_runs")
            .update(update_data)
            .eq("id", scrape_run["id"])
            .execute()
        )
        return response.data[0]

    async def link_offer(
        self, scrape_run: dict[str, Any], offer: dict[str, Any]
    ) -> dict[str, Any]:
        """Vincula uma oferta a uma execução de scraping."""
        # Verifica se já existe o relacionamento
        response = (
            self.client.table("offer_scrape_runs")
            .select("*")
            .eq("offer_id", offer["id"])
            .eq("scrape_run_id", scrape_run["id"])
            .execute()
        )

        if response.data and len(response.data) > 0:
            return response.data[0]

        # Cria novo relacionamento
        link_data = {
            "offer_id": offer["id"],
            "scrape_run_id": scrape_run["id"],
        }
        response = self.client.table("offer_scrape_runs").insert(link_data).execute()
        return response.data[0]

    async def get_by_id(self, scrape_run_id: str) -> dict[str, Any] | None:
        """Busca uma execução por ID."""
        response = (
            self.client.table("scrape_runs")
            .select("*")
            .eq("id", scrape_run_id)
            .execute()
        )
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None


class DatabaseService:
    """Serviço principal para operações de banco de dados."""

    def __init__(self, client: Client) -> None:
        self.client = client
        self.offers = OfferRepository(client)
        self.scrape_runs = ScrapeRunRepository(client)

    async def save_scrape_run_with_offers(
        self,
        offers: list[ScrapedOffer],
        min_discount_pct: int | None = None,
        max_scrolls: int | None = None,
        number_of_pages: int | None = None,
        config_snapshot: dict[str, Any] | None = None,
        save_price_history: bool = True,
        save_affiliate_info: bool = True,
    ) -> dict[str, Any]:
        """
        Salva uma execução de scraping com todas as ofertas coletadas.

        Args:
            offers: Lista de ofertas coletadas
            min_discount_pct: Desconto mínimo aplicado
            max_scrolls: Número máximo de scrolls
            number_of_pages: Número de páginas processadas
            config_snapshot: Snapshot da configuração
            save_price_history: Se deve salvar histórico de preços
            save_affiliate_info: Se deve salvar informações de afiliação

        Returns:
            ScrapeRun criado (como dict)
        """
        # Cria execução de scraping
        scrape_run = await self.scrape_runs.create(
            min_discount_pct=min_discount_pct,
            max_scrolls=max_scrolls,
            number_of_pages=number_of_pages,
            config_snapshot=config_snapshot,
        )

        # Processa cada oferta
        for scraped_offer in offers:
            # Cria ou atualiza oferta
            offer, _is_new = await self.offers.create_or_update_from_scraped(
                scraped_offer
            )

            # Vincula à execução
            await self.scrape_runs.link_offer(scrape_run, offer)

            # Salva histórico de preços se necessário
            if save_price_history:
                await self.offers.add_price_history(offer, scrape_run["id"])

            # Salva informações de afiliação se necessário
            if save_affiliate_info and (
                scraped_offer.commission_pct
                or scraped_offer.affiliate_link
                or scraped_offer.affiliation_id
            ):
                await self.offers.add_affiliate_info(
                    offer["id"], scraped_offer, scrape_run["id"]
                )

        # Atualiza contadores
        await self.scrape_runs.update_status(
            scrape_run,
            status="completed",
            filtered_count=len(offers),
        )

        return scrape_run
