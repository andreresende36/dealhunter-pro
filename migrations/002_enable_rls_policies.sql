-- Migration: Habilitar RLS e criar políticas para acesso via API
-- Compatível com Supabase/PostgreSQL
-- Data: 2026-01-18

-- Habilita Row Level Security em todas as tabelas
ALTER TABLE offers ENABLE ROW LEVEL SECURITY;
ALTER TABLE scrape_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE offer_scrape_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE affiliate_info ENABLE ROW LEVEL SECURITY;

-- Políticas para tabela 'offers'
CREATE POLICY "offers_select_anon" ON offers
    FOR SELECT TO anon USING (true);

CREATE POLICY "offers_insert_anon" ON offers
    FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "offers_update_anon" ON offers
    FOR UPDATE TO anon USING (true) WITH CHECK (true);

-- Políticas para tabela 'scrape_runs'
CREATE POLICY "scrape_runs_select_anon" ON scrape_runs
    FOR SELECT TO anon USING (true);

CREATE POLICY "scrape_runs_insert_anon" ON scrape_runs
    FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "scrape_runs_update_anon" ON scrape_runs
    FOR UPDATE TO anon USING (true) WITH CHECK (true);

-- Políticas para tabela 'offer_scrape_runs'
CREATE POLICY "offer_scrape_runs_select_anon" ON offer_scrape_runs
    FOR SELECT TO anon USING (true);

CREATE POLICY "offer_scrape_runs_insert_anon" ON offer_scrape_runs
    FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "offer_scrape_runs_update_anon" ON offer_scrape_runs
    FOR UPDATE TO anon USING (true) WITH CHECK (true);

-- Políticas para tabela 'price_history'
CREATE POLICY "price_history_select_anon" ON price_history
    FOR SELECT TO anon USING (true);

CREATE POLICY "price_history_insert_anon" ON price_history
    FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "price_history_update_anon" ON price_history
    FOR UPDATE TO anon USING (true) WITH CHECK (true);

-- Políticas para tabela 'affiliate_info'
CREATE POLICY "affiliate_info_select_anon" ON affiliate_info
    FOR SELECT TO anon USING (true);

CREATE POLICY "affiliate_info_insert_anon" ON affiliate_info
    FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "affiliate_info_update_anon" ON affiliate_info
    FOR UPDATE TO anon USING (true) WITH CHECK (true);
