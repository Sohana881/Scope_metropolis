from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from pydantic import BaseModel, ConfigDict

from services.schemas import ProposedAction, EvaluationResponse
from services.action_hash import calculate_action_hash
from services.database import get_evaluated_action
from services.execution_service import (
    evaluate_and_record,
    execute_simulated_action,
    get_receipt,
)
from services.consent_service import create_consent_challenge, verify_consent
from services.receipt_service import verify_receipt


app = FastAPI(
    title="SCOPE Backend",
    description="AI agent action security and policy API",
    version="1.0.0",
)

_default_origins = (
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:3001,http://localhost:3002,"
    "http://localhost:5173,http://127.0.0.1:5173"
)
_allowed_origins = [
    origin.strip()
    for origin in os.getenv("SCOPE_CORS_ORIGINS", _default_origins).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Request models
# --------------------------------------------------

class ConsentVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_id: str
    action_hash: str
    consent_granted: bool


class ExecuteActionRequest(ProposedAction):
    consent_challenge_id: str | None = None


class ReceiptVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: str
    action_hash: str
    decision: str
    execution_status: str
    issued_at: str
    signature: str | None = None


# --------------------------------------------------
# Response models
# --------------------------------------------------

class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str


class ConsentChallengeResponse(BaseModel):
    challenge_id: str
    action_hash: str
    status: Literal["PENDING"]
    message: str


class ConsentVerificationResponse(BaseModel):
    verified: bool
    challenge_id: str | None = None
    action_hash: str | None = None
    reason: str | None = None


class ReceiptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: str
    action_hash: str
    decision: str
    execution_status: str
    issued_at: str
    signature: str | None = None


class ExecutionResponse(BaseModel):
    status: str
    reason: str | None = None
    action_hash: str | None = None
    receipt: ReceiptResponse | None = None


class ReceiptVerificationResponse(BaseModel):
    verified: bool
    reason: str
    receipt_id: str | None = None
    field: str | None = None


# --------------------------------------------------
# Minimal transaction/effect decoder
# --------------------------------------------------

class DecodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chain_id: int
    target_address: str
    calldata: str = "0x"
    value_wei: str = "0"


class DecodeResponse(BaseModel):
    supported: bool
    chain_id: int
    target_address: str
    selector: str | None = None
    method: str | None = None
    decoded: dict[str, str] = {}
    reason: str


def _decode_word_address(word: str) -> str:
    return "0x" + word[-40:].lower()


@app.post("/v1/actions/decode", response_model=DecodeResponse)
def decode_action(request: DecodeRequest):
    """Decode common ERC-20 selectors; unsupported calls are never labelled safe."""
    calldata = request.calldata.strip().lower()
    if not calldata.startswith("0x") or len(calldata) % 2 != 0:
        raise HTTPException(status_code=422, detail="calldata must be 0x-prefixed even-length hex.")
    try:
        bytes.fromhex(calldata[2:])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="calldata must contain hexadecimal bytes.") from exc

    raw = calldata[2:]
    selector = "0x" + raw[:8] if len(raw) >= 8 else None
    words = [raw[i:i + 64] for i in range(8, len(raw), 64)] if len(raw) >= 8 else []
    decoded: dict[str, str] = {}
    method = None
    supported = False
    reason = "ACTION_UNSUPPORTED"

    if selector == "0xa9059cbb" and len(words) >= 2 and all(len(w) == 64 for w in words[:2]):
        method = "transfer"
        decoded = {"recipient": _decode_word_address(words[0]), "amount_raw": str(int(words[1], 16))}
        supported, reason = True, "ERC20_TRANSFER_DECODED"
    elif selector == "0x095ea7b3" and len(words) >= 2 and all(len(w) == 64 for w in words[:2]):
        method = "approve"
        amount = int(words[1], 16)
        decoded = {"spender": _decode_word_address(words[0]), "amount_raw": str(amount)}
        if amount == 2**256 - 1:
            decoded["unlimited_approval"] = "true"
        supported, reason = True, "ERC20_APPROVAL_DECODED"
    elif selector == "0x23b872dd" and len(words) >= 3 and all(len(w) == 64 for w in words[:3]):
        method = "transferFrom"
        decoded = {
            "owner": _decode_word_address(words[0]),
            "recipient": _decode_word_address(words[1]),
            "amount_raw": str(int(words[2], 16)),
        }
        supported, reason = True, "ERC20_TRANSFER_FROM_DECODED"

    return {
        "supported": supported,
        "chain_id": request.chain_id,
        "target_address": request.target_address,
        "selector": selector,
        "method": method,
        "decoded": decoded,
        "reason": reason,
    }


# --------------------------------------------------
# Health
# --------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health_check():
    return {
        "status": "ok",
        "service": "scope-backend",
    }


# --------------------------------------------------
# Action evaluation
# --------------------------------------------------

@app.post(
    "/v1/actions/evaluate",
    response_model=EvaluationResponse,
)
def evaluate_action(action: ProposedAction):
    return evaluate_and_record(action)


# --------------------------------------------------
# Consent
# --------------------------------------------------

@app.post(
    "/v1/consent/challenge",
    response_model=ConsentChallengeResponse,
)
def consent_challenge(action: ProposedAction):
    action_hash = calculate_action_hash(action)
    record = get_evaluated_action(action_hash)

    if record is None:
        raise HTTPException(
            status_code=409,
            detail="Evaluate this action before requesting consent.",
        )

    if record["decision"] != "REQUIRE_CONSENT":
        raise HTTPException(
            status_code=409,
            detail="This action does not require consent.",
        )

    return create_consent_challenge(action)


@app.post(
    "/v1/consent/verify",
    response_model=ConsentVerificationResponse,
)
def consent_verify(request: ConsentVerificationRequest):
    result = verify_consent(
        challenge_id=request.challenge_id,
        action_hash=request.action_hash,
        consent_granted=request.consent_granted,
    )

    if not result["verified"]:
        raise HTTPException(
            status_code=400,
            detail=result,
        )

    if get_evaluated_action(request.action_hash) is None:
        raise HTTPException(
            status_code=404,
            detail="Evaluated action not found.",
        )

    return result


# --------------------------------------------------
# Simulated execution
# --------------------------------------------------

@app.post(
    "/v1/actions/execute",
    response_model=ExecutionResponse,
)
def execute_action(request: ExecuteActionRequest):
    action_data = request.model_dump(
        exclude={"consent_challenge_id"}
    )
    action = ProposedAction.model_validate(action_data)

    return execute_simulated_action(
        action,
        consent_challenge_id=request.consent_challenge_id,
    )


# --------------------------------------------------
# Receipt retrieval
# --------------------------------------------------

@app.get(
    "/v1/receipts/{receipt_id}",
    response_model=ReceiptResponse,
)
def read_receipt(receipt_id: str):
    receipt = get_receipt(receipt_id)

    if receipt is None:
        raise HTTPException(
            status_code=404,
            detail="Receipt not found",
        )

    return receipt


# --------------------------------------------------
# Receipt verification
# --------------------------------------------------

@app.post(
    "/v1/actions/verify",
    response_model=ReceiptVerificationResponse,
)
def verify_action_receipt(
    request: ReceiptVerificationRequest,
):
    return verify_receipt(request.model_dump())
