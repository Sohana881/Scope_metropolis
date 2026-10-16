# SCOPE API integration contract (Person 2)

Base URL locally: `http://127.0.0.1:8000`. Swagger: `/docs`. OpenAPI: `/openapi.json`.
All current JSON keys are `snake_case`. The action hash is SHA-256 over canonical JSON of the validated `ProposedAction`: JSON keys sorted, separators `(",", ":")`, UTF-8, with defaults included. Keep the same fields and defaults across clients; do not hash the original request text.

## Canonical action payload
```json
{
  "request_id": "integration-transfer-001",
  "chain_id": 10143,
  "action_kind": "transfer",
  "target_address": "0x1234567890123456789012345678901234567890",
  "amount": 25,
  "unlimited_approval": false,
  "known_contract": true,
  "requires_user_consent": false
}
```
`action_kind` must be `transfer`, `token_approval`, or `contract_call`. `chain_id` must be positive; `amount` must be non-negative. Unknown fields are rejected.

## Endpoints and flow
1. `POST /v1/actions/evaluate` with action payload. Response: `request_id`, `action_hash`, `decision` (`ALLOW`, `DENY`, `REQUIRE_CONSENT`), `risk_score`, `risk_band`, `reasons`.
2. For supported transaction calldata, `POST /v1/actions/decode`:
```json
{"chain_id":10143,"target_address":"0x1234567890123456789012345678901234567890","calldata":"0x","value_wei":"0"}
```
Response includes `supported`, `selector`, `method`, `decoded`, and stable `reason`. Current decoder recognizes ERC-20 `transfer` (`0xa9059cbb`), `approve` (`0x095ea7b3`), and `transferFrom` (`0x23b872dd`). It is a minimal selector decoder, not a full ABI/asset-decimal decoder. Unsupported calls return `supported:false` and `ACTION_UNSUPPORTED`.
3. If decision is `REQUIRE_CONSENT`, call `POST /v1/consent/challenge` with the exact same action. Response: `challenge_id`, `action_hash`, `status`, `message`.
4. `POST /v1/consent/verify`:
```json
{"challenge_id":"<challenge_id>","action_hash":"<action_hash>","consent_granted":true}
```
This is a demo confirmation endpoint, not real WebAuthn. Successful response includes `verified:true`, `challenge_id`, `action_hash`, `reason`.
5. `POST /v1/actions/execute` with action payload; if consent is required, also include `consent_challenge_id`. Response has `status`, `reason`, `action_hash`, and `receipt` (receipt or null). A rejected action may still return HTTP 200 with `status:"REJECTED"`; inspect `reason`, not HTTP status alone.
6. `GET /v1/receipts/{receipt_id}` retrieves the receipt.
7. `POST /v1/actions/verify` with the complete receipt JSON. Response includes `verified`, `reason`, and optional `field`.

## Example response: evaluation
```json
{
  "request_id":"integration-transfer-001",
  "action_hash":"0x...",
  "decision":"ALLOW",
  "risk_score":0,
  "risk_band":"LOW",
  "reasons":["NO_CONFIGURED_RISK_SIGNALS"]
}
```

## Integration notes for Person 1 (contracts)
- Agree on the exact action-hash encoding before comparing Solidity/TypeScript hashes. The current backend hash covers the entire validated action object including `request_id` and default boolean fields.
- Backend receipt signature is HMAC-SHA256 with a server secret; it is **not** a public-key signature that a smart contract or independent external verifier can validate without access to that secret.
- No on-chain receipt commitment or real transaction hash is produced by the current simulated executor.
- Grant/revoke routes are not implemented yet. Do not wire a frontend to a nonexistent revoke endpoint.

## Integration notes for Person 3 (frontend)
- Configure `SCOPE_CORS_ORIGINS` to include the frontend origin (comma-separated origins, no trailing slash).
- Local defaults permit common Next/Vite development ports.
- Use the typed SDK (`ScopeClient`) or the OpenAPI spec. Handle both HTTP errors and execution responses whose body has `status:"REJECTED"`.
- For consent-required actions, display a clear consent step, then send the exact same action and returned `consent_challenge_id` to execute.
- Treat unsupported decoder results as unknown, not safe.

## Known gaps (do not claim as implemented)
- Real WebAuthn/passkey assertion verification and challenge expiry.
- Persistent scoped grants and revoke/kill-switch API.
- Full ABI transaction decoding, ERC-20 decimals/token metadata and effects analysis.
- Real chain execution, RPC receipt checks and on-chain provenance commitments.
- Common envelope metadata (`schemaVersion`, `timestamp`, standardized `error.code`) is not yet present on every endpoint.
