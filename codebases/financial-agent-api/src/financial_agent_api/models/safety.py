from __future__ import annotations
from typing import Literal
from pydantic import BaseModel


class SafetyDecision(BaseModel):
    allowed: bool
    category: Literal[
        "allowed_public_information",
        "personalised_financial_advice",
        "pii_exposure_or_inference",
        "tos_evasion",
        "unsupported_guarantees",
    ]
    reason: str
    user_message: str
