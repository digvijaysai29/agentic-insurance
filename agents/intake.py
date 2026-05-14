from schema.state import AgentScratchpad, GlobalState


def intake_node(state: GlobalState) -> dict:
    """Validate the incoming request and initialize the workflow.

    Args:
        state: Current global state with ticket_id and initial messages.

    Returns:
        State update dict with current_stage set to "routing" or error fields.
    """
    if not state.ticket_id:
        return {
            "error": "Missing ticket_id",
            "current_stage": "error",
            "agent_scratchpad": [AgentScratchpad(
                agent="intake", action="validate_request", result="ERROR: Missing ticket_id",
            )],
        }

    if not state.messages:
        return {
            "error": "No messages provided",
            "current_stage": "error",
            "agent_scratchpad": [AgentScratchpad(
                agent="intake", action="validate_request", result="ERROR: No messages",
            )],
        }

    return {
        "current_stage": "routing",
        "agent_scratchpad": [AgentScratchpad(
            agent="intake",
            action="validate_request",
            result=f"OK: ticket {state.ticket_id} received with {len(state.messages)} message(s)",
        )],
    }
