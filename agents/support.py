from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, SystemMessage

from schema.state import AgentScratchpad, GlobalState

_llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0.3)

_SYSTEM = (
    "You are a helpful insurance support agent. Answer customer questions concisely and accurately. "
    "If you don't know something specific to their policy, ask them to call the main support line."
)


def support_node(state: GlobalState) -> dict:
    """Generate a support response using the LLM.

    Args:
        state: Global state with messages.

    Returns:
        State update dict with a new assistant message and current_stage="resolved".
    """
    all_messages = [SystemMessage(content=_SYSTEM)] + list(state.messages)
    response = _llm.invoke(all_messages)

    return {
        "current_stage": "resolved",
        "messages": [AIMessage(content=response.content)],
        "agent_scratchpad": [AgentScratchpad(
            agent="support",
            action="generate_response",
            result=f"response generated ({len(response.content)} chars)",
        )],
    }
