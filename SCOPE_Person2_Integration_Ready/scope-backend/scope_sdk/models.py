
"""Typed request and response models for the SCOPE SDK."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProposedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(min_length=1, max_length=100)
    chain_id: int = Field(gt=0)
    action_kind: Literal["transfer", "token_approval", "contract_call"]
    target_address: str = Field(min_length=1)
    amount: float = Field(ge=0)
    unlimited_approval: bool = False
    known_contract: bool = True
    requires_user_consent: bool = False


class ActionEvaluation(BaseModel):
    model_config = ConfigDict(extra="allow")

    request_id: str
    action_hash: str
    decision: Literal["ALLOW", "DENY", "REQUIRE_CONSENT"]
    risk_score: int = Field(ge=0, le=100)
    risk_band: Literal["LOW", "MEDIUM", "HIGH"]
    reasons: list[str]


class ConsentChallenge(BaseModel):
    model_config = ConfigDict(extra="allow")

    challenge_id: str
    action_hash: str
    status: str
    message: str | None = None


class ConsentVerification(BaseModel):
    model_config = ConfigDict(extra="allow")

    verified: bool
    challenge_id: str | None = None
    action_hash: str | None = None
    reason: str


class Receipt(BaseModel):
    model_config = ConfigDict(extra="allow")

    receipt_id: str
    action_hash: str
    decision: str
    execution_status: str
    issued_at: str
    signature: str | None = None


class ReceiptVerification(BaseModel):
    model_config = ConfigDict(extra="allow")

    verified: bool
    reason: str
    receipt_id: str | None = None
    field: str | None = None


JSONData = dict[str, Any]



class DecodeResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    supported: bool
    chain_id: int
    target_address: str
    selector: str | None = None
    method: str | None = None
    decoded: dict[str, str] = Field(default_factory=dict)
    reason: str
