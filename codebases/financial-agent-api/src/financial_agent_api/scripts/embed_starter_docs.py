from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from sqlalchemy import text

from ..core.config import get_settings
from ..core.database import create_engine_from_settings, create_session_factory, to_pgvector_literal
from ..db.schema import apply_schema
from ..services.llm_client import LLMHTTPClient
from ..services.llm_service import LLMService

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
SUPPORTED_DOC_EXTENSIONS = (".md", ".txt")


def _resolve_docs_dir(path: Path) -> Path:
    if not path.exists() or not path.is_dir():
        raise ValueError(f"DOCS_SOURCE_DIR does not exist or is not a directory: {path}")
    return path


def _chunk_text(content: str, *, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if not content:
        return []
    chunks: list[str] = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(content), step):
        chunk = content[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(content):
            break
    return chunks


def _digest(source_file: str, chunk_index: int, chunk_text: str) -> str:
    payload = f"{source_file}\n{chunk_index}\n{chunk_text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _resolve_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
    return fallback


def _collect_doc_files(docs_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in docs_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_DOC_EXTENSIONS
    )


async def run() -> dict[str, int]:
    settings = get_settings()
    docs_dir = _resolve_docs_dir(settings.require_docs_source_dir())
    schema_path = Path(__file__).resolve().parents[1] / "db" / "schema" / "0001_create_tables.sql"

    if settings.llm_provider == "openrouter":
        http_client = LLMHTTPClient(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
        )
    else:
        http_client = LLMHTTPClient(base_url=settings.ollama_base_url)
    llm = LLMService(settings=settings, http_client=http_client)

    engine = create_engine_from_settings(settings)
    session_factory = create_session_factory(engine)
    apply_schema(session_factory, schema_path=schema_path, embedding_dim=settings.embedding_dim)

    upsert_doc_sql = text(
        """
        INSERT INTO docs (source_file, chunk_index, title, content, digest)
        VALUES (:source_file, :chunk_index, :title, :content, :digest)
        ON CONFLICT (source_file, chunk_index)
        DO UPDATE SET
          title = EXCLUDED.title,
          content = EXCLUDED.content,
          digest = EXCLUDED.digest,
          updated_at = NOW()
        RETURNING id
        """
    )
    upsert_embedding_sql = text(
        """
        INSERT INTO doc_embeddings (doc_id, embedding)
        VALUES (:doc_id, CAST(:embedding AS vector))
        ON CONFLICT (doc_id)
        DO UPDATE SET embedding = EXCLUDED.embedding
        """
    )

    processed_docs = 0
    processed_chunks = 0
    source_files = _collect_doc_files(docs_dir)

    try:
        with session_factory.begin() as session:
            for source_path in source_files:
                raw = source_path.read_text(encoding="utf-8")
                source_file = str(source_path.relative_to(docs_dir))
                title = _resolve_title(raw, source_path.stem)
                for chunk_index, chunk in enumerate(_chunk_text(raw)):
                    embedding = await llm.embed(chunk)
                    doc_id = session.execute(
                        upsert_doc_sql,
                        {
                            "source_file": source_file,
                            "chunk_index": chunk_index,
                            "title": title,
                            "content": chunk,
                            "digest": _digest(source_file, chunk_index, chunk),
                        },
                    ).scalar_one()
                    session.execute(
                        upsert_embedding_sql,
                        {"doc_id": doc_id, "embedding": to_pgvector_literal(embedding)},
                    )
                    processed_chunks += 1
                processed_docs += 1
    finally:
        await http_client.close()
        engine.dispose()

    return {"documents": processed_docs, "chunks": processed_chunks}


if __name__ == "__main__":
    summary = asyncio.run(run())
    print(f"embed_starter_docs completed: documents={summary['documents']} chunks={summary['chunks']}")
