from __future__ import annotations

import asyncio
import sys
import traceback
from pathlib import Path

from ..core.config import get_settings
from ..core.database import create_engine_from_settings, create_session_factory
from ..db.schema import apply_schema
from .embed_starter_docs import run as run_docs_embedding
from .ingest_public_data import run as run_public_ingestion


def _root_cause(exc: BaseException) -> BaseException:
    cause = exc
    while cause.__cause__ is not None:
        cause = cause.__cause__
    return cause


def run() -> None:
    settings = get_settings()
    schema_path = Path(__file__).resolve().parents[1] / "db" / "schema" / "0001_create_tables.sql"

    print("[init] Step 1/3: applying schema...")
    try:
        engine = create_engine_from_settings(settings)
        session_factory = create_session_factory(engine)
        apply_schema(session_factory, schema_path=schema_path, embedding_dim=settings.embedding_dim)
    except Exception as exc:
        raise RuntimeError("Initialization failed during schema setup.") from exc
    finally:
        if "engine" in locals():
            engine.dispose()

    print("[init] Step 2/3: ingesting complaints CSV...")
    try:
        ingestion_summary = run_public_ingestion()
    except Exception as exc:
        raise RuntimeError("Initialization failed during complaints ingestion.") from exc
    print(
        f"[init] complaints ingestion done: processed={ingestion_summary['processed']} "
        f"skipped={ingestion_summary['skipped']}"
    )

    print("[init] Step 3/3: embedding starter docs...")
    try:
        embedding_summary = asyncio.run(run_docs_embedding())
    except Exception as exc:
        raise RuntimeError("Initialization failed during docs embedding.") from exc
    print(
        f"[init] docs embedding done: documents={embedding_summary['documents']} "
        f"chunks={embedding_summary['chunks']}"
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # propagate non-zero exit with clearer phase context
        root = _root_cause(exc)
        print(f"[init] ERROR: {exc}", file=sys.stderr)
        print(
            f"[init] Root cause: {type(root).__name__}: {root}",
            file=sys.stderr,
        )
        traceback.print_exc()
        sys.exit(1)
