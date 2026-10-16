
from services.action_hash import calculate_action_hash
from services.schemas import ProposedAction
from services.risk_engine import analyze_risk, risk_band


def evaluate_policy(action: ProposedAction) -> dict:
    score, reasons = analyze_risk(action)
    action_hash = calculate_action_hash(action)

    # Hard-denial rules have the highest priority.
    if action.unlimited_approval:
        decision = "DENY"
        reasons.append("POLICY_UNLIMITED_APPROVAL_BLOCKED")

    elif action.amount > 5000:
        decision = "DENY"
        reasons.append("POLICY_VALUE_LIMIT_EXCEEDED")

    # Require consent for flagged actions or medium/high risk.
    elif action.requires_user_consent or score >= 20:
        decision = "REQUIRE_CONSENT"
        reasons.append("USER_CONSENT_REQUIRED")

    else:
        decision = "ALLOW"

    return {
        "request_id": action.request_id,
        "action_hash": action_hash,
        "decision": decision,
        "risk_score": score,
        "risk_band": risk_band(score),
        "reasons": reasons,
    }
