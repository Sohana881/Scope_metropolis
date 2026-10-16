from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_unlimited_token_approval_is_denied():
    action = {
        "request_id": "security-unlimited-001",
        "chain_id": 1,
        "action_kind": "token_approval",
        "target_address": "0x1234567890abcdef",
        "amount": 100,
        "unlimited_approval": True,
        "known_contract": True,
        "requires_user_consent": False,
    }

    evaluation = client.post("/v1/actions/evaluate", json=action)
    assert evaluation.status_code == 200
    assert evaluation.json()["decision"] == "DENY"
    assert evaluation.json()["risk_band"] == "HIGH"

    execution = client.post("/v1/actions/execute", json=action)
    assert execution.status_code == 200
    assert execution.json()["status"] == "REJECTED"


def test_high_value_action_above_5000_is_denied():
    action = {
        "request_id": "security-high-value-001",
        "chain_id": 1,
        "action_kind": "transfer",
        "target_address": "0x1234567890abcdef",
        "amount": 6000,
        "unlimited_approval": False,
        "known_contract": True,
        "requires_user_consent": False,
    }

    evaluation = client.post("/v1/actions/evaluate", json=action)
    assert evaluation.status_code == 200
    assert evaluation.json()["decision"] == "DENY"

    execution = client.post("/v1/actions/execute", json=action)
    assert execution.status_code == 200
    assert execution.json()["status"] == "REJECTED"


def test_consent_required_action_needs_verified_consent():
    action = {
        "request_id": "security-consent-001",
        "chain_id": 1,
        "action_kind": "transfer",
        "target_address": "0x1234567890abcdef",
        "amount": 100,
        "unlimited_approval": False,
        "known_contract": True,
        "requires_user_consent": True,
    }

    evaluation_response = client.post(
        "/v1/actions/evaluate", json=action
    )
    assert evaluation_response.status_code == 200
    evaluation = evaluation_response.json()
    assert evaluation["decision"] == "REQUIRE_CONSENT"

    blocked_response = client.post(
        "/v1/actions/execute", json=action
    )
    assert blocked_response.status_code == 200
    assert blocked_response.json()["status"] == "REJECTED"

    challenge_response = client.post(
        "/v1/consent/challenge", json=action
    )
    assert challenge_response.status_code == 200
    challenge = challenge_response.json()

    verification_response = client.post(
        "/v1/consent/verify",
        json={
            "challenge_id": challenge["challenge_id"],
            "action_hash": evaluation["action_hash"],
            "consent_granted": True,
        },
    )
    assert verification_response.status_code == 200
    assert verification_response.json()["verified"] is True

    execution_response = client.post(
        "/v1/actions/execute",
        json={
            **action,
            "consent_challenge_id": challenge["challenge_id"],
        },
    )
    assert execution_response.status_code == 200
    assert execution_response.json()["status"] == "SIMULATED_SUCCESS"


def test_tampered_receipt_is_rejected():
    action = {
        "request_id": "security-tamper-001",
        "chain_id": 1,
        "action_kind": "transfer",
        "target_address": "0x1234567890abcdef",
        "amount": 100,
        "unlimited_approval": False,
        "known_contract": True,
        "requires_user_consent": False,
    }

    evaluation_response = client.post(
        "/v1/actions/evaluate", json=action
    )
    assert evaluation_response.status_code == 200
    assert evaluation_response.json()["decision"] == "ALLOW"

    execution_response = client.post(
        "/v1/actions/execute", json=action
    )
    assert execution_response.status_code == 200
    execution = execution_response.json()
    assert execution["status"] == "SIMULATED_SUCCESS"

    receipt = execution["receipt"]

    original_response = client.post(
        "/v1/actions/verify", json=receipt
    )
    assert original_response.status_code == 200
    assert original_response.json()["verified"] is True

    tampered_receipt = {
        **receipt,
        "execution_status": "REAL_BLOCKCHAIN_SUCCESS",
    }

    tampered_response = client.post(
        "/v1/actions/verify", json=tampered_receipt
    )
    assert tampered_response.status_code == 200

    result = tampered_response.json()
    print("\nTampered receipt verification:", result)

    assert result["verified"] is False
