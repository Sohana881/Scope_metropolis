
from services.action_hash import calculate_action_hash
from services.schemas import ProposedAction


def sample_action(**overrides) -> ProposedAction:
    data = {
        "request_id": "hash-test-001",
        "chain_id": 10143,
        "action_kind": "transfer",
        "target_address": "0x1234567890123456789012345678901234567890",
        "amount": 100,
        "unlimited_approval": False,
        "known_contract": True,
        "requires_user_consent": False,
    }

    data.update(overrides)
    return ProposedAction(**data)


def test_same_action_produces_same_hash():
    action = sample_action()

    hash_one = calculate_action_hash(action)
    hash_two = calculate_action_hash(action)

    assert hash_one == hash_two


def test_different_recipient_produces_different_hash():
    action_one = sample_action()

    action_two = sample_action(
        target_address="0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
    )

    assert calculate_action_hash(action_one) != calculate_action_hash(
        action_two
    )


def test_different_amount_produces_different_hash():
    action_one = sample_action(amount=100)
    action_two = sample_action(amount=200)

    assert calculate_action_hash(action_one) != calculate_action_hash(
        action_two
    )


def test_hash_has_expected_format():
    action_hash = calculate_action_hash(sample_action())

    assert action_hash.startswith("0x")
    assert len(action_hash) == 66
    assert all(
        character in "0123456789abcdef"
        for character in action_hash[2:]
    )
