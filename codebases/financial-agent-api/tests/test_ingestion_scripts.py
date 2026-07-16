from __future__ import annotations

from pathlib import Path

import pytest

from financial_agent_api.scripts.embed_starter_docs import _collect_doc_files, _resolve_docs_dir
from financial_agent_api.scripts.ingest_public_data import _resolve_csv_path


def test_resolve_csv_path_requires_existing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"
    with pytest.raises(ValueError, match="COMPLAINTS_CSV_PATH"):
        _resolve_csv_path(missing)


def test_resolve_docs_dir_requires_existing_directory(tmp_path: Path) -> None:
    missing = tmp_path / "docs"
    with pytest.raises(ValueError, match="DOCS_SOURCE_DIR"):
        _resolve_docs_dir(missing)


def test_collect_doc_files_supports_md_and_txt(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "a.md").write_text("# title", encoding="utf-8")
    (docs_dir / "b.txt").write_text("plain text", encoding="utf-8")
    (docs_dir / "c.csv").write_text("ignore,me", encoding="utf-8")

    files = _collect_doc_files(docs_dir)
    assert [path.name for path in files] == ["a.md", "b.txt"]
