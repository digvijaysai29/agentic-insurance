from schema.state import AgentScratchpad, GlobalState


def error_node(state: GlobalState) -> dict:
    """Normalize the state when an error has occurred in a prior node.

    Args:
        state: Global state with the error field set by a prior node.

    Returns:
        State update dict setting current_stage="error" and approval_status="denied".
    """
    error_detail = state.error or "Unknown error"
    return {
        "current_stage": "error",
        "approval_status": "denied",
        "agent_scratchpad": [AgentScratchpad(
            agent="error",
            action="handle_error",
            result=f"DENIED due to: {error_detail}",
        )],
    }
