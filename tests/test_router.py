from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from schema.state import GlobalState


def _state(text: str) -> GlobalState:
    return GlobalState(ticket_id="T-ROUTER", messages=[HumanMessage(content=text)])


def test_router_classifies_claims(monkeypatch):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="claims")
    import agents.router as router_mod
    monkeypatch.setattr(router_mod, "_llm", mock_llm)

    result = router_mod.router_node(_state("I want to file a claim for my car"))
    assert result["intent"] == "claims"
    assert result["current_stage"] == "claims"
    assert len(result["agent_scratchpad"]) == 1


def test_router_classifies_underwriting(monkeypatch):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="underwriting")
    import agents.router as router_mod
    monkeypatch.setattr(router_mod, "_llm", mock_llm)

    result = router_mod.router_node(_state("I need a quote for my home"))
    assert result["intent"] == "underwriting"


def test_router_classifies_support(monkeypatch):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="support")
    import agents.router as router_mod
    monkeypatch.setattr(router_mod, "_llm", mock_llm)

    result = router_mod.router_node(_state("What is my billing date?"))
    assert result["intent"] == "support"


def test_router_error_on_unknown_intent(monkeypatch):
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="gibberish")
    import agents.router as router_mod
    monkeypatch.setattr(router_mod, "_llm", mock_llm)

    result = router_mod.router_node(_state("hello"))
    assert result.get("error") is not None
    assert result["current_stage"] == "error"


def test_router_error_on_empty_messages():
    from agents.router import router_node
    state = GlobalState(ticket_id="T-ROUTER-EMPTY")
    result = router_node(state)
    assert result.get("error") is not None
