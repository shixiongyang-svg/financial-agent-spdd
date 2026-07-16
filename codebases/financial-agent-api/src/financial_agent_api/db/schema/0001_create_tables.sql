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

CREATE TABLE IF NOT EXISTS doc_embeddings (
  id BIGSERIAL PRIMARY KEY,
  doc_id BIGINT NOT NULL REFERENCES docs(id) ON DELETE CASCADE,
  embedding VECTOR(/* EMBEDDING_DIM */) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (doc_id)
);
