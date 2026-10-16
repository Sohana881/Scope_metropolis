
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProposedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=100)
    chain_id: int = Field(gt=0)

    action_kind: Literal[
        "transfer",
        "token_approval",
        "contract_call",
    ]

    target_address: str = Field(min_length=1)
    amount: float = Field(ge=0)

    unlimited_approval: bool = False
    known_contract: bool = True
    requires_user_consent: bool = False


class EvaluationResponse(BaseModel):
    request_id: str
    action_hash: str

    decision: Literal[
        "ALLOW",
        "DENY",
        "REQUIRE_CONSENT",
    ]

    risk_score: int = Field(ge=0, le=100)
    risk_band: Literal["LOW", "MEDIUM", "HIGH"]
    reasons: list[str]
