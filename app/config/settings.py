"""Configurações do projeto carregadas de variáveis de ambiente."""

from __future__ import annotations

from dataclasses import dataclass

from dotenv import load_dotenv

from utils.env import env_bool, env_float, env_int, env_string


@dataclass(frozen=True)
class MLConfig:
    """Configurações específicas do Mercado Livre."""

    url: str
    card_selector: str
    title_selector: str
    picture_selector: str
    price_fraction_selector: str
    price_cents_selector: str
    old_fraction_selector: str
    old_cents_selector: str
    discount_selector: str

    @classmethod
    def from_env(cls) -> MLConfig:
        """Cria configuração a partir de variáveis de ambiente."""
        return cls(
            url=env_string("ML_URL", "https://www.mercadolivre.com.br/ofertas"),
            card_selector=env_string(
                "CARD_SELECTOR",
                ".andes-card.poly-card.poly-card--grid-card.poly-card--xlarge.andes-card--flat.andes-card--padding-0.andes-card--animated",
            ),
            title_selector=env_string(
                "TITLE_SELECTOR", ".poly-component__title-wrapper"
            ),
            picture_selector=env_string("PICTURE_SELECTOR", ".poly-component__picture"),
            price_fraction_selector=env_string(
                "PRICE_FRACTION_SELECTOR",
                "span.andes-money-amount.andes-money-amount--cents-superscript span.andes-money-amount__fraction",
            ),
            price_cents_selector=env_string(
                "PRICE_CENTS_SELECTOR",
                "span.andes-money-amount.andes-money-amount--cents-superscript span.andes-money-amount__cents",
            ),
            old_fraction_selector=env_string(
                "OLD_FRACTION_SELECTOR",
                "s.andes-money-amount.andes-money-amount--previous span.andes-money-amount__fraction",
            ),
            old_cents_selector=env_string(
                "OLD_CENTS_SELECTOR",
                "s.andes-money-amount.andes-money-amount--previous span.andes-money-amount__cents",
            ),
            discount_selector=env_string(
                "DISCOUNT_SELECTOR",
                "span.andes-money-amount__discount.poly-price__disc--pill",
            ),
        )


@dataclass(frozen=True)
class ScrapeConfig:
    """Configurações de scraping."""

    max_scrolls: int
    number_of_pages: int
    scroll_delay_s: float
    page_delay_s: float
    min_discount_pct: float
    only_with_old_price: bool
    debug_dump: bool

    @classmethod
    def from_env(cls) -> ScrapeConfig:
        """Cria configuração a partir de variáveis de ambiente."""
        return cls(
            max_scrolls=env_int("ML_MAX_SCROLLS", 4),
            number_of_pages=env_int("NUMBER_OF_PAGES", 1),
            scroll_delay_s=env_float("ML_SCROLL_DELAY_S", 0.45),
            page_delay_s=env_float("ML_PAGE_DELAY_S", 0.0),
            min_discount_pct=env_float("MIN_DISCOUNT_PCT", 50.0),
            only_with_old_price=env_bool("ONLY_WITH_OLD_PRICE", default=False),
            debug_dump=env_bool("DEBUG_DUMP", default=False),
        )


@dataclass(frozen=True)
class AffiliateConfig:
    """Configurações de afiliação."""

    commission_selector: str
    commission_selector_alternative: str
    button_selector: str
    affiliate_share_text: str
    affiliate_link_selector: str
    affiliation_id_selector: str
    concurrency: int

    @classmethod
    def from_env(cls) -> AffiliateConfig:
        """Cria configuração a partir de variáveis de ambiente."""
        return cls(
            commission_selector=env_string(
                "COMMISSION_SELECTOR", "span.stripe-commission__percentage"
            ),
            commission_selector_alternative=env_string(
                "COMMISSION_SELECTOR_ALTERNATIVE",
                "div.stripe-commission__info span",
            ),
            button_selector=env_string("BUTTON_SELECTOR", "span.andes-button__text"),
            affiliate_share_text=env_string("AFFILIATE_SHARE_TEXT", "Compartilhar"),
            affiliate_link_selector=env_string(
                "AFFILIATE_LINK_SELECTOR",
                '[data-testid="text-field__label_link"]',
            ),
            affiliation_id_selector=env_string(
                "AFFILIATION_ID_SELECTOR",
                '[data-testid="text-field__label_id"]',
            ),
            concurrency=env_int("AFFILIATE_CONCURRENCY", 3),
        )


@dataclass(frozen=True)
class DatabaseConfig:
    """Configurações do banco de dados."""

    supabase_url: str
    supabase_key: str

    @classmethod
    def from_env(cls) -> DatabaseConfig:
        """Cria configuração a partir de variáveis de ambiente."""
        supabase_url = env_string("SUPABASE_URL", "")

        # Prioridade: SERVICE_ROLE_KEY > SUPABASE_PUBLISHABLE_KEY > SUPABASE_ANON_KEY
        # SERVICE_ROLE_KEY ignora RLS e é mais segura para uso backend
        supabase_key = (
            env_string("SUPABASE_SERVICE_ROLE_KEY", "")
            or env_string("SUPABASE_PUBLISHABLE_KEY", "")
            or env_string("SUPABASE_ANON_KEY", "")
        )

        if not supabase_url or not supabase_key:
            raise ValueError(
                "SUPABASE_URL e uma das chaves (SUPABASE_SERVICE_ROLE_KEY, "
                "SUPABASE_PUBLISHABLE_KEY ou SUPABASE_ANON_KEY) devem estar configuradas no .env"
            )

        return cls(
            supabase_url=supabase_url,
            supabase_key=supabase_key,
        )


@dataclass(frozen=True)
class Config:
    """Configuração completa do projeto."""

    ml: MLConfig
    scrape: ScrapeConfig
    affiliate: AffiliateConfig
    database: DatabaseConfig
    max_items_print: int

    @classmethod
    def from_env(cls) -> Config:
        """Cria configuração completa a partir de variáveis de ambiente."""
        return cls(
            ml=MLConfig.from_env(),
            scrape=ScrapeConfig.from_env(),
            affiliate=AffiliateConfig.from_env(),
            database=DatabaseConfig.from_env(),
            max_items_print=env_int("MAX_ITEMS_PRINT", 20),
        )


def get_config() -> Config:
    """Carrega e retorna a configuração do projeto."""
    load_dotenv()
    return Config.from_env()
