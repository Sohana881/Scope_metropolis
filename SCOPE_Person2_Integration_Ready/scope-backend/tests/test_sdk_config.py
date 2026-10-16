
import pytest

from scope_sdk import ScopeClient, ScopeSDKError


def test_from_env_uses_default_configuration(monkeypatch):
    monkeypatch.delenv("SCOPE_BASE_URL", raising=False)
    monkeypatch.delenv("SCOPE_TIMEOUT", raising=False)

    with ScopeClient.from_env() as client:
        assert client.base_url == "http://127.0.0.1:8000"
        assert client.timeout == 10.0


def test_from_env_uses_custom_configuration(monkeypatch):
    monkeypatch.setenv(
        "SCOPE_BASE_URL",
        "http://localhost:9000/",
    )
    monkeypatch.setenv("SCOPE_TIMEOUT", "4.5")

    with ScopeClient.from_env() as client:
        assert client.base_url == "http://localhost:9000"
        assert client.timeout == 4.5


def test_from_env_rejects_non_numeric_timeout(monkeypatch):
    monkeypatch.setenv("SCOPE_TIMEOUT", "not-a-number")

    with pytest.raises(
        ScopeSDKError,
        match="SCOPE_TIMEOUT must be a valid number",
    ):
        ScopeClient.from_env()


@pytest.mark.parametrize("timeout", ["0", "-1", "-0.5"])
def test_from_env_rejects_non_positive_timeout(monkeypatch, timeout):
    monkeypatch.setenv("SCOPE_TIMEOUT", timeout)

    with pytest.raises(
        ScopeSDKError,
        match="SCOPE_TIMEOUT must be greater than zero",
    ):
        ScopeClient.from_env()


def test_from_env_rejects_empty_base_url(monkeypatch):
    monkeypatch.setenv("SCOPE_BASE_URL", "   ")

    with pytest.raises(
        ScopeSDKError,
        match="SCOPE_BASE_URL must not be empty",
    ):
        ScopeClient.from_env()
