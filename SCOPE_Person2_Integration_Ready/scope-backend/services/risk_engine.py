
from services.schemas import ProposedAction


def analyze_risk(action: ProposedAction) -> tuple[int, list[str]]:
    score = 0
    reasons = []

    if action.unlimited_approval:
        score += 70
        reasons.append("UNLIMITED_TOKEN_APPROVAL")

    if not action.known_contract:
        score += 25
        reasons.append("UNKNOWN_CONTRACT")

    if action.amount > 1000:
        score += 20
        reasons.append("HIGH_TRANSACTION_AMOUNT")

    if not reasons:
        reasons.append("NO_CONFIGURED_RISK_SIGNALS")

    return min(score, 100), reasons


def risk_band(score: int) -> str:
    if score >= 60:
        return "HIGH"
    if score >= 30:
        return "MEDIUM"
    return "LOW"
