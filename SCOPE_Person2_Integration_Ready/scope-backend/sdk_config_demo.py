
from scope_sdk import ScopeClient, ScopeSDKError


def main():
    try:
        with ScopeClient.from_env() as client:
            print("Configured backend:", client.base_url)
            print("Configured timeout:", client.timeout)
            print("Health:", client.health())

    except ScopeSDKError as exc:
        print("SDK configuration or request error:", exc)


if __name__ == "__main__":
    main()
