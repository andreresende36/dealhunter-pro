-- Migration: Schema inicial do banco de dados
-- Compatível com Supabase/PostgreSQL
-- Data: 2024

-- Extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tabela: offers (Ofertas)
CREATE TABLE IF NOT EXISTS offers (
    id BIGSERIAL PRIMARY KEY,
    marketplace VARCHAR(50) NOT NULL,
    external_id VARCHAR(100) NOT NULL,
    title VARCHAR(500) NOT NULL,
    url TEXT NOT NULL,
    image_url TEXT,
    price_cents INTEGER NOT NULL,
    old_price_cents INTEGER,
    discount_pct DECIMAL(5,2),
    commission_pct DECIMAL(5,2),
    affiliate_link TEXT,
    affiliation_id VARCHAR(100),
    source VARCHAR(50) DEFAULT 'ml_offers_playwright',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_external_id UNIQUE (external_id)
);

-- Índices para offers
CREATE INDEX IF NOT EXISTS idx_offers_marketplace ON offers(marketplace);
CREATE INDEX IF NOT EXISTS idx_offers_discount_pct ON offers(discount_pct);
CREATE INDEX IF NOT EXISTS idx_offers_created_at ON offers(created_at);
CREATE INDEX IF NOT EXISTS idx_offers_price_cents ON offers(price_cents);
CREATE INDEX IF NOT EXISTS idx_offers_updated_at ON offers(updated_at);

-- Tabela: scrape_runs (Execuções de scraping)
CREATE TABLE IF NOT EXISTS scrape_runs (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    raw_count INTEGER DEFAULT 0,
    filtered_count INTEGER DEFAULT 0,
    min_discount_pct DECIMAL(5,2),
    max_scrolls INTEGER,
    number_of_pages INTEGER,
    error_message TEXT,
    config_snapshot JSONB
);

-- Índices para scrape_runs
CREATE INDEX IF NOT EXISTS idx_scrape_runs_started_at ON scrape_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_scrape_runs_status ON scrape_runs(status);
CREATE INDEX IF NOT EXISTS idx_scrape_runs_finished_at ON scrape_runs(finished_at);

-- Tabela: offer_scrape_runs (Relacionamento N:N)
CREATE TABLE IF NOT EXISTS offer_scrape_runs (
    id BIGSERIAL PRIMARY KEY,
    offer_id BIGINT NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
    scrape_run_id BIGINT NOT NULL REFERENCES scrape_runs(id) ON DELETE CASCADE,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_offer_scrape_run UNIQUE (offer_id, scrape_run_id)
);

-- Índices para offer_scrape_runs
CREATE INDEX IF NOT EXISTS idx_offer_scrape_runs_offer_id ON offer_scrape_runs(offer_id);
CREATE INDEX IF NOT EXISTS idx_offer_scrape_runs_scrape_run_id ON offer_scrape_runs(scrape_run_id);
CREATE INDEX IF NOT EXISTS idx_offer_scrape_runs_detected_at ON offer_scrape_runs(detected_at);

-- Tabela: price_history (Histórico de preços)
CREATE TABLE IF NOT EXISTS price_history (
    id BIGSERIAL PRIMARY KEY,
    offer_id BIGINT NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
    price_cents INTEGER NOT NULL,
    old_price_cents INTEGER,
    discount_pct DECIMAL(5,2),
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    scrape_run_id BIGINT REFERENCES scrape_runs(id) ON DELETE SET NULL
);

-- Índices para price_history
CREATE INDEX IF NOT EXISTS idx_price_history_offer_id ON price_history(offer_id);
CREATE INDEX IF NOT EXISTS idx_price_history_recorded_at ON price_history(recorded_at);
CREATE INDEX IF NOT EXISTS idx_price_history_offer_recorded ON price_history(offer_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_price_history_scrape_run_id ON price_history(scrape_run_id);

-- Tabela: affiliate_info (Informações de afiliação)
CREATE TABLE IF NOT EXISTS affiliate_info (
    id BIGSERIAL PRIMARY KEY,
    offer_id BIGINT NOT NULL REFERENCES offers(id) ON DELETE CASCADE,
    commission_pct DECIMAL(5,2),
    affiliate_link TEXT,
    affiliation_id VARCHAR(100),
    checked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    scrape_run_id BIGINT REFERENCES scrape_runs(id) ON DELETE SET NULL
);

-- Índices para affiliate_info
CREATE INDEX IF NOT EXISTS idx_affiliate_info_offer_id ON affiliate_info(offer_id);
CREATE INDEX IF NOT EXISTS idx_affiliate_info_checked_at ON affiliate_info(checked_at);
CREATE INDEX IF NOT EXISTS idx_affiliate_info_offer_checked ON affiliate_info(offer_id, checked_at);
CREATE INDEX IF NOT EXISTS idx_affiliate_info_scrape_run_id ON affiliate_info(scrape_run_id);

-- Função para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para atualizar updated_at em offers
CREATE TRIGGER update_offers_updated_at
    BEFORE UPDATE ON offers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comentários nas tabelas
COMMENT ON TABLE offers IS 'Armazena ofertas coletadas de marketplaces';
COMMENT ON TABLE scrape_runs IS 'Registra execuções de scraping para auditoria';
COMMENT ON TABLE offer_scrape_runs IS 'Relaciona ofertas às execuções de scraping';
COMMENT ON TABLE price_history IS 'Histórico de preços das ofertas';
COMMENT ON TABLE affiliate_info IS 'Histórico de informações de afiliação';
