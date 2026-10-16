
from scope_sdk import ScopeClient, ScopeAPIError, ScopeSDKError


action = {
    "request_id": "sdk-live-demo-001",
    "chain_id": 10143,
    "action_kind": "transfer",
    "target_address": "0x1234567890123456789012345678901234567890",
    "amount": 25,
    "unlimited_approval": False,
    "known_contract": True,
    "requires_user_consent": False,
}


def main():
    try:
        with ScopeClient("http://127.0.0.1:8000") as client:
            print("1. Checking backend...")
            print(client.health())

            print("\n2. Evaluating action...")
            evaluation = client.evaluate_action(action)
            print(evaluation.model_dump())

            if evaluation.decision != "ALLOW":
                print(
                    "\nExecution skipped because the policy decision is:",
                    evaluation.decision,
                )
                return

            print("\n3. Requesting simulated execution...")
            result = client.execute_action(action)
            print(result)

            if result.get("status") != "SIMULATED_SUCCESS":
                print("\nExecution was rejected; no receipt verification attempted.")
                return

            print("\n4. Retrieving receipt...")
            receipt = client.get_receipt(
                result["receipt"]["receipt_id"]
            )
            print(receipt.model_dump())

            print("\n5. Verifying receipt...")
            verification = client.verify_receipt(receipt)
            print(verification.model_dump())

    except ScopeAPIError as exc:
        print("SCOPE API error:", exc)
        print("HTTP status:", exc.status_code)
        print("Details:", exc.detail)

    except ScopeSDKError as exc:
        print("SCOPE SDK error:", exc)


if __name__ == "__main__":
    main()
