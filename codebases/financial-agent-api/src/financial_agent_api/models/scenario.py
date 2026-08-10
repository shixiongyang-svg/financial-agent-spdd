from __future__ import annotations
from pydantic import BaseModel


class Scenario(BaseModel):
    """Scenario extracted from user query for complaints & docs filtering.

    Note: 本实现仅包含三字段（product_type / issue_type / confidence），
    暂不实现 amount / jurisdiction（见 Task 4 决议 1）。
    未来如需扩展可单独提案。
    """
    product_type: str | None = None
    issue_type: str | None = None
    confidence: float
