# SCOPE integration contract (safe advisory mode)

1. The current SCOPE action schema includes `chain_id`, `action_kind`, `target_address`, `amount`, `unlimited_approval`, `known_contract`, and `requires_user_consent`. PTXPhish contains labelled transaction hashes/categories, not these exact fields. Training must use fetched transaction payload features and inference must pass the same feature representation.
2. Preserve the deterministic policy engine. A model score may increase caution or request consent; it must never turn an explicit deterministic `DENY` into `ALLOW`.
3. This dataset is Ethereum-specific. Although Monad is EVM-compatible, validate transfer/approval selectors, transaction encoding and distribution shift on chain-specific examples before production use.
4. A model trained from the notebook is **not plug-and-play** with `/v1/actions/evaluate` unless the API passes calldata/payload-derived features through the same feature extractor. Do not silently map missing features to benign defaults.
5. Use an explicit `model_available`/`feature_coverage` flag. If required payload features are missing, skip the ML score and fall back to deterministic SCOPE policy.
6. Before merging: add tests for known phishing payloads, benign payloads, missing calldata, unknown selector, unsupported chain, deterministic deny precedence, and model artifact version.
