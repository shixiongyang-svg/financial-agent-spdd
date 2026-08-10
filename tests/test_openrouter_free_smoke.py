from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.openrouter_free_smoke import (
    ordered_completion_models,
    ordered_embedding_models,
    parse_decimal,
    prioritized_candidates,
    read_optional_env_value,
)


def test_parse_decimal_handles_strings_and_numbers() -> None:
    assert parse_decimal("0.001") is not None
    assert parse_decimal(0.002) is not None
    assert parse_decimal(None) is None


def test_ordered_completion_models_sorts_by_prompt_plus_completion() -> None:
    catalog = [
        {"id": "expensive", "pricing": {"prompt": "0.0002", "completion": "0.0003"}},
        {"id": "cheap", "pricing": {"prompt": "0.0001", "completion": "0.0001"}},
        {"id": "free:free", "pricing": {"prompt": "0", "completion": "0"}},
    ]

    assert ordered_completion_models(catalog) == ["cheap", "expensive"]


def test_ordered_embedding_models_sorts_by_prompt_price() -> None:
    catalog = [
        {"id": "emb-expensive", "pricing": {"prompt": "0.0003"}},
        {"id": "emb-cheap", "pricing": {"prompt": "0.0001"}},
        {"id": "emb-free:free", "pricing": {"prompt": "0"}},
    ]

    assert ordered_embedding_models(catalog) == ["emb-cheap", "emb-expensive"]


def test_read_optional_env_value_returns_none_for_missing_file(tmp_path: Path) -> None:
    assert read_optional_env_value(tmp_path / "missing.env", "OPENROUTER_MODEL") is None


def test_read_optional_env_value_reads_present_key(tmp_path: Path) -> None:
    env_file = tmp_path / "llm.env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "export OPENROUTER_MODEL=inclusionai/ling-2.6-flash",
                "EMBEDDING_MODEL='perplexity/pplx-embed-v1-0.6b'",
            ]
        ),
        encoding="utf-8",
    )

    assert read_optional_env_value(env_file, "OPENROUTER_MODEL") == "inclusionai/ling-2.6-flash"
    assert read_optional_env_value(env_file, "EMBEDDING_MODEL") == "perplexity/pplx-embed-v1-0.6b"
    assert read_optional_env_value(env_file, "EMBEDDING_DIM") is None


def test_prioritized_candidates_skips_failed_preferred_model() -> None:
    assert prioritized_candidates(
        "preferred",
        ["preferred", "fallback-a", "fallback-b"],
        skip_models={"preferred"},
    ) == ["fallback-a", "fallback-b"]
