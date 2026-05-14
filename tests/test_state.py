from datetime import date

import pytest
from pydantic import ValidationError

from schema.state import AgentScratchpad, CustomerProfile, GlobalState


def _make_profile(**kwargs) -> CustomerProfile:
    defaults = dict(
        customer_id="C001",
        name="Jane Doe",
        policy_number="POL-001",
        policy_start_date=date(2024, 1, 1),
        policy_end_date=date(2025, 12, 31),
        coverage_limit=100_000.0,
        policy_type="auto",
    )
    return CustomerProfile(**{**defaults, **kwargs})


def test_global_state_defaults():
    state = GlobalState(ticket_id="T-001")
    assert state.current_stage == "intake"
    assert state.agent_scratchpad == []
    assert state.messages == []
    assert state.intent is None
    assert state.error is None
    assert state.requires_human_review is False


def test_customer_profile_valid():
    profile = _make_profile()
    assert profile.policy_type == "auto"
    assert profile.coverage_limit == 100_000.0


def test_customer_profile_invalid_type():
    with pytest.raises(ValidationError):
        _make_profile(policy_type="boat")


def test_global_state_rejects_invalid_stage():
    with pytest.raises(ValidationError):
        GlobalState(ticket_id="T-002", current_stage="unknown_stage")


def test_scratchpad_reducer_append():
    """Validate the operator.add reducer semantics for agent_scratchpad."""
    state = GlobalState(ticket_id="T-003")
    entry = AgentScratchpad(agent="intake", action="validate", result="OK")
    merged = state.agent_scratchpad + [entry]
    assert len(merged) == 1
    assert merged[0].agent == "intake"
