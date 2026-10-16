
"""Configurable HTTP client for the SCOPE backend API."""

import os
from typing import Any

import httpx
from pydantic import ValidationError

from scope_sdk.models import (
    ActionEvaluation,
    ConsentChallenge,
    ConsentVerification,
    DecodeResult,
    ProposedAction,
    Receipt,
    ReceiptVerification,
)


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT = 10.0


class ScopeSDKError(Exception):
    """Base exception raised by the SCOPE SDK."""


class ScopeAPIError(ScopeSDKError):
    """An HTTP error returned by the SCOPE API."""

    def __init__(
        self,
        status_code: int,
        detail: Any,
        method: str,
        path: str,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.method = method
        self.path = path

        super().__init__(
            f"SCOPE API returned HTTP {status_code} "
            f"for {method} {path}: {detail}"
        )


class ScopeClient:
    """Typed client for the SCOPE REST API."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        normalized_url = base_url.strip().rstrip("/")

        if not normalized_url:
            raise ValueError("base_url must not be empty.")

        if timeout <= 0:
            raise ValueError("timeout must be greater than zero.")

        self.base_url = normalized_url
        self.timeout = timeout

        self._http = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            transport=transport,
        )

    @classmethod
    def from_env(cls) -> "ScopeClient":
        """
        Build a client using environment variables.

        SCOPE_BASE_URL defaults to http://127.0.0.1:8000.
        SCOPE_TIMEOUT defaults to 10 seconds.
        """
        base_url = os.getenv("SCOPE_BASE_URL", DEFAULT_BASE_URL).strip()
        timeout_text = os.getenv(
            "SCOPE_TIMEOUT",
            str(DEFAULT_TIMEOUT),
        ).strip()

        if not base_url:
            raise ScopeSDKError(
                "SCOPE_BASE_URL must not be empty."
            )

        try:
            timeout = float(timeout_text)
        except ValueError as exc:
            raise ScopeSDKError(
                "SCOPE_TIMEOUT must be a valid number of seconds."
            ) from exc

        if timeout <= 0:
            raise ScopeSDKError(
                "SCOPE_TIMEOUT must be greater than zero."
            )

        try:
            return cls(base_url=base_url, timeout=timeout)
        except ValueError as exc:
            raise ScopeSDKError(str(exc)) from exc

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._http.close()

    def __enter__(self) -> "ScopeClient":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        """Send a request and normalize transport, HTTP and JSON errors."""
        try:
            response = self._http.request(
                method,
                path,
                json=json_body,
            )
        except httpx.RequestError as exc:
            raise ScopeSDKError(
                f"Could not reach the SCOPE API at {self.base_url}: {exc}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            if not response.is_success:
                data = response.text
            else:
                raise ScopeSDKError(
                    f"SCOPE API returned invalid JSON for "
                    f"{method} {path}."
                ) from exc

        if not response.is_success:
            if isinstance(data, dict):
                detail = data.get("detail", data)
            else:
                detail = data

            raise ScopeAPIError(
                status_code=response.status_code,
                detail=detail,
                method=method,
                path=path,
            )

        return data

    @staticmethod
    def _validate(model_type, data):
        try:
            return model_type.model_validate(data)
        except ValidationError as exc:
            raise ScopeSDKError(
                f"SCOPE API response did not match "
                f"{model_type.__name__}: {exc}"
            ) from exc

    def health(self) -> dict[str, Any]:
        """Check backend availability."""
        data = self._request("GET", "/health")

        if not isinstance(data, dict):
            raise ScopeSDKError(
                "Health response must be a JSON object."
            )

        return data

    def evaluate_action(
        self,
        action: ProposedAction | dict[str, Any],
    ) -> ActionEvaluation:
        """Evaluate an action against the risk and policy engines."""
        payload = self._action_payload(action)
        data = self._request(
            "POST",
            "/v1/actions/evaluate",
            json_body=payload,
        )
        return self._validate(ActionEvaluation, data)

    def decode_action(
        self,
        *,
        chain_id: int,
        target_address: str,
        calldata: str = "0x",
        value_wei: str = "0",
    ) -> DecodeResult:
        """Decode supported common ERC-20 calldata selectors."""
        data = self._request(
            "POST",
            "/v1/actions/decode",
            json_body={
                "chain_id": chain_id,
                "target_address": target_address,
                "calldata": calldata,
                "value_wei": value_wei,
            },
        )
        return self._validate(DecodeResult, data)

    def create_consent_challenge(
        self,
        action: ProposedAction | dict[str, Any],
    ) -> ConsentChallenge:
        """Request a consent challenge for an evaluated action."""
        payload = self._action_payload(action)
        data = self._request(
            "POST",
            "/v1/consent/challenge",
            json_body=payload,
        )
        return self._validate(ConsentChallenge, data)

    def verify_consent(
        self,
        challenge_id: str,
        action_hash: str,
        consent_granted: bool,
    ) -> ConsentVerification:
        """Submit the user's consent decision."""
        data = self._request(
            "POST",
            "/v1/consent/verify",
            json_body={
                "challenge_id": challenge_id,
                "action_hash": action_hash,
                "consent_granted": consent_granted,
            },
        )
        return self._validate(ConsentVerification, data)

    def execute_action(
        self,
        action: ProposedAction | dict[str, Any],
        consent_challenge_id: str | None = None,
    ) -> dict[str, Any]:
        """Request simulated execution through the SCOPE API."""
        payload = self._action_payload(action)

        if consent_challenge_id is not None:
            payload["consent_challenge_id"] = consent_challenge_id

        data = self._request(
            "POST",
            "/v1/actions/execute",
            json_body=payload,
        )

        if not isinstance(data, dict):
            raise ScopeSDKError(
                "Execution response must be a JSON object."
            )

        return data

    def get_receipt(self, receipt_id: str) -> Receipt:
        """Retrieve a stored receipt, including its signature."""
        data = self._request(
            "GET",
            f"/v1/receipts/{receipt_id}",
        )
        return self._validate(Receipt, data)

    def verify_receipt(
        self,
        receipt: Receipt | dict[str, Any],
    ) -> ReceiptVerification:
        """Verify a receipt against the backend's stored record."""
        if isinstance(receipt, Receipt):
            payload = receipt.model_dump(exclude_none=True)
        else:
            payload = dict(receipt)

        data = self._request(
            "POST",
            "/v1/actions/verify",
            json_body=payload,
        )
        return self._validate(ReceiptVerification, data)

    @staticmethod
    def _action_payload(
        action: ProposedAction | dict[str, Any],
    ) -> dict[str, Any]:
        """Validate action data before sending it to the API."""
        model = (
            action
            if isinstance(action, ProposedAction)
            else ProposedAction.model_validate(action)
        )
        return model.model_dump(mode="json")
