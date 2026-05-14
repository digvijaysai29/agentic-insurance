from schema.state import AgentScratchpad, GlobalState, ToolCall
from tools.fraud_search import search_fraud_patterns


def fraud_node(state: GlobalState) -> dict:
    """Search the vector DB for anomaly patterns that match this claim.

    Args:
        state: Global state with claim_amount and customer_profile.

    Returns:
        State update dict with fraud_flags populated; empty list means clean.
    """
    if not state.customer_profile or state.claim_amount is None:
        return {
            "error": "Insufficient data for fraud check",
            "current_stage": "error",
            "agent_scratchpad": [AgentScratchpad(
                agent="fraud", action="check_patterns", result="ERROR: missing data",
            )],
        }

    query = (
        f"policy_type={state.customer_profile.policy_type} "
        f"claim_amount={state.claim_amount} "
        f"customer_id={state.customer_profile.customer_id}"
    )
    flags = search_fraud_patterns(query, top_k=5, similarity_threshold=0.85)

    tool_call = ToolCall(
        tool_name="search_fraud_patterns",
        args={"query": query, "top_k": 5, "similarity_threshold": 0.85},
        result=f"{len(flags)} flag(s) found",
    )

    return {
        "fraud_flags": flags,
        "current_stage": "approval" if not flags else "error",
        "agent_scratchpad": [AgentScratchpad(
            agent="fraud",
            action="check_patterns",
            result=f"{'CLEAN' if not flags else 'FLAGGED'}: {flags}",
            tool_calls=[tool_call],
        )],
    }
