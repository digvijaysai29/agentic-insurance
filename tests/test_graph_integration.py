from datetime import date
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage

from schema.state import CustomerProfile, GlobalState


def _profile() -> CustomerProfile:
    return CustomerProfile(
        customer_id="C001",
        name="Jane Doe",
        policy_number="POL-001",
        policy_start_date=date(2024, 1, 1),
        policy_end_date=date(2025, 12, 31),
        coverage_limit=100_000.0,
        policy_type="auto",
    )


def _state(message: str, ticket_id: str = "T-INT") -> GlobalState:
    return GlobalState(
        ticket_id=ticket_id,
        customer_profile=_profile(),
        messages=[HumanMessage(content=message)],
    )


def test_small_claim_auto_approved_end_to_end(monkeypatch):
    """$5k claim: intake → router → claims → fraud (clean) → approval → approved."""
    import agents.router as router_mod
    import agents.claims as claims_mod
    import agents.fraud as fraud_mod

    monkeypatch.setattr(router_mod, "_llm", MagicMock(invoke=lambda m: AIMessage(content="claims")))
    monkeypatch.setattr(claims_mod, "lookup_policy", lambda _: _profile())
    monkeypatch.setattr(fraud_mod, "search_fraud_patterns", lambda *a, **k: [])

    from graph.main_graph import build_graph
    g = build_graph()
    config = {"configurable": {"thread_id": "T-SMALL"}}
    final = g.invoke(_state("claim $5000 car damage", "T-SMALL"), config=config)

    assert final["approval_status"] == "approved"
    assert final["current_stage"] == "resolved"
    assert final["claim_amount"] == 5000.0
    assert any(e["agent"] == "intake" for e in final["agent_scratchpad"])
    assert any(e["agent"] == "approval" for e in final["agent_scratchpad"])


def test_support_intent_resolves(monkeypatch):
    """Support intent: intake → router → support → resolved."""
    import agents.router as router_mod
    import agents.support as support_mod
    from langchain_core.messages import AIMessage as AI

    monkeypatch.setattr(router_mod, "_llm", MagicMock(invoke=lambda m: AI(content="support")))
    monkeypatch.setattr(
        support_mod, "_llm",
        MagicMock(invoke=lambda m: AI(content="Please call 1-800-INSURE for billing help.")),
    )

    from graph.main_graph import build_graph
    g = build_graph()
    config = {"configurable": {"thread_id": "T-SUPPORT"}}
    final = g.invoke(_state("What is my billing date?", "T-SUPPORT"), config=config)

    assert final["current_stage"] == "resolved"
    assert final["intent"] == "support"


def test_fraud_flagged_claim_denied(monkeypatch):
    """Fraud-flagged claim should end at error node with approval_status=denied."""
    import agents.router as router_mod
    import agents.claims as claims_mod
    import agents.fraud as fraud_mod

    monkeypatch.setattr(router_mod, "_llm", MagicMock(invoke=lambda m: AIMessage(content="claims")))
    monkeypatch.setattr(claims_mod, "lookup_policy", lambda _: _profile())
    monkeypatch.setattr(fraud_mod, "search_fraud_patterns", lambda *a, **k: ["suspicious_pattern"])

    from graph.main_graph import build_graph
    g = build_graph()
    config = {"configurable": {"thread_id": "T-FRAUD-INT"}}
    final = g.invoke(_state("claim $3000 flood damage", "T-FRAUD-INT"), config=config)

    assert final["current_stage"] == "error"
    assert final["approval_status"] == "denied"


def test_large_claim_pauses_for_human_review(monkeypatch):
    """$15k claim: approval_node flags it; graph pauses at human_review_node."""
    import agents.router as router_mod
    import agents.claims as claims_mod
    import agents.fraud as fraud_mod
    from langgraph.errors import GraphInterrupt
    import pytest

    monkeypatch.setattr(router_mod, "_llm", MagicMock(invoke=lambda m: AIMessage(content="claims")))
    monkeypatch.setattr(claims_mod, "lookup_policy", lambda _: _profile())
    monkeypatch.setattr(fraud_mod, "search_fraud_patterns", lambda *a, **k: [])

    from graph.main_graph import build_graph
    g = build_graph()
    config = {"configurable": {"thread_id": "T-HITL"}}

    with pytest.raises(GraphInterrupt):
        g.invoke(_state("claim $15000 home damage", "T-HITL"), config=config)
