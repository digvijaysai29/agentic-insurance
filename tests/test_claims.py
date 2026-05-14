from datetime import date
from unittest.mock import MagicMock

from langchain_core.messages import HumanMessage

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


def _state(message: str = "I need to claim $5,000 for car damage") -> GlobalState:
    return GlobalState(
        ticket_id="T-CLAIMS",
        customer_profile=_profile(),
        messages=[HumanMessage(content=message)],
    )


def test_claims_extracts_amount(monkeypatch):
    import agents.claims as claims_mod
    monkeypatch.setattr(claims_mod, "lookup_policy", lambda _: _profile())

    result = claims_mod.claims_node(_state("I need to claim $5,000 for car damage"))
    assert result["claim_amount"] == 5000.0
    assert result["current_stage"] == "fraud"


def test_claims_error_when_policy_not_found(monkeypatch):
    import agents.claims as claims_mod
    monkeypatch.setattr(claims_mod, "lookup_policy", lambda _: None)

    result = claims_mod.claims_node(_state())
    assert result.get("error") is not None
    assert result["current_stage"] == "error"


def test_claims_error_without_profile():
    from agents.claims import claims_node
    state = GlobalState(ticket_id="T-NO-PROFILE")
    result = claims_node(state)
    assert result.get("error") is not None
    assert result["current_stage"] == "error"


def test_claims_zero_amount_when_no_dollar_value(monkeypatch):
    import agents.claims as claims_mod
    monkeypatch.setattr(claims_mod, "lookup_policy", lambda _: _profile())

    result = claims_mod.claims_node(_state("My car was damaged in a storm"))
    assert result["claim_amount"] == 0.0
