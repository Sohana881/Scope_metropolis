from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_unknown_selector_is_explicitly_unsupported():
    response = client.post("/v1/actions/decode", json={
        "chain_id": 10143,
        "target_address": "0x1234567890123456789012345678901234567890",
        "calldata": "0xdeadbeef",
    })
    assert response.status_code == 200
    assert response.json()["supported"] is False
    assert response.json()["reason"] == "ACTION_UNSUPPORTED"


def test_erc20_transfer_selector_is_decoded():
    recipient = "0000000000000000000000001234567890123456789012345678901234567890"
    amount = f"{25:064x}"
    response = client.post("/v1/actions/decode", json={
        "chain_id": 10143,
        "target_address": "0x1234567890123456789012345678901234567890",
        "calldata": "0xa9059cbb" + recipient + amount,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["supported"] is True
    assert body["method"] == "transfer"
    assert body["decoded"]["recipient"] == "0x1234567890123456789012345678901234567890"
    assert body["decoded"]["amount_raw"] == "25"


def test_invalid_calldata_returns_422():
    response = client.post("/v1/actions/decode", json={
        "chain_id": 10143,
        "target_address": "0xabc",
        "calldata": "not-hex",
    })
    assert response.status_code == 422
