-- Migration: Atualiza IDs para UUID e percentuais para INTEGER
-- Compatível com Supabase/PostgreSQL
-- Data: 2026-01-19

-- Extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Converte IDs para UUID somente se ainda estiverem como BIGINT
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'offers'
          AND column_name = 'id'
          AND data_type <> 'uuid'
    ) THEN
        -- Adiciona colunas UUID auxiliares
        ALTER TABLE offers ADD COLUMN IF NOT EXISTS id_uuid uuid DEFAULT uuid_generate_v4();
        ALTER TABLE scrape_runs ADD COLUMN IF NOT EXISTS id_uuid uuid DEFAULT uuid_generate_v4();
        ALTER TABLE offer_scrape_runs ADD COLUMN IF NOT EXISTS id_uuid uuid DEFAULT uuid_generate_v4();
        ALTER TABLE price_history ADD COLUMN IF NOT EXISTS id_uuid uuid DEFAULT uuid_generate_v4();
        ALTER TABLE affiliate_info ADD COLUMN IF NOT EXISTS id_uuid uuid DEFAULT uuid_generate_v4();

        ALTER TABLE offer_scrape_runs ADD COLUMN IF NOT EXISTS offer_id_uuid uuid;
        ALTER TABLE offer_scrape_runs ADD COLUMN IF NOT EXISTS scrape_run_id_uuid uuid;
        ALTER TABLE price_history ADD COLUMN IF NOT EXISTS offer_id_uuid uuid;
        ALTER TABLE price_history ADD COLUMN IF NOT EXISTS scrape_run_id_uuid uuid;
        ALTER TABLE affiliate_info ADD COLUMN IF NOT EXISTS offer_id_uuid uuid;
        ALTER TABLE affiliate_info ADD COLUMN IF NOT EXISTS scrape_run_id_uuid uuid;

        -- Preenche IDs UUID
        UPDATE offers SET id_uuid = COALESCE(id_uuid, uuid_generate_v4());
        UPDATE scrape_runs SET id_uuid = COALESCE(id_uuid, uuid_generate_v4());
        UPDATE offer_scrape_runs SET id_uuid = COALESCE(id_uuid, uuid_generate_v4());
        UPDATE price_history SET id_uuid = COALESCE(id_uuid, uuid_generate_v4());
        UPDATE affiliate_info SET id_uuid = COALESCE(id_uuid, uuid_generate_v4());

        -- Mapeia FKs para UUID
        UPDATE offer_scrape_runs osr
        SET offer_id_uuid = o.id_uuid
        FROM offers o
        WHERE osr.offer_id = o.id;

        UPDATE offer_scrape_runs osr
        SET scrape_run_id_uuid = sr.id_uuid
        FROM scrape_runs sr
        WHERE osr.scrape_run_id = sr.id;

        UPDATE price_history ph
        SET offer_id_uuid = o.id_uuid
        FROM offers o
        WHERE ph.offer_id = o.id;

        UPDATE price_history ph
        SET scrape_run_id_uuid = sr.id_uuid
        FROM scrape_runs sr
        WHERE ph.scrape_run_id = sr.id;

        UPDATE affiliate_info ai
        SET offer_id_uuid = o.id_uuid
        FROM offers o
        WHERE ai.offer_id = o.id;

        UPDATE affiliate_info ai
        SET scrape_run_id_uuid = sr.id_uuid
        FROM scrape_runs sr
        WHERE ai.scrape_run_id = sr.id;

        -- Remove constraints antigas
        ALTER TABLE offer_scrape_runs DROP CONSTRAINT IF EXISTS offer_scrape_runs_offer_id_fkey;
        ALTER TABLE offer_scrape_runs DROP CONSTRAINT IF EXISTS offer_scrape_runs_scrape_run_id_fkey;
        ALTER TABLE price_history DROP CONSTRAINT IF EXISTS price_history_offer_id_fkey;
        ALTER TABLE price_history DROP CONSTRAINT IF EXISTS price_history_scrape_run_id_fkey;
        ALTER TABLE affiliate_info DROP CONSTRAINT IF EXISTS affiliate_info_offer_id_fkey;
        ALTER TABLE affiliate_info DROP CONSTRAINT IF EXISTS affiliate_info_scrape_run_id_fkey;
        ALTER TABLE offer_scrape_runs DROP CONSTRAINT IF EXISTS unique_offer_scrape_run;

        ALTER TABLE offers DROP CONSTRAINT IF EXISTS offers_pkey;
        ALTER TABLE scrape_runs DROP CONSTRAINT IF EXISTS scrape_runs_pkey;
        ALTER TABLE offer_scrape_runs DROP CONSTRAINT IF EXISTS offer_scrape_runs_pkey;
        ALTER TABLE price_history DROP CONSTRAINT IF EXISTS price_history_pkey;
        ALTER TABLE affiliate_info DROP CONSTRAINT IF EXISTS affiliate_info_pkey;

        -- Substitui IDs por UUID
        ALTER TABLE offers DROP COLUMN IF EXISTS id;
        ALTER TABLE offers RENAME COLUMN id_uuid TO id;
        ALTER TABLE offers ALTER COLUMN id SET DEFAULT uuid_generate_v4();
        ALTER TABLE offers ALTER COLUMN id SET NOT NULL;
        ALTER TABLE offers ADD PRIMARY KEY (id);

        ALTER TABLE scrape_runs DROP COLUMN IF EXISTS id;
        ALTER TABLE scrape_runs RENAME COLUMN id_uuid TO id;
        ALTER TABLE scrape_runs ALTER COLUMN id SET DEFAULT uuid_generate_v4();
        ALTER TABLE scrape_runs ALTER COLUMN id SET NOT NULL;
        ALTER TABLE scrape_runs ADD PRIMARY KEY (id);

        ALTER TABLE offer_scrape_runs DROP COLUMN IF EXISTS id;
        ALTER TABLE offer_scrape_runs RENAME COLUMN id_uuid TO id;
        ALTER TABLE offer_scrape_runs ALTER COLUMN id SET DEFAULT uuid_generate_v4();
        ALTER TABLE offer_scrape_runs ALTER COLUMN id SET NOT NULL;
        ALTER TABLE offer_scrape_runs ADD PRIMARY KEY (id);

        ALTER TABLE price_history DROP COLUMN IF EXISTS id;
        ALTER TABLE price_history RENAME COLUMN id_uuid TO id;
        ALTER TABLE price_history ALTER COLUMN id SET DEFAULT uuid_generate_v4();
        ALTER TABLE price_history ALTER COLUMN id SET NOT NULL;
        ALTER TABLE price_history ADD PRIMARY KEY (id);

        ALTER TABLE affiliate_info DROP COLUMN IF EXISTS id;
        ALTER TABLE affiliate_info RENAME COLUMN id_uuid TO id;
        ALTER TABLE affiliate_info ALTER COLUMN id SET DEFAULT uuid_generate_v4();
        ALTER TABLE affiliate_info ALTER COLUMN id SET NOT NULL;
        ALTER TABLE affiliate_info ADD PRIMARY KEY (id);

        -- Substitui FKs por UUID
        ALTER TABLE offer_scrape_runs DROP COLUMN IF EXISTS offer_id;
        ALTER TABLE offer_scrape_runs RENAME COLUMN offer_id_uuid TO offer_id;
        ALTER TABLE offer_scrape_runs ALTER COLUMN offer_id SET NOT NULL;

        ALTER TABLE offer_scrape_runs DROP COLUMN IF EXISTS scrape_run_id;
        ALTER TABLE offer_scrape_runs RENAME COLUMN scrape_run_id_uuid TO scrape_run_id;
        ALTER TABLE offer_scrape_runs ALTER COLUMN scrape_run_id SET NOT NULL;

        ALTER TABLE price_history DROP COLUMN IF EXISTS offer_id;
        ALTER TABLE price_history RENAME COLUMN offer_id_uuid TO offer_id;
        ALTER TABLE price_history ALTER COLUMN offer_id SET NOT NULL;

        ALTER TABLE price_history DROP COLUMN IF EXISTS scrape_run_id;
        ALTER TABLE price_history RENAME COLUMN scrape_run_id_uuid TO scrape_run_id;

        ALTER TABLE affiliate_info DROP COLUMN IF EXISTS offer_id;
        ALTER TABLE affiliate_info RENAME COLUMN offer_id_uuid TO offer_id;
        ALTER TABLE affiliate_info ALTER COLUMN offer_id SET NOT NULL;

        ALTER TABLE affiliate_info DROP COLUMN IF EXISTS scrape_run_id;
        ALTER TABLE affiliate_info RENAME COLUMN scrape_run_id_uuid TO scrape_run_id;
    END IF;
END $$;

-- Ajusta colunas de percentuais para INTEGER
ALTER TABLE offers
    ALTER COLUMN discount_pct TYPE INTEGER USING ROUND(discount_pct)::INTEGER,
    ALTER COLUMN commission_pct TYPE INTEGER USING ROUND(commission_pct)::INTEGER;

ALTER TABLE price_history
    ALTER COLUMN discount_pct TYPE INTEGER USING ROUND(discount_pct)::INTEGER;

ALTER TABLE affiliate_info
    ALTER COLUMN commission_pct TYPE INTEGER USING ROUND(commission_pct)::INTEGER;

ALTER TABLE scrape_runs
    ALTER COLUMN min_discount_pct TYPE INTEGER USING ROUND(min_discount_pct)::INTEGER;

-- Remove colunas não mais usadas
ALTER TABLE scrape_runs DROP COLUMN IF EXISTS raw_count;

-- Backfill de affiliate_info quando dados existirem em offers
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'offers'
          AND column_name = 'affiliate_link'
    ) THEN
        INSERT INTO affiliate_info (
            id,
            offer_id,
            commission_pct,
            affiliate_link,
            affiliation_id,
            checked_at,
            scrape_run_id
        )
        SELECT
            uuid_generate_v4(),
            o.id,
            CASE
                WHEN o.commission_pct IS NULL THEN NULL
                ELSE ROUND(o.commission_pct)::INTEGER
            END,
            o.affiliate_link,
            o.affiliation_id,
            CURRENT_TIMESTAMP,
            NULL
        FROM offers o
        WHERE (o.affiliate_link IS NOT NULL OR o.affiliation_id IS NOT NULL)
          AND NOT EXISTS (
              SELECT 1
              FROM affiliate_info ai
              WHERE ai.offer_id = o.id
          );
    END IF;
END $$;

-- Adiciona referência em offers para affiliate_info
ALTER TABLE offers ADD COLUMN IF NOT EXISTS affiliate_info_id uuid;

UPDATE offers o
SET affiliate_info_id = latest.id
FROM (
    SELECT DISTINCT ON (offer_id) offer_id, id
    FROM affiliate_info
    ORDER BY offer_id, checked_at DESC, id DESC
) latest
WHERE o.id = latest.offer_id
  AND (o.affiliate_info_id IS NULL OR o.affiliate_info_id <> latest.id);

ALTER TABLE offers DROP COLUMN IF EXISTS affiliate_link;
ALTER TABLE offers DROP COLUMN IF EXISTS affiliation_id;

-- Recria constraints com ON UPDATE CASCADE
ALTER TABLE offer_scrape_runs DROP CONSTRAINT IF EXISTS offer_scrape_runs_offer_id_fkey;
ALTER TABLE offer_scrape_runs DROP CONSTRAINT IF EXISTS offer_scrape_runs_scrape_run_id_fkey;
ALTER TABLE price_history DROP CONSTRAINT IF EXISTS price_history_offer_id_fkey;
ALTER TABLE price_history DROP CONSTRAINT IF EXISTS price_history_scrape_run_id_fkey;
ALTER TABLE affiliate_info DROP CONSTRAINT IF EXISTS affiliate_info_offer_id_fkey;
ALTER TABLE affiliate_info DROP CONSTRAINT IF EXISTS affiliate_info_scrape_run_id_fkey;
ALTER TABLE offer_scrape_runs DROP CONSTRAINT IF EXISTS unique_offer_scrape_run;
ALTER TABLE offers DROP CONSTRAINT IF EXISTS offers_affiliate_info_id_fkey;

ALTER TABLE offer_scrape_runs
    ADD CONSTRAINT offer_scrape_runs_offer_id_fkey
    FOREIGN KEY (offer_id) REFERENCES offers(id)
    ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE offer_scrape_runs
    ADD CONSTRAINT offer_scrape_runs_scrape_run_id_fkey
    FOREIGN KEY (scrape_run_id) REFERENCES scrape_runs(id)
    ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE offer_scrape_runs
    ADD CONSTRAINT unique_offer_scrape_run UNIQUE (offer_id, scrape_run_id);

ALTER TABLE price_history
    ADD CONSTRAINT price_history_offer_id_fkey
    FOREIGN KEY (offer_id) REFERENCES offers(id)
    ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE price_history
    ADD CONSTRAINT price_history_scrape_run_id_fkey
    FOREIGN KEY (scrape_run_id) REFERENCES scrape_runs(id)
    ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE affiliate_info
    ADD CONSTRAINT affiliate_info_offer_id_fkey
    FOREIGN KEY (offer_id) REFERENCES offers(id)
    ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE affiliate_info
    ADD CONSTRAINT affiliate_info_scrape_run_id_fkey
    FOREIGN KEY (scrape_run_id) REFERENCES scrape_runs(id)
    ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE offers
    ADD CONSTRAINT offers_affiliate_info_id_fkey
    FOREIGN KEY (affiliate_info_id) REFERENCES affiliate_info(id)
    ON DELETE SET NULL ON UPDATE CASCADE;

-- Recria índices
CREATE INDEX IF NOT EXISTS idx_offers_marketplace ON offers(marketplace);
CREATE INDEX IF NOT EXISTS idx_offers_discount_pct ON offers(discount_pct);
CREATE INDEX IF NOT EXISTS idx_offers_created_at ON offers(created_at);
CREATE INDEX IF NOT EXISTS idx_offers_price_cents ON offers(price_cents);
CREATE INDEX IF NOT EXISTS idx_offers_updated_at ON offers(updated_at);

CREATE INDEX IF NOT EXISTS idx_scrape_runs_started_at ON scrape_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_scrape_runs_status ON scrape_runs(status);
CREATE INDEX IF NOT EXISTS idx_scrape_runs_finished_at ON scrape_runs(finished_at);

CREATE INDEX IF NOT EXISTS idx_offer_scrape_runs_offer_id ON offer_scrape_runs(offer_id);
CREATE INDEX IF NOT EXISTS idx_offer_scrape_runs_scrape_run_id ON offer_scrape_runs(scrape_run_id);
CREATE INDEX IF NOT EXISTS idx_offer_scrape_runs_detected_at ON offer_scrape_runs(detected_at);

CREATE INDEX IF NOT EXISTS idx_price_history_offer_id ON price_history(offer_id);
CREATE INDEX IF NOT EXISTS idx_price_history_recorded_at ON price_history(recorded_at);
CREATE INDEX IF NOT EXISTS idx_price_history_offer_recorded ON price_history(offer_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_price_history_scrape_run_id ON price_history(scrape_run_id);

CREATE INDEX IF NOT EXISTS idx_affiliate_info_offer_id ON affiliate_info(offer_id);
CREATE INDEX IF NOT EXISTS idx_affiliate_info_checked_at ON affiliate_info(checked_at);
CREATE INDEX IF NOT EXISTS idx_affiliate_info_offer_checked ON affiliate_info(offer_id, checked_at);
CREATE INDEX IF NOT EXISTS idx_affiliate_info_scrape_run_id ON affiliate_info(scrape_run_id);
