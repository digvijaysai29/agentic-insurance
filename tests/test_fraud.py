from datetime import date

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


def _state(claim_amount: float = 3000.0) -> GlobalState:
    return GlobalState(
        ticket_id="T-FRAUD",
        claim_amount=claim_amount,
        customer_profile=_profile(),
    )


def test_fraud_clean_claim(monkeypatch):
    import agents.fraud as fraud_mod
    monkeypatch.setattr(fraud_mod, "search_fraud_patterns", lambda *a, **k: [])

    result = fraud_mod.fraud_node(_state())
    assert result["fraud_flags"] == []
    assert result["current_stage"] == "approval"


def test_fraud_flagged_claim(monkeypatch):
    import agents.fraud as fraud_mod
    monkeypatch.setattr(fraud_mod, "search_fraud_patterns", lambda *a, **k: ["pattern_A", "pattern_B"])

    result = fraud_mod.fraud_node(_state())
    assert len(result["fraud_flags"]) == 2
    assert result["current_stage"] == "error"


def test_fraud_missing_data():
    from agents.fraud import fraud_node
    state = GlobalState(ticket_id="T-FRAUD-NODATA")
    result = fraud_node(state)
    assert result.get("error") is not None
    assert result["current_stage"] == "error"


def test_fraud_missing_claim_amount():
    from agents.fraud import fraud_node
    state = GlobalState(ticket_id="T-FRAUD-NOAMOUNT", customer_profile=_profile())
    result = fraud_node(state)
    assert result.get("error") is not None
