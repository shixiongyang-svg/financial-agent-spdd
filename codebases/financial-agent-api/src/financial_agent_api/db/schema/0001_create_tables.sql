CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS complaints (
  id BIGSERIAL PRIMARY KEY,
  complaint_id TEXT NOT NULL UNIQUE,
  date_received DATE NULL,
  product TEXT NULL,
  issue TEXT NULL,
  company TEXT NULL,
  state TEXT NULL,
  submitted_via TEXT NULL,
  narrative TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS docs (
  id BIGSERIAL PRIMARY KEY,
  source_file TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  title TEXT NULL,
  content TEXT NOT NULL,
  digest TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (source_file, chunk_index)
);

CREATE TABLE IF NOT EXISTS conversation_sessions (
  session_id TEXT PRIMARY KEY,
  conversation_history TEXT NOT NULL DEFAULT '[]',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS doc_embeddings (
  id BIGSERIAL PRIMARY KEY,
  doc_id BIGINT NOT NULL REFERENCES docs(id) ON DELETE CASCADE,
  embedding VECTOR(/* EMBEDDING_DIM */) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (doc_id)
);

-- Derived table: valid product/issue combinations from complaints (Task 4 PR #3)
-- Purpose: Support scenario_extraction filtering with allowed_product_issue_map
-- Populated after complaints ingestion completes
CREATE TABLE IF NOT EXISTS allowed_product_issue_map (
  id BIGSERIAL PRIMARY KEY,
  product TEXT NOT NULL,
  issue TEXT NOT NULL,
  complaint_count INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (product, issue)
);

CREATE INDEX IF NOT EXISTS idx_allowed_product_issue_map_product
  ON allowed_product_issue_map(product);
