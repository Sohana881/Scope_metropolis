
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from main import app
from services.database import get_evaluated_action, list_receipts
from services.action_hash import calculate_action_hash
from services.schemas import ProposedAction

client = TestClient(app)


def sample_action(**overrides):
    action = {
        "request_id": "execution-test-001",
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


def test_allowed_action_creates_receipt():
    action = sample_action()

    evaluation = client.post("/v1/actions/evaluate", json=action)
    assert evaluation.status_code == 200
    assert evaluation.json()["decision"] == "ALLOW"

    execution = client.post("/v1/actions/execute", json=action)
    assert execution.status_code == 200

    result = execution.json()
    assert result["status"] == "SIMULATED_SUCCESS"
    assert result["receipt"]["action_hash"] == evaluation.json()["action_hash"]


def test_unassessed_action_is_rejected():
    response = client.post(
        "/v1/actions/execute",
        json=sample_action(),
    )

    assert response.json()["status"] == "REJECTED"
    assert response.json()["reason"] == "ACTION_NOT_EVALUATED"


def test_denied_action_cannot_execute():
    action = sample_action(
        action_kind="token_approval",
        unlimited_approval=True,
    )

    client.post("/v1/actions/evaluate", json=action)
    response = client.post("/v1/actions/execute", json=action)

    assert response.json()["status"] == "REJECTED"
    assert response.json()["reason"] == "POLICY_DOES_NOT_ALLOW_EXECUTION"


def test_modified_action_is_rejected():
    original = sample_action()
    client.post("/v1/actions/evaluate", json=original)

    modified = {**original, "amount": 200}
    response = client.post("/v1/actions/execute", json=modified)

    assert response.json()["status"] == "REJECTED"
    assert response.json()["reason"] == "ACTION_NOT_EVALUATED"


def test_receipt_can_be_retrieved():
    action = sample_action()
    client.post("/v1/actions/evaluate", json=action)

    execution = client.post("/v1/actions/execute", json=action)
    assert execution.json()["status"] == "SIMULATED_SUCCESS"
    receipt_id = execution.json()["receipt"]["receipt_id"]

    response = client.get(f"/v1/receipts/{receipt_id}")

    assert response.status_code == 200
    assert response.json()["action_hash"] == execution.json()["action_hash"]


def test_same_action_cannot_execute_twice():
    action = sample_action()
    client.post("/v1/actions/evaluate", json=action)

    first = client.post("/v1/actions/execute", json=action)
    second = client.post("/v1/actions/execute", json=action)

    assert first.json()["status"] == "SIMULATED_SUCCESS"
    assert second.json()["status"] == "REJECTED"
    assert second.json()["reason"] == "ACTION_ALREADY_EXECUTED"


def test_execution_uses_exact_stored_action():
    action = sample_action()
    action_model = ProposedAction.model_validate(action)
    action_hash = calculate_action_hash(action_model)

    client.post("/v1/actions/evaluate", json=action)

    stored = get_evaluated_action(action_hash)
    assert stored is not None
    assert stored["action"] == action


def test_duplicate_execution_does_not_create_second_receipt():
    action = sample_action()
    client.post("/v1/actions/evaluate", json=action)

    before = len(list_receipts())

    first = client.post("/v1/actions/execute", json=action)
    second = client.post("/v1/actions/execute", json=action)

    after = len(list_receipts())

    assert first.json()["status"] == "SIMULATED_SUCCESS"
    assert second.json()["status"] == "REJECTED"
    assert second.json()["reason"] == "ACTION_ALREADY_EXECUTED"
    assert after == before + 1


def test_concurrent_execution_creates_only_one_receipt():
    action = sample_action(request_id="concurrent-execution-test")
    evaluation = client.post("/v1/actions/evaluate", json=action)
    assert evaluation.status_code == 200

    action_hash = evaluation.json()["action_hash"]
    before = sum(
        1
        for receipt in list_receipts()
        if receipt["action_hash"] == action_hash
        and receipt["execution_status"] == "SIMULATED_SUCCESS"
    )

    def execute_action():
        # Each worker uses its own TestClient instance.
        with TestClient(app) as worker_client:
            return worker_client.post("/v1/actions/execute", json=action).json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(execute_action),
            executor.submit(execute_action),
        ]
        results = [future.result(timeout=15) for future in futures]

    statuses = [result["status"] for result in results]

    assert statuses.count("SIMULATED_SUCCESS") == 1
    assert statuses.count("REJECTED") == 1

    rejected = next(
        result for result in results
        if result["status"] == "REJECTED"
    )
    assert rejected["reason"] == "ACTION_ALREADY_EXECUTED"

    after = sum(
        1
        for receipt in list_receipts()
        if receipt["action_hash"] == action_hash
        and receipt["execution_status"] == "SIMULATED_SUCCESS"
    )

    assert after == before + 1
