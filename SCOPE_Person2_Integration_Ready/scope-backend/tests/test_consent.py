
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def sample_action(**overrides):
    action = {
        "request_id": "consent-test-001",
        "chain_id": 10143,
        "action_kind": "transfer",
        "target_address": "0x1234567890123456789012345678901234567890",
        "amount": 1500,
        "unlimited_approval": False,
        "known_contract": True,
        "requires_user_consent": False,
    }
    action.update(overrides)
    return action


def evaluate_and_create_challenge(action):
    evaluation = client.post("/v1/actions/evaluate", json=action)
    assert evaluation.status_code == 200
    assert evaluation.json()["decision"] == "REQUIRE_CONSENT"

    challenge_response = client.post(
        "/v1/consent/challenge",
        json=action,
    )
    assert challenge_response.status_code == 200

    return evaluation.json(), challenge_response.json()


def verify_challenge(challenge, action_hash, consent_granted=True):
    return client.post(
        "/v1/consent/verify",
        json={
            "challenge_id": challenge["challenge_id"],
            "action_hash": action_hash,
            "consent_granted": consent_granted,
        },
    )


def test_execution_requires_consent():
    action = sample_action()
    client.post("/v1/actions/evaluate", json=action)

    response = client.post("/v1/actions/execute", json=action)

    assert response.json()["status"] == "REJECTED"
    assert response.json()["reason"] == "VALID_CONSENT_REQUIRED"


def test_valid_consent_allows_execution():
    action = sample_action()
    evaluation, challenge = evaluate_and_create_challenge(action)

    verification = verify_challenge(
        challenge,
        evaluation["action_hash"],
    )
    assert verification.status_code == 200
    assert verification.json()["verified"] is True

    execution = client.post(
        "/v1/actions/execute",
        json={
            **action,
            "consent_challenge_id": challenge["challenge_id"],
        },
    )

    assert execution.json()["status"] == "SIMULATED_SUCCESS"


def test_wrong_hash_invalidates_challenge():
    action = sample_action()
    _, challenge = evaluate_and_create_challenge(action)

    response = verify_challenge(
        challenge,
        "0x" + "0" * 64,
    )

    assert response.status_code == 400
    assert response.json()["detail"]["reason"] == "ACTION_HASH_MISMATCH"

    retry = verify_challenge(challenge, challenge["action_hash"])

    assert retry.status_code == 400
    assert retry.json()["detail"]["reason"] == "CHALLENGE_ALREADY_USED"


def test_denied_consent_cannot_execute():
    action = sample_action()
    evaluation, challenge = evaluate_and_create_challenge(action)

    response = verify_challenge(
        challenge,
        evaluation["action_hash"],
        consent_granted=False,
    )

    assert response.status_code == 400
    assert response.json()["detail"]["reason"] == "CONSENT_DENIED"

    execution = client.post(
        "/v1/actions/execute",
        json={
            **action,
            "consent_challenge_id": challenge["challenge_id"],
        },
    )

    assert execution.json()["status"] == "REJECTED"
    assert execution.json()["reason"] == "VALID_CONSENT_REQUIRED"


def test_consent_challenge_can_only_be_used_once():
    action = sample_action()
    evaluation, challenge = evaluate_and_create_challenge(action)

    first = verify_challenge(challenge, evaluation["action_hash"])
    assert first.status_code == 200

    second = verify_challenge(challenge, evaluation["action_hash"])
    assert second.status_code == 400
    assert second.json()["detail"]["reason"] == "CHALLENGE_ALREADY_USED"


def test_consent_must_match_specific_challenge():
    action = sample_action()
    evaluation, challenge = evaluate_and_create_challenge(action)

    verification = verify_challenge(challenge, evaluation["action_hash"])
    assert verification.status_code == 200

    execution = client.post("/v1/actions/execute", json=action)

    assert execution.json()["status"] == "REJECTED"
    assert execution.json()["reason"] == "VALID_CONSENT_REQUIRED"


def test_verified_challenge_cannot_authorize_different_action():
    original = sample_action()
    evaluation, challenge = evaluate_and_create_challenge(original)

    verification = verify_challenge(challenge, evaluation["action_hash"])
    assert verification.status_code == 200

    different_action = {
        **original,
        "request_id": "consent-test-different-action",
        "target_address": "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
    }

    client.post("/v1/actions/evaluate", json=different_action)

    execution = client.post(
        "/v1/actions/execute",
        json={
            **different_action,
            "consent_challenge_id": challenge["challenge_id"],
        },
    )

    assert execution.json()["status"] == "REJECTED"
    assert execution.json()["reason"] in {
        "ACTION_HASH_MISMATCH",
        "VALID_CONSENT_REQUIRED",
    }


def test_successful_execution_consumes_consent_challenge():
    action = sample_action()
    evaluation, challenge = evaluate_and_create_challenge(action)

    verification = verify_challenge(challenge, evaluation["action_hash"])
    assert verification.status_code == 200

    execution = client.post(
        "/v1/actions/execute",
        json={
            **action,
            "consent_challenge_id": challenge["challenge_id"],
        },
    )

    assert execution.json()["status"] == "SIMULATED_SUCCESS"

    retry = client.post(
        "/v1/consent/verify",
        json={
            "challenge_id": challenge["challenge_id"],
            "action_hash": evaluation["action_hash"],
            "consent_granted": True,
        },
    )

    assert retry.status_code == 400
    assert retry.json()["detail"]["reason"] == "CHALLENGE_ALREADY_USED"
