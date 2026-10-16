
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def create_receipt():
    action = {
        "request_id": "receipt-test-001",
        "chain_id": 10143,
        "action_kind": "transfer",
        "target_address": "0x1234567890123456789012345678901234567890",
        "amount": 100,
        "unlimited_approval": False,
        "known_contract": True,
        "requires_user_consent": False,
    }

    evaluation = client.post("/v1/actions/evaluate", json=action)
    assert evaluation.status_code == 200
    assert evaluation.json()["decision"] == "ALLOW"

    execution = client.post("/v1/actions/execute", json=action)
    assert execution.status_code == 200

    return execution.json()["receipt"]


def test_valid_receipt_verifies():
    receipt = create_receipt()

    response = client.post("/v1/actions/verify", json=receipt)

    assert response.status_code == 200
    assert response.json()["verified"] is True
    assert response.json()["reason"] == "RECEIPT_MATCHES_STORED_RECORD"


def test_tampered_receipt_is_rejected():
    receipt = create_receipt()
    tampered = {
        **receipt,
        "action_hash": "0x" + "0" * 64,
    }

    response = client.post("/v1/actions/verify", json=tampered)

    assert response.status_code == 200
    assert response.json()["verified"] is False
    assert response.json()["reason"] == "RECEIPT_FIELD_MISMATCH"
    assert response.json()["field"] == "action_hash"


def test_unknown_receipt_does_not_verify():
    response = client.post(
        "/v1/actions/verify",
        json={
            "receipt_id": "receipt-does-not-exist",
            "action_hash": "0x" + "0" * 64,
            "decision": "ALLOW",
            "execution_status": "SIMULATED_SUCCESS",
            "issued_at": "2026-01-01T00:00:00+00:00",
        },
    )

    assert response.status_code == 200
    assert response.json()["verified"] is False
    assert response.json()["reason"] == "RECEIPT_NOT_FOUND"
