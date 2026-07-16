# Week 2 — From Foundations to Naive RAG

You shipped Week 1: `Settings`, `LLMService`, structured logging
with `request_id`. The agent can call an LLM but it doesn't yet
*retrieve* anything. This week the corpus lands.

## What you're getting this week

- `.spdd_specs/tasks/Task_2_Ingestion.trainee.md` — your
  Monday brief.
- On Sunday: the destination canvas `Task_2_Ingestion.md`.

## What this week introduces

1. **The `complaints` and `docs` tables** plus a
   `doc_embeddings` pgvector table.
2. **Two ingestion scripts** — one for the public CSV
   (`ingest_public_data.py`) and one for the markdown corpus
   (`embed_starter_docs.py`). Source paths are configured via
   environment variables (`COMPLAINTS_CSV_PATH`,
   `DOCS_SOURCE_DIR`) rather than hardcoded directories.
3. **`RetrievalService`** with two methods (`retrieve_docs`,
   `retrieve_complaints`).

You're building a *deliberately simple* RAG this week. It will
appear to work. Future weeks may revisit retrieval choices —
trust that there are reasons we're keeping this week's surface
small.

## Why we did it this way

- **Why fixed-size chunking, not section-aware?** Because
  section-aware needs a doc parser, and we want you to feel the
  recall failure of fixed-size chunking before you invest in
  better. Skip the lesson and you optimise the wrong thing
  next time.
- **Why `apply_schema` with string substitution, not Alembic?**
  Trade-off documented in the constitution under "Risks &
  Trade-offs". Pedagogical simplicity here, *not* a pattern to
  copy to production.
- **Why upsert on `complaint_id` and not just insert?**
  Because the ingestion script must be idempotent. Re-running
  it on the same CSV must not double-count.

## Common Week-2 pitfalls

| Pitfall | What it looks like | The fix |
|---|---|---|
| String-formatting SQL | `f"WHERE product = '{product}'"`. | Use SQLAlchemy `text()` with bound params. The constitution forbids string-built SQL anywhere it accepts user input. |
| Embedding dim drift | Ingest writes 768-dim vectors; later code reads 1536. | The schema's `/* EMBEDDING_DIM */` placeholder is the contract; `apply_schema` substitutes from `Settings.embedding_dim`. Pick one and stick with it. |
| Returning ORM objects from `RetrievalService` | Session lifetime escapes the service; tests start failing for opaque reasons. | Project to `DocumentChunk` / `ComplaintRow` Pydantic models inside the service, before returning. |
| Forgetting `request_id: str \| None = None` | Public service methods miss the param; structured logs lose correlation. | Required by the Week-1 logging contract. Every public method takes it. |
| Hardcoded corpus paths | Scripts only work on one machine/path layout. | Read inputs from `COMPLAINTS_CSV_PATH` and `DOCS_SOURCE_DIR` in `Settings`; fail explicitly when missing or invalid. |

## Wednesday self-check

- [ ] *Risks noticed* covers deduplication of `(source_file,
      chunk_index)` pairs, embedding drift, and PII handling
      for the `narrative` column.
- [ ] *Trade-offs accepted* names fixed-size vs section-aware
      chunking, `IF NOT EXISTS` schema vs migrations, ILIKE vs
      full-text search.
- [ ] *Class diagram* shows `RetrievalService → SQLAlchemy
      session_factory → Postgres`, plus `LLMService` injection
      for embeddings.
- [ ] *Operations* numbered. Schema filename pinned to
      `0001_create_tables.sql` (the destination naming will
      assume this).
- [ ] *Input path control* confirms ingestion sources are read from
      `COMPLAINTS_CSV_PATH` and `DOCS_SOURCE_DIR`, not hardcoded.

## What Sunday will reveal

The destination canvas pins the exact `RetrievalService`
signatures the rest of the curriculum depends on, including
parameters you may not have written yet, and the ILIKE / ORDER
BY clauses inside the SQL. Expect a small reconciliation diff:
your `__init__` may be missing an `embedding_dim` argument, or
your `retrieve_complaints` may be missing a positional argument.

## Going further (optional reading)

- A primer on pgvector index types — HNSW vs IVFFlat — and
  when each wins. (You're not building an index this week, but
  the choice matters for Week 6.)
  [pgvector Official Indexing Documentation](https://github.com/pgvector/pgvector#indexing)
- The Anthropic / OpenAI cookbook chapters on chunking
  strategies. Fixed-size chunking fails frequently compared to
  section-aware chunking.
  [Pinecone: Chunking Strategies for LLM Applications](https://www.pinecone.io/learn/chunking-strategies/)
- The CFPB consumer complaints data dictionary so you
  understand what an `Issue` value actually means.
  [CFPB Consumer Complaint Database Data Dictionary](https://cfpb.github.io/api/ccdb/data_dictionary.html)
- **SQL Injection in the Age of AI:** String-formatting SQL
  like `f"WHERE product = '{product}'"` is forbidden; use
  SQLAlchemy `text()` with bound params.
  [SQLAlchemy: Using Textual SQL safely](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html)

## Post-reading questions

TODO AI answer these in order; only generate the implementation plan after user approval.

1. Should the `doc_embeddings` pgvector table be linked to the `docs` table? If yes, how?
   **[AI Answer]**
   Yes. It should be a **strong relational link**.

   Recommended:
   - `docs` has primary key `id` (typically `bigserial` or `uuid`)
   - `doc_embeddings` stores `doc_id` as a foreign key to `docs.id`
   - SQL uses `FOREIGN KEY (doc_id) REFERENCES docs(id) ON DELETE CASCADE`

   Benefits:
   - Prevents orphan embedding rows
   - Cleans embeddings automatically when docs are deleted
   - Enables stable joins: `doc_embeddings JOIN docs ON doc_embeddings.doc_id = docs.id`

2. How is data in `doc_embeddings` generated?
   **[AI Answer]**
   Typical flow:
   1. Read markdown source
   2. Split into fixed-size chunks
   3. Call embedding API for each chunk (via `LLMService.embed`)
   4. Write returned `List[float]` into `doc_embeddings.embedding` (pgvector)
   5. Write linkage metadata (`doc_id`, `chunk_index`, and optionally chunk text fields)

   In short, `doc_embeddings` is generated by ingestion scripts + embedding inference, not manual inserts.

3. Does fixed-size chunking mean substring by fixed length on markdown content?
   **[AI Answer]**
   Conceptually yes, but prefer **fixed window + light boundary handling** over raw hard cuts.

   Typical practice:
   - Convert markdown to plain/near-plain text
   - Chunk by fixed character window (e.g., 800–1200 chars)
   - Optionally add overlap (e.g., 100–200 chars) to reduce semantic breaks

   This week intentionally uses a simple, repeatable approach before section-aware parsing.

4. What does `apply_schema` string substitution actually do? I still don’t fully get the `/* EMBEDDING_DIM */` replacement part.
   **[AI Answer]**
   Your understanding is mostly correct. Split into two concerns:

   - Schema SQL file exists (e.g., `0001_create_tables.sql`)
   - Vector column uses a placeholder, e.g. `embedding vector(/* EMBEDDING_DIM */)`
   - Before execution, `apply_schema` replaces that placeholder with config value (e.g., `1536`)
   - Final SQL becomes `embedding vector(1536)` and is then executed

   Why replace:
   - pgvector dimension must be a **constant**, not a bound runtime parameter
   - Different embedding models use different dimensions

   Distinct from idempotency:
   - **Placeholder replacement** = SQL templating
   - **Idempotent execution** = `CREATE ... IF NOT EXISTS` (for this training task)

5. For markdown digest idempotency, what should be the unique ID basis?
   **[AI Answer]**
   Use a hash of stable inputs, not auto-increment IDs.

   Common patterns:
   - Document-level: `digest = sha256(source_file + normalized_content)`
   - Chunk-level: `chunk_digest = sha256(source_file + chunk_index + chunk_text)`

   Most practical for this week:
   - `UNIQUE(source_file, chunk_index)` (explicitly called out in the task)
   - Or `UNIQUE(chunk_digest)` as an alternative

6. So this week is mainly writing ingestion scripts to consume provided corpus and store it in DB, right?
   **[AI Answer]**
   Mostly yes, but scope is **ingest + retrieval readiness**:

   1. Build three core tables: `complaints`, `docs`, `doc_embeddings`
   2. Deliver two ingestion scripts:
      - public complaints CSV -> `complaints`
      - markdown corpus -> `docs` + `doc_embeddings`
   3. Implement retrieval methods:
      - `retrieve_docs`
      - `retrieve_complaints`

   So not only loading data, but also making it queryable for the agent.

7. Since vectors are involved, do we need to call embedding in this week?
   **[AI Answer]**
   Yes. This is a core requirement this week.

   You are correct: embedding converts text into vectors for similarity retrieval.

   Minimum expected:
   - Call `LLMService.embed` during markdown ingestion
   - Persist vectors into `doc_embeddings`
   - Keep dimension aligned with `Settings.embedding_dim`

   That is exactly why the `/* EMBEDDING_DIM */` schema placeholder must match runtime configuration.

## Implementation plan

(Drafted; execute only after your approval.)

### Scope and goals

- [ ] Deliver Week-2 minimal RAG foundation in `financial-agent-api`: `complaints`/`docs`/`doc_embeddings` tables, two ingestion scripts, and two `RetrievalService` methods.
- [ ] Keep idempotency and security constraints: parameterized SQL, no secret leakage, and `request_id`-aware logging.
- [ ] Control all raw input locations via environment variables (no hardcoded source directories).

### Directory structure (this phase)

- [ ] API code layout (`codebases/financial-agent-api/`):
  - `src/financial_agent_api/db/schema/0001_create_tables.sql`
  - `src/financial_agent_api/db/schema.py`
  - `src/financial_agent_api/scripts/ingest_public_data.py`
  - `src/financial_agent_api/scripts/embed_starter_docs.py`
  - `src/financial_agent_api/scripts/initialize_data.py`
  - `src/financial_agent_api/services/retrieval_service.py`
- [ ] Local data layout (repository root):
  - `data/complaints/` (CSV input directory)
  - `data/docs/` (markdown corpus directory)
- [ ] Local private config layout (repository root):
  - `.local-config/llm.env` (local model/secret env file, git-ignored)
  - note: `data/` is reserved for committable corpus/data assets only
- [ ] In-container path contract:
  - mount `./data:/app/data:ro`
  - `COMPLAINTS_CSV_PATH=/app/data/complaints/...`
  - `DOCS_SOURCE_DIR=/app/data/docs`

### Phase 1 — Schema and bootstrap

- [ ] Add schema file (pinned as `0001_create_tables.sql`) with:
  - `complaints` (unique on `complaint_id`)
  - `docs` (document/chunk metadata)
  - `doc_embeddings` (`doc_id` FK to `docs.id`, `embedding vector(/* EMBEDDING_DIM */)`)
  - Unique constraint on `(source_file, chunk_index)` (or equivalent idempotent key)
- [ ] Implement/complete `apply_schema`:
  - Replace `/* EMBEDDING_DIM */` with `Settings.embedding_dim` before execution
  - Use `CREATE ... IF NOT EXISTS` for repeat-safe runs

### Phase 2 — Ingestion scripts

- [ ] `ingest_public_data.py`:
  - Read CSV from `COMPLAINTS_CSV_PATH`, normalize, and write to `complaints`
  - Upsert by `complaint_id` for idempotency
  - Use bound params only (no string-built SQL)
- [ ] `embed_starter_docs.py`:
  - Read markdown corpus from `DOCS_SOURCE_DIR`
  - Apply fixed-size chunking (optionally with overlap)
  - Call `LLMService.embed` and write vectors to `doc_embeddings`
  - Keep stable FK linkage to `docs`; avoid duplicate inserts on reruns

### Phase 3 — RetrievalService

- [ ] Add `RetrievalService` wired with `session_factory` and `LLMService` (following existing container pattern).
- [ ] Implement `retrieve_docs`:
  - Embed query
  - Vector similarity search in `doc_embeddings` and join back to `docs`
  - Return Pydantic DTOs (not ORM entities)
- [ ] Implement `retrieve_complaints`:
  - Baseline ILIKE + ORDER BY retrieval
  - Return Pydantic DTOs (not ORM entities)
- [ ] Keep public signatures with `request_id: str | None = None` and existing structured logging contract.

### Phase 4 — Config and wiring

- [ ] Extend `Settings` with Week-2 minimal config (`embedding_model`, `embedding_dim`, DB connection settings).
- [ ] Add and validate raw input path settings:
  - `COMPLAINTS_CSV_PATH`
  - `DOCS_SOURCE_DIR`
- [ ] Register/inject `RetrievalService` via `ServicesContainer` and app startup wiring.
- [ ] Keep `.env.example` aligned with added config (placeholders only).

### Phase 5 — Local container build and initialization

- [ ] Update root `docker-compose.yml` for `financial-agent-api`:
  - define `COMPLAINTS_CSV_PATH` and `DOCS_SOURCE_DIR`
  - point both to in-container `/app/data/...` paths backed by repository-root `./data`
  - add fixed `env_file` path: `./.local-config/llm.env` (for real local LLM credentials/config)
- [ ] Add API container volume mount:
  - `./data:/app/data:ro`
- [ ] Update container startup script/entrypoint:
  - run initialization before serving traffic (`apply_schema` + initial ingestion flow)
  - fail fast if initialization fails (no silent skip)
  - have `start` generate `./.local-config/llm.env` interactively; entrypoint should only consume it and start
- [ ] Update `start` script and `README`:
  - first run (no `./.local-config/llm.env`) must be interactive:
    1. prompt user to choose provider (`ollama` or `openrouter`)
    2. ask provider-specific required values with non-empty validation
       - Ollama: `OLLAMA_BASE_URL`, `OLLAMA_CHAT_MODEL`, `EMBEDDING_MODEL`
       - OpenRouter: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `EMBEDDING_MODEL`
    3. auto-write fixed path values: `COMPLAINTS_CSV_PATH=/app/data/complaints/...`, `DOCS_SOURCE_DIR=/app/data/docs`
    4. persist generated config to `./.local-config/llm.env` and print “saved for reuse”
  - second and subsequent runs (file exists):
    - do not ask any interactive questions
    - print “using existing config”
    - print reset hint: “delete `./.local-config` to reconfigure”
  - README must include sample interaction transcript for first run and second run behavior
  - document reset as directory deletion: `rm -rf ./.local-config`
  - document re-init flow: rerun `start` after deletion
- [ ] Update `.gitignore`:
  - ignore `.local-config/` to prevent committing local secrets

### Phase 6 — Tests and acceptance

- [ ] Add/complete tests for:
  - Schema placeholder substitution and idempotent schema apply
  - Idempotency for both ingestion scripts
  - Explicit failure when required env vars are missing or paths are invalid
  - API container startup via docker-compose can read corpus from `/app/data` and complete initialization
  - `start` interaction behavior: first run prompts, second run no prompts, reset re-enables prompts
  - Return shape and key filtering behavior for both retrieval methods
- [ ] Run and pass existing repo lint, type-check, and tests.

### Risks handled in this implementation

- [ ] Embedding dimension drift: unify schema/runtime on `Settings.embedding_dim`.
- [ ] Duplicate ingestion: `complaint_id` upsert + unique `(source_file, chunk_index)`.
- [ ] SQL injection: parameterized SQL only (`text()` + bound params).
- [ ] Logging safety: no key logging, prompt truncation per existing policy.

### Current convergence plan (updated 2026-07-16)

- [ ] P0. Close initialization observability gaps: explicitly enable logging in `initialize_data` flow and print phase summaries (schema/complaints/docs-embedding), with stage context on failures.
- [ ] P0. Align verification expectations: keep complaints deduplicated by `complaint_id` (1000 raw rows -> 400 unique IDs) as the current contract, and document this in README/acceptance notes.
- [ ] P1. Fix docs ingestion coverage: support both `.md` and `.txt` under `DOCS_SOURCE_DIR` so starter corpus is ingested and embedded.
- [ ] P1. Complete `start` interaction: explicitly prompt and persist `EMBEDDING_DIM` (with model-inferred default allowed).
- [ ] P1. Solidify acceptance checklist: provide post-compose SQL checks for `complaints_count`, `docs_count`, `doc_embeddings_count`, `vector_dims`, and `digest` completeness.
