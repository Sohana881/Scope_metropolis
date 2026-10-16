
from typing import Any

from services.execution_service import get_receipt
from services.receipt_signing import verify_receipt_signature


def verify_receipt(submitted_receipt: dict[str, Any]) -> dict[str, Any]:
    """Verify receipt fields and the receipt's HMAC signature."""
    receipt_id = submitted_receipt.get("receipt_id")

    if not receipt_id:
        return {
            "verified": False,
            "reason": "RECEIPT_ID_REQUIRED",
        }

    stored_receipt = get_receipt(receipt_id)

    if stored_receipt is None:
        return {
            "verified": False,
            "reason": "RECEIPT_NOT_FOUND",
        }

    # Compare the receipt fields first so a changed field is identified.
    all_fields = set(submitted_receipt) | set(stored_receipt)

    for field in sorted(all_fields):
        if field == "signature":
            continue

        if submitted_receipt.get(field) != stored_receipt.get(field):
            return {
                "verified": False,
                "reason": "RECEIPT_FIELD_MISMATCH",
                "field": field,
            }

    # Require a valid signature even if the submitted fields match.
    if not verify_receipt_signature(submitted_receipt):
        return {
            "verified": False,
            "reason": "INVALID_RECEIPT_SIGNATURE",
        }

    if submitted_receipt.get("signature") != stored_receipt.get("signature"):
        return {
            "verified": False,
            "reason": "INVALID_RECEIPT_SIGNATURE",
        }

    return {
        "verified": True,
        "reason": "RECEIPT_MATCHES_STORED_RECORD",
        "receipt_id": receipt_id,
    }
