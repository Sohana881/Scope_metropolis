
import hashlib
import json

from services.schemas import ProposedAction


def calculate_action_hash(action: ProposedAction) -> str:
    """Return a deterministic SHA-256 hash of a validated action."""

    payload = action.model_dump(mode="json")

    canonical_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )

    digest = hashlib.sha256(
        canonical_json.encode("utf-8")
    ).hexdigest()

    return f"0x{digest}"
