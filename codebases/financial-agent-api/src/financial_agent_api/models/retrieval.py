from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class DocumentChunk(BaseModel):
    doc_id: int
    source_file: str
    chunk_index: int
    content: str
    similarity: float


class ComplaintRow(BaseModel):
    complaint_id: str
    date_received: date | None = None
    product: str | None = None
    issue: str | None = None
    company: str | None = None
    state: str | None = None
    submitted_via: str | None = None
    narrative: str | None = None
