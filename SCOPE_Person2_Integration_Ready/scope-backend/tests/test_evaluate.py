
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def sample_action(**overrides):
    action = {
        "request_id": "test-001",
        "chain_id": 10143,
        "action_kind": "transfer",
        "target_address": "0x1234567890123456789012345678901234567890",
        "amount": 100,
        "unlimited_approval": False,
        "known_contract": True,
        "requires_user_consent": False,
    }
    action.update(overrides)
    return action


def test_unlimited_approval_is_denied():
    response = client.post(
        "/v1/actions/evaluate",
        json=sample_action(
            action_kind="token_approval",
            unlimited_approval=True,
        ),
    )

    assert response.status_code == 200
    result = response.json()
    assert result["decision"] == "DENY"
    assert result["risk_band"] == "HIGH"
    assert "POLICY_UNLIMITED_APPROVAL_BLOCKED" in result["reasons"]


def test_normal_action_is_allowed():
    response = client.post(
        "/v1/actions/evaluate",
        json=sample_action(),
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "ALLOW"


def test_user_consent_is_required():
    response = client.post(
        "/v1/actions/evaluate",
        json=sample_action(requires_user_consent=True),
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "REQUIRE_CONSENT"


def test_value_above_policy_limit_is_denied():
    response = client.post(
        "/v1/actions/evaluate",
        json=sample_action(amount=5001),
    )

    assert response.status_code == 200
    result = response.json()
    assert result["decision"] == "DENY"
    assert "POLICY_VALUE_LIMIT_EXCEEDED" in result["reasons"]


def test_invalid_action_is_rejected():
    action = sample_action()
    action["unexpected_field"] = "not allowed"

    response = client.post(
        "/v1/actions/evaluate",
        json=action,
    )

    assert response.status_code == 422
