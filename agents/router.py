from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from schema.state import AgentScratchpad, GlobalState

_llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)

_SYSTEM = (
    "You are an insurance triage agent. Classify the customer's message into exactly one of:\n"
    "- claims: customer wants to file or check on an insurance claim\n"
    "- underwriting: customer wants a quote, policy evaluation, or risk assessment\n"
    "- support: anything else (billing questions, account updates, general inquiries)\n\n"
    "Respond with only the category name, lowercase."
)


def router_node(state: GlobalState) -> dict:
    """Classify the customer intent from the latest message.

    Args:
        state: Global state containing messages from the customer.

    Returns:
        State update dict with intent and updated current_stage.
    """
    customer_text = str(state.messages[-1].content) if state.messages else ""
    if not customer_text:
        return {
            "error": "Empty message for routing",
            "current_stage": "error",
            "agent_scratchpad": [AgentScratchpad(
                agent="router", action="classify_intent", result="ERROR: empty message",
            )],
        }

    response = _llm.invoke([
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=customer_text),
    ])
    raw = response.content.strip().lower()
    intent = raw if raw in {"claims", "underwriting", "support"} else None

    if intent is None:
        return {
            "error": f"Unrecognized intent: {raw!r}",
            "current_stage": "error",
            "agent_scratchpad": [AgentScratchpad(
                agent="router", action="classify_intent", result=f"ERROR: unknown intent {raw!r}",
            )],
        }

    return {
        "intent": intent,
        "current_stage": intent,
        "agent_scratchpad": [AgentScratchpad(
            agent="router", action="classify_intent", result=intent,
        )],
    }
