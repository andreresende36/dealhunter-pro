"""Repositórios para operações de banco de dados usando Supabase."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from supabase import Client

from core.domain.offer import ScrapedOffer
from shared.constants import DEFAULT_QUERY_LIMIT


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

    async def get_many_by_external_ids(
        self, external_ids: list[str], marketplace_id: str
    ) -> dict[str, dict[str, Any]]:
        """
        Busca múltiplas ofertas pelos IDs externos em uma única query.

        Args:
            external_ids: Lista de IDs externos
            marketplace_id: ID do marketplace

        Returns:
            Dicionário mapeando external_id -> oferta
        """
        if not external_ids:
            return {}

        response = (
            self.client.table("offers")
            .select("*")
            .eq("marketplace_id", marketplace_id)
            .in_("external_id", external_ids)
            .execute()
        )

        # Cria um mapa de external_id -> oferta para lookup rápido
        result = {}
        if response.data:
            for offer in response.data:
                result[offer["external_id"]] = offer

        return result

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

    async def get_by_id(self, offer_id: str) -> dict[str, Any] | None:
        """Busca uma oferta pelo ID."""
        response = (
            self.client.table("offers")
            .select("*")
            .eq("id", offer_id)
            .execute()
        )
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None

    async def update_offer_enrichment(
        self,
        offer_id: str,
        old_price_cents: int | None = None,
        discount_pct: int | None = None,
        affiliate_link: str | None = None,
        affiliation_id: str | None = None,
        scrape_run_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Atualiza campos enriquecidos de uma oferta.

        Args:
            offer_id: ID da oferta
            old_price_cents: Preço antigo em centavos
            discount_pct: Porcentagem de desconto
            affiliate_link: Link de afiliado
            affiliation_id: ID de afiliação
            scrape_run_id: ID da execução de scraping (opcional)

        Returns:
            Oferta atualizada
        """
        update_data: dict[str, Any] = {}

        if old_price_cents is not None:
            update_data["old_price_cents"] = old_price_cents

        if discount_pct is not None:
            update_data["discount_pct"] = int(discount_pct)

        response = (
            self.client.table("offers")
            .update(update_data)
            .eq("id", offer_id)
            .execute()
        )

        if not response.data:
            raise ValueError(f"Oferta com ID {offer_id} não encontrada")

        updated_offer = response.data[0]

        # Atualiza ou cria affiliate_info se houver dados de afiliado
        if affiliate_link is not None or affiliation_id is not None:
            # Busca affiliate_info existente
            existing_affiliate = None
            if updated_offer.get("affiliate_info_id"):
                try:
                    affiliate_response = (
                        self.client.table("affiliate_info")
                        .select("*")
                        .eq("id", updated_offer["affiliate_info_id"])
                        .execute()
                    )
                    if affiliate_response.data:
                        existing_affiliate = affiliate_response.data[0]
                except Exception:
                    pass

            affiliate_info_data: dict[str, Any] = {
                "offer_id": offer_id,
                "scrape_run_id": scrape_run_id,
            }

            if affiliate_link is not None:
                affiliate_info_data["affiliate_link"] = affiliate_link
            if affiliation_id is not None:
                affiliate_info_data["affiliation_id"] = affiliation_id

            if existing_affiliate:
                # Atualiza affiliate_info existente
                affiliate_response = (
                    self.client.table("affiliate_info")
                    .update(affiliate_info_data)
                    .eq("id", existing_affiliate["id"])
                    .execute()
                )
            else:
                # Cria novo affiliate_info
                affiliate_response = (
                    self.client.table("affiliate_info")
                    .insert(affiliate_info_data)
                    .execute()
                )
                # Atualiza offer com affiliate_info_id
                self.client.table("offers").update(
                    {"affiliate_info_id": affiliate_response.data[0]["id"]}
                ).eq("id", offer_id).execute()

        return updated_offer

    async def get_offers_needing_enrichment(
        self,
        limit: int = DEFAULT_QUERY_LIMIT,
        missing_old_price: bool = True,
        missing_discount: bool = True,
        missing_affiliate_link: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Busca ofertas que precisam de enriquecimento.

        Args:
            limit: Número máximo de ofertas a retornar
            missing_old_price: Incluir ofertas sem old_price_cents
            missing_discount: Incluir ofertas sem discount_pct
            missing_affiliate_link: Incluir ofertas sem affiliate_link

        Returns:
            Lista de ofertas que precisam enriquecimento
        """
        # Para Supabase, precisamos fazer queries separadas e combinar resultados
        # ou usar uma abordagem mais simples
        all_offers: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        # Busca ofertas sem old_price_cents
        if missing_old_price:
            try:
                response = (
                    self.client.table("offers")
                    .select("id, url, price_cents, old_price_cents, discount_pct, affiliate_info_id")
                    .is_("old_price_cents", "null")
                    .limit(limit)
                    .execute()
                )
                if response.data:
                    for offer in response.data:
                        if offer["id"] not in seen_ids:
                            all_offers.append(offer)
                            seen_ids.add(offer["id"])
            except Exception:
                pass

        # Busca ofertas sem discount_pct
        if missing_discount:
            try:
                response = (
                    self.client.table("offers")
                    .select("id, url, price_cents, old_price_cents, discount_pct, affiliate_info_id")
                    .is_("discount_pct", "null")
                    .limit(limit)
                    .execute()
                )
                if response.data:
                    for offer in response.data:
                        if offer["id"] not in seen_ids:
                            all_offers.append(offer)
                            seen_ids.add(offer["id"])
            except Exception:
                pass

        # Busca ofertas sem affiliate_info_id
        if missing_affiliate_link:
            try:
                response = (
                    self.client.table("offers")
                    .select("id, url, price_cents, old_price_cents, discount_pct, affiliate_info_id")
                    .is_("affiliate_info_id", "null")
                    .limit(limit)
                    .execute()
                )
                if response.data:
                    for offer in response.data:
                        if offer["id"] not in seen_ids:
                            all_offers.append(offer)
                            seen_ids.add(offer["id"])
            except Exception:
                pass

        return all_offers[:limit]


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
