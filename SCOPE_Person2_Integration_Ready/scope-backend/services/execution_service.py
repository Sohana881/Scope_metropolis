
from datetime import datetime, timezone
from uuid import uuid4

from services.action_hash import calculate_action_hash
from services.schemas import ProposedAction
from services.policy_engine import evaluate_policy
from services.database import (
    save_evaluated_action,
    execute_action_atomically,
    get_receipt as get_stored_receipt,
    get_evaluated_action,
    get_signature,
)
from services.receipt_signing import sign_receipt


def evaluate_and_record(action: ProposedAction) -> dict:
    """Evaluate an action and persist its decision."""
    result = evaluate_policy(action)

    save_evaluated_action(
        action_hash=result["action_hash"],
        action_json=action.model_dump(mode="json"),
        decision=result["decision"],
        request_id=action.request_id,
    )

    return result


def execute_simulated_action(
    action: ProposedAction,
    consent_challenge_id: str | None = None,
) -> dict:
    """Execute a simulated action and atomically persist its signed receipt."""
    action_hash = calculate_action_hash(action)
    record = get_evaluated_action(action_hash)

    if record is None:
        return {
            "status": "REJECTED",
            "reason": "ACTION_NOT_EVALUATED",
            "action_hash": action_hash,
        }

    receipt = {
        "receipt_id": str(uuid4()),
        "action_hash": action_hash,
        "decision": record["decision"],
        "execution_status": "SIMULATED_SUCCESS",
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }

    # Sign the receipt before writing. The receipt and signature will be
    # inserted together by execute_action_atomically().
    signature = sign_receipt(receipt)

    return execute_action_atomically(
        action_hash=action_hash,
        action_json=action.model_dump(mode="json"),
        consent_challenge_id=consent_challenge_id,
        receipt=receipt,
        signature=signature,
    )


def get_receipt(receipt_id: str) -> dict | None:
    """Retrieve a stored receipt with its signature."""
    receipt = get_stored_receipt(receipt_id)

    if receipt is None:
        return None

    signature = get_signature(receipt_id)

    if signature is not None:
        receipt["signature"] = signature

    return receipt
