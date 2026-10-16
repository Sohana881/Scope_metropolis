
import hashlib
import hmac
import json
import os
from typing import Any


def _get_secret() -> bytes:
    """
    Get the receipt-signing secret from the environment.

    The fallback is only for local development. Production must
    configure a strong secret outside the source code.
    """
    secret = os.environ.get("SCOPE_RECEIPT_SECRET")

    if not secret:
        secret = "LOCAL-DEVELOPMENT-ONLY-CHANGE-ME"

    if secret == "LOCAL-DEVELOPMENT-ONLY-CHANGE-ME":
        if os.environ.get("SCOPE_ENV", "").lower() == "production":
            raise RuntimeError(
                "A secure SCOPE_RECEIPT_SECRET is required in production."
            )

    return secret.encode("utf-8")


def canonical_receipt_json(receipt: dict[str, Any]) -> bytes:
    """Serialize receipt fields consistently before signing."""
    payload = {
        key: value
        for key, value in receipt.items()
        if key != "signature"
    }

    canonical_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )

    return canonical_json.encode("utf-8")


def sign_receipt(receipt: dict[str, Any]) -> str:
    """Return an HMAC-SHA256 signature for a receipt."""
    signature = hmac.new(
        _get_secret(),
        canonical_receipt_json(receipt),
        hashlib.sha256,
    ).hexdigest()

    return "hmac-sha256:" + signature


def verify_receipt_signature(receipt: dict[str, Any]) -> bool:
    """Verify the signature included in a receipt."""
    supplied_signature = receipt.get("signature")

    if not isinstance(supplied_signature, str):
        return False

    expected_signature = sign_receipt(receipt)

    return hmac.compare_digest(
        supplied_signature,
        expected_signature,
    )
