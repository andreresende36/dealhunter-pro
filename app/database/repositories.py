"""Repositórios para operações de banco de dados."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import (
    AffiliateInfo,
    Offer,
    OfferScrapeRun,
    PriceHistory,
    ScrapeRun,
)
from models.offer import ScrapedOffer


class OfferRepository:
    """Repositório para operações com ofertas."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_external_id(
        self, external_id: str, marketplace: str
    ) -> Offer | None:
        """Busca uma oferta pelo ID externo."""
        stmt = select(Offer).where(
            Offer.external_id == external_id, Offer.marketplace == marketplace
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_or_update_from_scraped(
        self, scraped: ScrapedOffer
    ) -> tuple[Offer, bool]:
        """
        Cria ou atualiza uma oferta a partir de um ScrapedOffer.
        Retorna (offer, is_new).
        """
        existing = await self.get_by_external_id(
            scraped.external_id, scraped.marketplace
        )

        if existing:
            # Atualiza oferta existente
            existing.title = scraped.title
            existing.url = scraped.url
            existing.image_url = scraped.image_url
            existing.price_cents = scraped.price_cents
            existing.old_price_cents = scraped.old_price_cents
            existing.discount_pct = (
                Decimal(str(scraped.discount_pct))
                if scraped.discount_pct is not None
                else None
            )
            existing.commission_pct = (
                Decimal(str(scraped.commission_pct))
                if scraped.commission_pct is not None
                else None
            )
            existing.affiliate_link = scraped.affiliate_link
            existing.affiliation_id = scraped.affiliation_id
            existing.source = scraped.source
            return (existing, False)

        # Cria nova oferta
        new_offer = Offer(
            marketplace=scraped.marketplace,
            external_id=scraped.external_id,
            title=scraped.title,
            url=scraped.url,
            image_url=scraped.image_url,
            price_cents=scraped.price_cents,
            old_price_cents=scraped.old_price_cents,
            discount_pct=(
                Decimal(str(scraped.discount_pct))
                if scraped.discount_pct is not None
                else None
            ),
            commission_pct=(
                Decimal(str(scraped.commission_pct))
                if scraped.commission_pct is not None
                else None
            ),
            affiliate_link=scraped.affiliate_link,
            affiliation_id=scraped.affiliation_id,
            source=scraped.source,
        )
        self.session.add(new_offer)
        await self.session.flush()
        return (new_offer, True)

    async def add_price_history(
        self, offer: Offer, scrape_run_id: int | None = None
    ) -> PriceHistory:
        """Adiciona um registro ao histórico de preços."""
        price_history = PriceHistory(
            offer_id=offer.id,
            price_cents=offer.price_cents,
            old_price_cents=offer.old_price_cents,
            discount_pct=offer.discount_pct,
            scrape_run_id=scrape_run_id,
        )
        self.session.add(price_history)
        await self.session.flush()
        return price_history

    async def add_affiliate_info(
        self, offer: Offer, scrape_run_id: int | None = None
    ) -> AffiliateInfo:
        """Adiciona um registro de informações de afiliação."""
        affiliate_info = AffiliateInfo(
            offer_id=offer.id,
            commission_pct=offer.commission_pct,
            affiliate_link=offer.affiliate_link,
            affiliation_id=offer.affiliation_id,
            scrape_run_id=scrape_run_id,
        )
        self.session.add(affiliate_info)
        await self.session.flush()
        return affiliate_info


class ScrapeRunRepository:
    """Repositório para operações com execuções de scraping."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        min_discount_pct: float | None = None,
        max_scrolls: int | None = None,
        number_of_pages: int | None = None,
        config_snapshot: dict[str, Any] | None = None,
    ) -> ScrapeRun:
        """Cria uma nova execução de scraping."""
        scrape_run = ScrapeRun(
            status="running",
            started_at=datetime.now(timezone.utc),
            min_discount_pct=(
                Decimal(str(min_discount_pct)) if min_discount_pct is not None else None
            ),
            max_scrolls=max_scrolls,
            number_of_pages=number_of_pages,
            config_snapshot=config_snapshot,
        )
        self.session.add(scrape_run)
        await self.session.flush()
        return scrape_run

    async def update_status(
        self,
        scrape_run: ScrapeRun,
        status: str,
        raw_count: int | None = None,
        filtered_count: int | None = None,
        error_message: str | None = None,
    ) -> ScrapeRun:
        """Atualiza o status de uma execução."""
        scrape_run.status = status
        if raw_count is not None:
            scrape_run.raw_count = raw_count
        if filtered_count is not None:
            scrape_run.filtered_count = filtered_count
        if error_message is not None:
            scrape_run.error_message = error_message
        if status in ("completed", "failed"):
            scrape_run.finished_at = datetime.now(timezone.utc)
        await self.session.flush()
        return scrape_run

    async def link_offer(self, scrape_run: ScrapeRun, offer: Offer) -> OfferScrapeRun:
        """Vincula uma oferta a uma execução de scraping."""
        # Verifica se já existe o relacionamento
        stmt = select(OfferScrapeRun).where(
            OfferScrapeRun.offer_id == offer.id,
            OfferScrapeRun.scrape_run_id == scrape_run.id,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return existing

        # Cria novo relacionamento
        link = OfferScrapeRun(
            offer_id=offer.id,
            scrape_run_id=scrape_run.id,
        )
        self.session.add(link)
        await self.session.flush()
        return link

    async def get_by_id(self, scrape_run_id: int) -> ScrapeRun | None:
        """Busca uma execução por ID."""
        stmt = (
            select(ScrapeRun)
            .where(ScrapeRun.id == scrape_run_id)
            .options(selectinload(ScrapeRun.offers).selectinload(OfferScrapeRun.offer))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class DatabaseService:
    """Serviço principal para operações de banco de dados."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.offers = OfferRepository(session)
        self.scrape_runs = ScrapeRunRepository(session)

    async def save_scrape_run_with_offers(
        self,
        offers: list[ScrapedOffer],
        min_discount_pct: float | None = None,
        max_scrolls: int | None = None,
        number_of_pages: int | None = None,
        config_snapshot: dict[str, Any] | None = None,
        save_price_history: bool = True,
        save_affiliate_info: bool = True,
    ) -> ScrapeRun:
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
            ScrapeRun criado
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
            offer, is_new = await self.offers.create_or_update_from_scraped(
                scraped_offer
            )

            # Vincula à execução
            await self.scrape_runs.link_offer(scrape_run, offer)

            # Salva histórico de preços se necessário
            if save_price_history:
                await self.offers.add_price_history(offer, scrape_run.id)

            # Salva informações de afiliação se necessário
            if save_affiliate_info and (
                scraped_offer.commission_pct
                or scraped_offer.affiliate_link
                or scraped_offer.affiliation_id
            ):
                await self.offers.add_affiliate_info(offer, scrape_run.id)

        # Atualiza contadores
        await self.scrape_runs.update_status(
            scrape_run,
            status="completed",
            raw_count=len(offers),
            filtered_count=len(offers),
        )

        return scrape_run
