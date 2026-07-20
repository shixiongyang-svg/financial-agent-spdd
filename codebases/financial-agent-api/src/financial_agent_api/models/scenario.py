from __future__ import annotations
from pydantic import BaseModel


class Scenario(BaseModel):
    product_type: str
    issue_type: str
    amount: float | None = None
    jurisdiction: str | None = None
    confidence: float
