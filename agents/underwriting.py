from schema.state import AgentScratchpad, GlobalState

_RISK_WEIGHTS: dict[str, float] = {
    "auto": 0.8,
    "home": 0.6,
    "health": 1.0,
    "life": 0.5,
}


def underwriting_node(state: GlobalState) -> dict:
    """Calculate a risk score using the rules engine.

    Score range: 0.0 (lowest risk) to 10.0 (highest risk).
    Factors: policy type base weight, claim amount as a fraction of coverage limit.

    Args:
        state: Global state with customer_profile and optional claim_amount.

    Returns:
        State update dict with risk_score and current_stage="resolved".
    """
    if not state.customer_profile:
        return {
            "error": "No customer profile for underwriting",
            "current_stage": "error",
            "agent_scratchpad": [AgentScratchpad(
                agent="underwriting", action="calculate_risk", result="ERROR: no profile",
            )],
        }

    profile = state.customer_profile
    base_weight = _RISK_WEIGHTS.get(profile.policy_type, 0.7)
    coverage_ratio = (
        (state.claim_amount or 0.0) / profile.coverage_limit
        if profile.coverage_limit > 0
        else 0.0
    )
    risk_score = round(min(base_weight * 5.0 + coverage_ratio * 5.0, 10.0), 2)

    return {
        "risk_score": risk_score,
        "current_stage": "resolved",
        "agent_scratchpad": [AgentScratchpad(
            agent="underwriting",
            action="calculate_risk",
            result=f"risk_score={risk_score} (type={profile.policy_type}, ratio={coverage_ratio:.2f})",
        )],
    }
