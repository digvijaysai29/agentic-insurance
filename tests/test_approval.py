from schema.state import GlobalState


def test_approval_auto_approves_under_threshold():
    from agents.approval import approval_node
    state = GlobalState(ticket_id="T-APPROVE", claim_amount=5_000.0)
    result = approval_node(state)
    assert result["approval_status"] == "approved"
    assert result["requires_human_review"] is False
    assert result["current_stage"] == "resolved"


def test_approval_requires_human_review_over_threshold():
    from agents.approval import approval_node
    state = GlobalState(ticket_id="T-APPROVE-BIG", claim_amount=15_000.0)
    result = approval_node(state)
    assert result["approval_status"] == "human_required"
    assert result["requires_human_review"] is True
    assert result["current_stage"] == "human_review"
    assert result["human_review_reason"] is not None


def test_approval_exactly_at_threshold_auto_approves():
    from agents.approval import approval_node
    state = GlobalState(ticket_id="T-APPROVE-EXACT", claim_amount=10_000.0)
    result = approval_node(state)
    assert result["approval_status"] == "approved"
    assert result["requires_human_review"] is False


def test_approval_zero_amount_auto_approves():
    from agents.approval import approval_node
    state = GlobalState(ticket_id="T-APPROVE-ZERO", claim_amount=0.0)
    result = approval_node(state)
    assert result["approval_status"] == "approved"


def test_route_after_approval_goes_to_human_review():
    from graph.main_graph import route_after_approval
    state = GlobalState(ticket_id="T-ROUTE", requires_human_review=True)
    assert route_after_approval(state) == "human_review"


def test_route_after_approval_goes_to_end():
    from langgraph.graph import END
    from graph.main_graph import route_after_approval
    state = GlobalState(ticket_id="T-ROUTE-END", requires_human_review=False)
    assert route_after_approval(state) == END
