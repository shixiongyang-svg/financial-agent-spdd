from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import text

from ..core.config import get_settings
from ..core.database import create_engine_from_settings, create_session_factory
from ..db.schema import apply_schema


def _pick(row: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value:
            stripped = value.strip()
            if stripped:
                return stripped
    return None


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _resolve_csv_path(path: Path) -> Path:
    if not path.exists() or not path.is_file():
        raise ValueError(f"COMPLAINTS_CSV_PATH does not exist or is not a file: {path}")
    return path


def run() -> dict[str, int]:
    settings = get_settings()
    csv_path = _resolve_csv_path(settings.require_complaints_csv_path())
    schema_path = Path(__file__).resolve().parents[1] / "db" / "schema" / "0001_create_tables.sql"

    engine = create_engine_from_settings(settings)
    session_factory = create_session_factory(engine)
    apply_schema(session_factory, schema_path=schema_path, embedding_dim=settings.embedding_dim)

    upsert_sql = text(
        """
        INSERT INTO complaints (
          complaint_id,
          date_received,
          product,
          issue,
          company,
          state,
          submitted_via,
          narrative
        ) VALUES (
          :complaint_id,
          :date_received,
          :product,
          :issue,
          :company,
          :state,
          :submitted_via,
          :narrative
        )
        ON CONFLICT (complaint_id)
        DO UPDATE SET
          date_received = EXCLUDED.date_received,
          product = EXCLUDED.product,
          issue = EXCLUDED.issue,
          company = EXCLUDED.company,
          state = EXCLUDED.state,
          submitted_via = EXCLUDED.submitted_via,
          narrative = EXCLUDED.narrative,
          updated_at = NOW()
        """
    )

    processed = 0
    skipped = 0
    with csv_path.open("r", encoding="utf-8", newline="") as handle, session_factory.begin() as session:
        reader = csv.DictReader(handle)
        for row in reader:
            complaint_id = _pick(row, "Complaint ID", "complaint_id")
            if not complaint_id:
                skipped += 1
                continue

            params = {
                "complaint_id": complaint_id,
                "date_received": _parse_date(_pick(row, "Date received", "date_received")),
                "product": _pick(row, "Product", "product"),
                "issue": _pick(row, "Issue", "issue"),
                "company": _pick(row, "Company", "company"),
                "state": _pick(row, "State", "state"),
                "submitted_via": _pick(row, "Submitted via", "submitted_via"),
                "narrative": _pick(row, "Consumer complaint narrative", "narrative"),
            }
            session.execute(upsert_sql, params)
            processed += 1

    engine.dispose()
    return {"processed": processed, "skipped": skipped}


if __name__ == "__main__":
    summary = run()
    print(f"ingest_public_data completed: processed={summary['processed']} skipped={summary['skipped']}")
