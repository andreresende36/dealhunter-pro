-- Migration: Add Performance Indexes
-- Descrição: Adiciona índices para otimizar queries frequentes
-- Data: 2026-01-22

-- ============================================================================
-- ÍNDICES PARA TABELA OFFERS
-- ============================================================================

-- Índice composto para lookup de ofertas por external_id e marketplace
-- Usado em: get_by_external_id(), get_many_by_external_ids()
-- Impacto: 10-50x mais rápido em lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_offers_external_marketplace
    ON offers(external_id, marketplace_id);

-- Índice para buscar ofertas que precisam de enriquecimento
-- Usado em: get_offers_needing_enrichment()
-- Impacto: 5-10x mais rápido em queries de enriquecimento
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_offers_enrichment_status
    ON offers(old_price_cents, discount_pct, affiliate_info_id)
    WHERE old_price_cents IS NULL
       OR discount_pct IS NULL
       OR affiliate_info_id IS NULL;

-- Índice para filtrar ofertas por desconto
-- Usado em: filtros de desconto mínimo
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_offers_discount
    ON offers(discount_pct DESC)
    WHERE discount_pct IS NOT NULL;

-- Índice para ordenação por preço
-- Usado em: ordenação de ofertas
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_offers_price
    ON offers(price_cents);

-- Índice para buscar por marketplace
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_offers_marketplace
    ON offers(marketplace_id);

-- Índice para buscar por fonte de scraping
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_offers_source
    ON offers(source);

-- ============================================================================
-- ÍNDICES PARA TABELA PRICE_HISTORY
-- ============================================================================

-- Índice composto para histórico de preços de uma oferta
-- Usado em: consultas de histórico de preços
-- Impacto: 10-20x mais rápido em históricos
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_price_history_offer
    ON price_history(offer_id, created_at DESC);

-- Índice para buscar por scrape_run
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_price_history_scrape_run
    ON price_history(scrape_run_id);

-- ============================================================================
-- ÍNDICES PARA TABELA AFFILIATE_INFO
-- ============================================================================

-- Índice para buscar informações de afiliado por oferta
-- Usado em: get_affiliate_info_by_offer()
-- Impacto: 5-10x mais rápido
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_affiliate_info_offer
    ON affiliate_info(offer_id);

-- Índice para buscar por scrape_run
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_affiliate_info_scrape_run
    ON affiliate_info(scrape_run_id);

-- ============================================================================
-- ÍNDICES PARA TABELA SCRAPE_RUNS
-- ============================================================================

-- Índice para ordenar scrape_runs por data
-- Usado em: listagem de execuções recentes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_scrape_runs_started
    ON scrape_runs(started_at DESC);

-- Índice para filtrar por status
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_scrape_runs_status
    ON scrape_runs(status, started_at DESC);

-- ============================================================================
-- ÍNDICES PARA TABELA OFFER_SCRAPE_RUNS
-- ============================================================================

-- Índice para buscar ofertas de um scrape_run
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_offer_scrape_runs_scrape_run
    ON offer_scrape_runs(scrape_run_id);

-- Índice para buscar scrape_runs de uma oferta
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_offer_scrape_runs_offer
    ON offer_scrape_runs(offer_id);

-- ============================================================================
-- ÍNDICES PARA TABELA MARKETPLACES
-- ============================================================================

-- Índice único para buscar marketplace por nome
-- Usado em: _get_marketplace_id()
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_marketplaces_name
    ON marketplaces(name);

-- ============================================================================
-- ANÁLISE E ESTATÍSTICAS
-- ============================================================================

-- Atualiza estatísticas para o otimizador de queries
ANALYZE offers;
ANALYZE price_history;
ANALYZE affiliate_info;
ANALYZE scrape_runs;
ANALYZE offer_scrape_runs;
ANALYZE marketplaces;

-- ============================================================================
-- COMENTÁRIOS
-- ============================================================================

COMMENT ON INDEX idx_offers_external_marketplace IS
    'Índice composto para lookup rápido de ofertas por external_id e marketplace';

COMMENT ON INDEX idx_offers_enrichment_status IS
    'Índice parcial para buscar ofertas que precisam de enriquecimento';

COMMENT ON INDEX idx_price_history_offer IS
    'Índice para histórico de preços ordenado por data';

COMMENT ON INDEX idx_affiliate_info_offer IS
    'Índice para buscar informações de afiliado por oferta';

COMMENT ON INDEX idx_marketplaces_name IS
    'Índice único para garantir nomes de marketplace únicos';
