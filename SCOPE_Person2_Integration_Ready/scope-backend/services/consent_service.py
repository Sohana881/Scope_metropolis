
from uuid import uuid4

from services.action_hash import calculate_action_hash
from services.schemas import ProposedAction
from services.database import (
    save_consent_challenge,
    get_consent_challenge,
    verify_pending_challenge,
)


def create_consent_challenge(action: ProposedAction) -> dict:
    action_hash = calculate_action_hash(action)
    challenge_id = str(uuid4())

    challenge = {
        "challenge_id": challenge_id,
        "action_hash": action_hash,
        "status": "PENDING",
        "consent_granted": False,
    }

    save_consent_challenge(challenge)

    return {
        "challenge_id": challenge_id,
        "action_hash": action_hash,
        "status": "PENDING",
        "message": "Explicit user confirmation is required.",
    }


def get_challenge(challenge_id: str) -> dict | None:
    return get_consent_challenge(challenge_id)


def consume_challenge(challenge_id: str) -> None:
    """Retained for compatibility with existing callers."""
    from services.database import update_consent_challenge

    update_consent_challenge(
        challenge_id=challenge_id,
        status="USED",
        consent_granted=True,
    )


def verify_consent(
    challenge_id: str,
    action_hash: str,
    consent_granted: bool,
) -> dict:
    return verify_pending_challenge(
        challenge_id=challenge_id,
        action_hash=action_hash,
        consent_granted=consent_granted,
    )
