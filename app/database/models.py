"""Modelos SQLAlchemy para o banco de dados."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.connection import Base


class Offer(Base):
    """Modelo de oferta no banco de dados."""

    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    marketplace: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    old_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    commission_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    affiliate_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    affiliation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="ml_offers_playwright"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="CURRENT_TIMESTAMP",
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relacionamentos
    scrape_runs: Mapped[list["OfferScrapeRun"]] = relationship(
        "OfferScrapeRun", back_populates="offer", cascade="all, delete-orphan"
    )
    price_history: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="offer", cascade="all, delete-orphan"
    )
    affiliate_info: Mapped[list["AffiliateInfo"]] = relationship(
        "AffiliateInfo", back_populates="offer", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_offers_marketplace", "marketplace"),
        Index("idx_offers_discount_pct", "discount_pct"),
        Index("idx_offers_created_at", "created_at"),
        Index("idx_offers_price_cents", "price_cents"),
        Index("idx_offers_updated_at", "updated_at"),
    )

    def __repr__(self) -> str:
        return f"<Offer(id={self.id}, external_id={self.external_id}, title={self.title[:50]}...)>"


class ScrapeRun(Base):
    """Modelo de execução de scraping."""

    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP"
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="running",
    )
    raw_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filtered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    min_discount_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    max_scrolls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    number_of_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relacionamentos
    offers: Mapped[list["OfferScrapeRun"]] = relationship(
        "OfferScrapeRun", back_populates="scrape_run", cascade="all, delete-orphan"
    )
    price_history: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="scrape_run"
    )
    affiliate_info: Mapped[list["AffiliateInfo"]] = relationship(
        "AffiliateInfo", back_populates="scrape_run"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed')", name="check_status"
        ),
        Index("idx_scrape_runs_started_at", "started_at"),
        Index("idx_scrape_runs_status", "status"),
        Index("idx_scrape_runs_finished_at", "finished_at"),
    )

    def __repr__(self) -> str:
        return f"<ScrapeRun(id={self.id}, status={self.status}, started_at={self.started_at})>"


class OfferScrapeRun(Base):
    """Modelo de relacionamento entre ofertas e execuções de scraping."""

    __tablename__ = "offer_scrape_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    offer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    scrape_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("scrape_runs.id", ondelete="CASCADE"), nullable=False
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP"
    )

    # Relacionamentos
    offer: Mapped["Offer"] = relationship("Offer", back_populates="scrape_runs")
    scrape_run: Mapped["ScrapeRun"] = relationship("ScrapeRun", back_populates="offers")

    __table_args__ = (
        UniqueConstraint("offer_id", "scrape_run_id", name="unique_offer_scrape_run"),
        Index("idx_offer_scrape_runs_offer_id", "offer_id"),
        Index("idx_offer_scrape_runs_scrape_run_id", "scrape_run_id"),
        Index("idx_offer_scrape_runs_detected_at", "detected_at"),
    )

    def __repr__(self) -> str:
        return f"<OfferScrapeRun(offer_id={self.offer_id}, scrape_run_id={self.scrape_run_id})>"


class PriceHistory(Base):
    """Modelo de histórico de preços."""

    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    offer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    old_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP"
    )
    scrape_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("scrape_runs.id", ondelete="SET NULL"), nullable=True
    )

    # Relacionamentos
    offer: Mapped["Offer"] = relationship("Offer", back_populates="price_history")
    scrape_run: Mapped["ScrapeRun | None"] = relationship(
        "ScrapeRun", back_populates="price_history"
    )

    __table_args__ = (
        Index("idx_price_history_offer_id", "offer_id"),
        Index("idx_price_history_recorded_at", "recorded_at"),
        Index("idx_price_history_offer_recorded", "offer_id", "recorded_at"),
        Index("idx_price_history_scrape_run_id", "scrape_run_id"),
    )

    def __repr__(self) -> str:
        return f"<PriceHistory(id={self.id}, offer_id={self.offer_id}, price_cents={self.price_cents})>"


class AffiliateInfo(Base):
    """Modelo de informações de afiliação."""

    __tablename__ = "affiliate_info"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    offer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    commission_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    affiliate_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    affiliation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP"
    )
    scrape_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("scrape_runs.id", ondelete="SET NULL"), nullable=True
    )

    # Relacionamentos
    offer: Mapped["Offer"] = relationship("Offer", back_populates="affiliate_info")
    scrape_run: Mapped["ScrapeRun | None"] = relationship(
        "ScrapeRun", back_populates="affiliate_info"
    )

    __table_args__ = (
        Index("idx_affiliate_info_offer_id", "offer_id"),
        Index("idx_affiliate_info_checked_at", "checked_at"),
        Index("idx_affiliate_info_offer_checked", "offer_id", "checked_at"),
        Index("idx_affiliate_info_scrape_run_id", "scrape_run_id"),
    )

    def __repr__(self) -> str:
        return f"<AffiliateInfo(id={self.id}, offer_id={self.offer_id}, commission_pct={self.commission_pct})>"
