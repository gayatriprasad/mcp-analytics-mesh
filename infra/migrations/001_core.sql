-- 001_core.sql: core tables for Online Retail II + catalog/audit anchors

CREATE SCHEMA IF NOT EXISTS retail;

-- --- Dataset table (raw-ish, but typed) ---
CREATE TABLE IF NOT EXISTS retail.online_retail (
  invoice_no      TEXT NOT NULL,
  stock_code      TEXT,
  description     TEXT,
  quantity        INTEGER,
  invoice_date    TIMESTAMP,
  unit_price      NUMERIC(12, 4),
  customer_id     TEXT,
  country         TEXT
);

CREATE INDEX IF NOT EXISTS idx_or_invoice_date ON retail.online_retail (invoice_date);
CREATE INDEX IF NOT EXISTS idx_or_country      ON retail.online_retail (country);
CREATE INDEX IF NOT EXISTS idx_or_stock_code   ON retail.online_retail (stock_code);

-- --- Catalog table for freshness + snapshot determinism ---
CREATE TABLE IF NOT EXISTS retail.data_catalog (
  dataset_name       TEXT PRIMARY KEY,
  snapshot_id        TEXT NOT NULL,
  last_ingested_at   TIMESTAMP NOT NULL,
  sla_hours          INTEGER NOT NULL DEFAULT 24,
  source             TEXT,
  notes              TEXT
);

-- Seed row (will be updated by loader)
INSERT INTO retail.data_catalog (dataset_name, snapshot_id, last_ingested_at, sla_hours, source, notes)
VALUES ('online_retail', 'UNSET', NOW(), 24, 'UCI Online Retail II', 'Initialized')
ON CONFLICT (dataset_name) DO NOTHING;