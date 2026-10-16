
import httpx
import pytest
from pydantic import ValidationError

from scope_sdk import (
    ProposedAction,
    ScopeAPIError,
    ScopeClient,
    ScopeSDKError,
)


def sample_action():
    return {
        "request_id": "sdk-test-001",
        "chain_id": 10143,
        "action_kind": "transfer",
        "target_address": "0x1234567890123456789012345678901234567890",
        "amount": 25,
        "unlimited_approval": False,
        "known_contract": True,
        "requires_user_consent": False,
    }


def mock_client(handler):
    transport = httpx.MockTransport(handler)
    return ScopeClient(
        base_url="http://scope.test",
        transport=transport,
    )


def test_health_returns_backend_status():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/health"
        return httpx.Response(
            200,
            json={"status": "ok", "service": "scope-backend"},
        )

    with mock_client(handler) as client:
        result = client.health()

    assert result == {
        "status": "ok",
        "service": "scope-backend",
    }


def test_evaluate_action_returns_typed_response():
    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/v1/actions/evaluate"

        body = request.read().decode()
        assert '"request_id":"sdk-test-001"' in body

        return httpx.Response(
            200,
            json={
                "request_id": "sdk-test-001",
                "action_hash": "0x" + "a" * 64,
                "decision": "ALLOW",
                "risk_score": 0,
                "risk_band": "LOW",
                "reasons": [],
            },
        )

    with mock_client(handler) as client:
        result = client.evaluate_action(sample_action())

    assert result.request_id == "sdk-test-001"
    assert result.decision == "ALLOW"
    assert result.risk_band == "LOW"


def test_execute_action_includes_consent_challenge_id():
    def handler(request):
        assert request.url.path == "/v1/actions/execute"
        assert request.method == "POST"

        import json
        payload = json.loads(request.read())

        assert payload["consent_challenge_id"] == "challenge-123"

        return httpx.Response(
            200,
            json={
                "status": "SIMULATED_SUCCESS",
                "action_hash": "0x" + "b" * 64,
                "receipt": {
                    "receipt_id": "receipt-123",
                },
            },
        )

    with mock_client(handler) as client:
        result = client.execute_action(
            sample_action(),
            consent_challenge_id="challenge-123",
        )

    assert result["status"] == "SIMULATED_SUCCESS"
    assert result["receipt"]["receipt_id"] == "receipt-123"


def test_http_api_error_exposes_status_and_detail():
    def handler(request):
        return httpx.Response(
            409,
            json={"detail": "Evaluate this action first."},
        )

    with mock_client(handler) as client:
        with pytest.raises(ScopeAPIError) as caught:
            client.create_consent_challenge(sample_action())

    assert caught.value.status_code == 409
    assert caught.value.detail == "Evaluate this action first."
    assert caught.value.method == "POST"
    assert caught.value.path == "/v1/consent/challenge"


def test_network_error_becomes_sdk_error():
    def handler(request):
        raise httpx.ConnectError(
            "simulated connection failure",
            request=request,
        )

    with mock_client(handler) as client:
        with pytest.raises(ScopeSDKError, match="Could not reach"):
            client.health()


def test_invalid_success_json_becomes_sdk_error():
    def handler(request):
        return httpx.Response(
            200,
            content=b"this is not JSON",
            headers={"content-type": "application/json"},
        )

    with mock_client(handler) as client:
        with pytest.raises(ScopeSDKError, match="invalid JSON"):
            client.health()


def test_invalid_action_is_rejected_before_http_request():
    def handler(request):
        pytest.fail("HTTP request should not happen for an invalid action")

    with mock_client(handler) as client:
        invalid_action = {
            **sample_action(),
            "chain_id": 0,
        }

        with pytest.raises(ValidationError):
            client.evaluate_action(invalid_action)


def test_typed_action_model_can_be_passed_to_client():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "request_id": "sdk-test-001",
                "action_hash": "0x" + "c" * 64,
                "decision": "ALLOW",
                "risk_score": 0,
                "risk_band": "LOW",
                "reasons": [],
            },
        )

    action = ProposedAction.model_validate(sample_action())

    with mock_client(handler) as client:
        result = client.evaluate_action(action)

    assert isinstance(result.request_id, str)
    assert result.decision == "ALLOW"




def test_decode_action_returns_typed_response():
    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/v1/actions/decode"
        return httpx.Response(200, json={
            "supported": False,
            "chain_id": 10143,
            "target_address": "0xabc",
            "selector": "0xdeadbeef",
            "method": None,
            "decoded": {},
            "reason": "ACTION_UNSUPPORTED",
        })

    with mock_client(handler) as client:
        result = client.decode_action(
            chain_id=10143,
            target_address="0xabc",
            calldata="0xdeadbeef",
        )

    assert result.supported is False
    assert result.reason == "ACTION_UNSUPPORTED"
