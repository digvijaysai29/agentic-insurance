from langgraph.types import interrupt

from schema.state import AgentScratchpad, GlobalState


def human_review_node(state: GlobalState) -> dict:
    """Pause execution and wait for a human reviewer decision via interrupt.

    Raises a LangGraph interrupt with the claim details. When the external
    system resumes the graph via Command(resume={"decision": "approved"|"denied"}),
    interrupt() returns the decision dict and execution continues.

    Args:
        state: Global state with ticket_id, claim_amount, fraud_flags, and
            human_review_reason set by the approval_node.

    Returns:
        State update dict with final approval_status and current_stage="resolved".
    """
    human_decision: dict = interrupt({
        "ticket_id": state.ticket_id,
        "claim_amount": state.claim_amount,
        "customer_profile": (
            state.customer_profile.model_dump() if state.customer_profile else None
        ),
        "fraud_flags": state.fraud_flags,
        "reason": state.human_review_reason,
    })

    decision = human_decision.get("decision", "denied")
    reviewer = human_decision.get("reviewer_id", "unknown")

    return {
        "approval_status": decision,
        "requires_human_review": False,
        "current_stage": "resolved",
        "agent_scratchpad": [AgentScratchpad(
            agent="human_review",
            action="process_decision",
            result=f"decision={decision} by reviewer={reviewer}",
        )],
    }
