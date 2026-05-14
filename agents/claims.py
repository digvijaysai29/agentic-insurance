import re

from schema.state import AgentScratchpad, GlobalState, ToolCall
from tools.policy_lookup import lookup_policy


def claims_node(state: GlobalState) -> dict:
    """Validate policy coverage and extract the claim amount from the request.

    Args:
        state: Global state with customer_profile and messages.

    Returns:
        State update dict with claim_amount set or error flag.
    """
    if not state.customer_profile:
        return {
            "error": "No customer profile available for claims validation",
            "current_stage": "error",
            "agent_scratchpad": [AgentScratchpad(
                agent="claims", action="validate_coverage", result="ERROR: no customer profile",
            )],
        }

    policy_number = state.customer_profile.policy_number
    db_profile = lookup_policy(policy_number)
    tool_call = ToolCall(
        tool_name="lookup_policy",
        args={"policy_number": policy_number},
        result="found" if db_profile else "not found",
    )

    if db_profile is None:
        return {
            "error": f"Policy {policy_number} not found",
            "current_stage": "error",
            "agent_scratchpad": [AgentScratchpad(
                agent="claims",
                action="lookup_policy",
                result=f"ERROR: policy {policy_number} not found",
                tool_calls=[tool_call],
            )],
        }

    customer_text = str(state.messages[-1].content) if state.messages else ""
    amount = _extract_amount(customer_text)

    return {
        "claim_amount": amount,
        "current_stage": "fraud",
        "agent_scratchpad": [AgentScratchpad(
            agent="claims",
            action="validate_coverage",
            result=f"OK: policy valid, claim_amount=${amount}",
            tool_calls=[tool_call],
        )],
    }


def _extract_amount(text: str) -> float:
    """Extract the first dollar amount mentioned in the text."""
    match = re.search(r"\$?([\d,]+(?:\.\d{2})?)", text)
    if match:
        return float(match.group(1).replace(",", ""))
    return 0.0
