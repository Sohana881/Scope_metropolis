
import sqlite3
from uuid import uuid4

from fastapi.testclient import TestClient

from main import app
from services.database import (
    DB_PATH,
    get_signature,
)
from services.execution_service import get_receipt
from services.receipt_signing import verify_receipt_signature


def sample_action(**overrides):
    action = {
        "request_id": "receipt-atomicity-test",
        "chain_id": 10143,
        "action_kind": "transfer",
        "target_address": "0x1234567890123456789012345678901234567890",
        "amount": 25,
        "unlimited_approval": False,
        "known_contract": True,
        "requires_user_consent": False,
    }
    action.update(overrides)
    return action


def test_receipt_and_signature_both_rollback_on_signature_failure():
    """A failed signature insert must also roll back the receipt insert."""
    action = sample_action()
    receipt_id = str(uuid4())

    with TestClient(app) as client:
        evaluation = client.post("/v1/actions/evaluate", json=action)

    assert evaluation.status_code == 200
    assert evaluation.json()["decision"] == "ALLOW"

    from services.action_hash import calculate_action_hash
    from services.database import (
        execute_action_atomically,
        get_evaluated_action,
        get_receipt as get_database_receipt,
    )
    from services.receipt_signing import sign_receipt
    from services.schemas import ProposedAction

    action_model = ProposedAction.model_validate(action)
    action_hash = calculate_action_hash(action_model)
    stored = get_evaluated_action(action_hash)

    assert stored is not None

    receipt = {
        "receipt_id": receipt_id,
        "action_hash": action_hash,
        "decision": stored["decision"],
        "execution_status": "SIMULATED_SUCCESS",
        "issued_at": "2026-10-13T12:00:00+00:00",
    }
    signature = sign_receipt(receipt)

    with sqlite3.connect(DB_PATH, timeout=10) as connection:
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS test_fail_signature_insert
            BEFORE INSERT ON receipt_signatures
            BEGIN
                SELECT RAISE(ABORT, 'simulated signature insertion failure');
            END
            """
        )

    try:
        try:
            execute_action_atomically(
                action_hash=action_hash,
                action_json=action_model.model_dump(mode="json"),
                consent_challenge_id=None,
                receipt=receipt,
                signature=signature,
            )
            assert False, "Expected the signature insert to fail"
        except sqlite3.IntegrityError as exc:
            assert "simulated signature insertion failure" in str(exc)

        assert get_database_receipt(receipt_id) is None
        assert get_signature(receipt_id) is None

    finally:
        with sqlite3.connect(DB_PATH, timeout=10) as connection:
            connection.execute(
                "DROP TRIGGER IF EXISTS test_fail_signature_insert"
            )


def test_signed_receipt_persists_and_verifies_after_database_reopen():
    """Verify the complete receipt survives fresh database connections."""
    action = sample_action(request_id="receipt-persistence-test")

    with TestClient(app) as client:
        evaluation = client.post("/v1/actions/evaluate", json=action)
        assert evaluation.status_code == 200

        execution = client.post("/v1/actions/execute", json=action)
        assert execution.status_code == 200

        result = execution.json()
        assert result["status"] == "SIMULATED_SUCCESS"

        receipt = result["receipt"]
        assert receipt["signature"].startswith("hmac-sha256:")

    receipt_id = receipt["receipt_id"]

    # Confirm the receipt exists using a newly opened SQLite connection.
    with sqlite3.connect(DB_PATH, timeout=10) as connection:
        row = connection.execute(
            "SELECT receipt_id FROM receipts WHERE receipt_id = ?",
            (receipt_id,),
        ).fetchone()
        assert row is not None

    # Use the same service the API uses so the signature is attached.
    stored_receipt = get_receipt(receipt_id)
    stored_signature = get_signature(receipt_id)

    assert stored_receipt is not None
    assert stored_signature == receipt["signature"]
    assert stored_receipt["signature"] == stored_signature
    assert stored_receipt["action_hash"] == receipt["action_hash"]

    assert verify_receipt_signature(stored_receipt) is True

    # Confirm the public verification endpoint accepts the persisted receipt.
    with TestClient(app) as client:
        verification = client.post(
            "/v1/actions/verify",
            json=stored_receipt,
        )

    assert verification.status_code == 200
    assert verification.json()["verified"] is True
    assert (
        verification.json()["reason"]
        == "RECEIPT_MATCHES_STORED_RECORD"
    )
