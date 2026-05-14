from schema.state import AgentScratchpad, GlobalState

HUMAN_REVIEW_THRESHOLD = 10_000.0


def approval_node(state: GlobalState) -> dict:
    """Determine if a claim can be auto-approved or requires human review.

    Claims above $10,000 are flagged for human-in-the-loop review.
    Claims at or below $10,000 are auto-approved immediately.

    Args:
        state: Global state with claim_amount.

    Returns:
        State update dict with approval_status and requires_human_review flag.
    """
    amount = state.claim_amount or 0.0

    if amount > HUMAN_REVIEW_THRESHOLD:
        return {
            "approval_status": "human_required",
            "requires_human_review": True,
            "human_review_reason": (
                f"Claim of ${amount:,.2f} exceeds ${HUMAN_REVIEW_THRESHOLD:,.0f} auto-approval threshold"
            ),
            "current_stage": "human_review",
            "agent_scratchpad": [AgentScratchpad(
                agent="approval",
                action="threshold_check",
                result=f"HUMAN_REQUIRED: ${amount:,.2f} > threshold",
            )],
        }

    return {
        "approval_status": "approved",
        "requires_human_review": False,
        "current_stage": "resolved",
        "agent_scratchpad": [AgentScratchpad(
            agent="approval",
            action="auto_approve",
            result=f"AUTO_APPROVED: ${amount:,.2f} ≤ threshold",
        )],
    }
