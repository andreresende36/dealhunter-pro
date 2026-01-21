-- Migration: Adiciona marketplaces e referencia ofertas por ID
-- Compatível com Supabase/PostgreSQL
-- Data: 2026-01-19

-- Extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tabela: marketplaces
CREATE TABLE IF NOT EXISTS marketplaces (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'marketplaces'
          AND constraint_name = 'unique_marketplaces_name'
    ) THEN
        ALTER TABLE marketplaces
            ADD CONSTRAINT unique_marketplaces_name UNIQUE (name);
    END IF;
END $$;

-- Garante marketplace inicial
INSERT INTO marketplaces (name)
VALUES ('Mercado Livre')
ON CONFLICT (name) DO NOTHING;

-- RLS e políticas para marketplaces (para bases já migradas)
ALTER TABLE marketplaces ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'marketplaces'
          AND policyname = 'marketplaces_select_anon'
    ) THEN
        EXECUTE 'CREATE POLICY "marketplaces_select_anon" ON marketplaces FOR SELECT TO anon USING (true)';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'marketplaces'
          AND policyname = 'marketplaces_insert_anon'
    ) THEN
        EXECUTE 'CREATE POLICY "marketplaces_insert_anon" ON marketplaces FOR INSERT TO anon WITH CHECK (true)';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'marketplaces'
          AND policyname = 'marketplaces_update_anon'
    ) THEN
        EXECUTE 'CREATE POLICY "marketplaces_update_anon" ON marketplaces FOR UPDATE TO anon USING (true) WITH CHECK (true)';
    END IF;
END $$;

-- Migra marketplaces existentes (se coluna antiga existir)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'offers'
          AND column_name = 'marketplace'
    ) THEN
        INSERT INTO marketplaces (name)
        SELECT DISTINCT marketplace
        FROM offers
        WHERE marketplace IS NOT NULL
        ON CONFLICT (name) DO NOTHING;
    END IF;
END $$;

-- Adiciona coluna marketplace_id
ALTER TABLE offers ADD COLUMN IF NOT EXISTS marketplace_id UUID;

-- Backfill via coluna antiga (se existir)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'offers'
          AND column_name = 'marketplace'
    ) THEN
        UPDATE offers o
        SET marketplace_id = m.id
        FROM marketplaces m
        WHERE o.marketplace = m.name;
    END IF;
END $$;

-- Preenche marketplace_id faltante com Mercado Livre
UPDATE offers
SET marketplace_id = ml.id
FROM (
    SELECT id
    FROM marketplaces
    WHERE name = 'Mercado Livre'
    LIMIT 1
) ml
WHERE offers.marketplace_id IS NULL;

-- FK offers -> marketplaces
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'offers'
          AND constraint_name = 'offers_marketplace_id_fkey'
    ) THEN
        ALTER TABLE offers
            ADD CONSTRAINT offers_marketplace_id_fkey
            FOREIGN KEY (marketplace_id) REFERENCES marketplaces(id)
            ON UPDATE CASCADE;
    END IF;
END $$;

ALTER TABLE offers ALTER COLUMN marketplace_id SET NOT NULL;

-- Remove colunas antigas
ALTER TABLE offers DROP COLUMN IF EXISTS marketplace;
ALTER TABLE offers DROP COLUMN IF EXISTS commission_pct;

-- Ajusta constraint de unicidade
ALTER TABLE offers DROP CONSTRAINT IF EXISTS unique_external_id;
ALTER TABLE offers
    ADD CONSTRAINT unique_external_id UNIQUE (external_id, marketplace_id);

-- Ajusta índices
DROP INDEX IF EXISTS idx_offers_marketplace;
CREATE INDEX IF NOT EXISTS idx_offers_marketplace_id ON offers(marketplace_id);
