"""Claims domain subgraph: validates coverage → fraud detection → approval →
optional human review.

Compiled as a standalone StateGraph and added as a single node in the main
supervisor graph.
"""
from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from agents.approval import approval_node
from agents.claims import claims_node
from agents.fraud import fraud_node
from agents.human_review import human_review_node
from schema.state import GlobalState


def _route_after_claims(state: GlobalState) -> Literal["fraud", "error_sink"]:
    return "error_sink" if state.error else "fraud"


def _route_after_fraud(state: GlobalState) -> Literal["approval", "error_sink"]:
    return "error_sink" if (state.error or state.fraud_flags) else "approval"


def _route_after_approval(state: GlobalState) -> Literal["human_review", "__end__"]:
    return "human_review" if state.requires_human_review else END  # type: ignore[return-value]


def _error_sink(state: GlobalState) -> dict:
    """Terminal node for internal claims subgraph error routing."""
    return {"current_stage": "error"}


def build_claims_graph() -> StateGraph:
    """Compile the claims domain subgraph.

    Returns:
        Compiled StateGraph for the claims domain.
    """
    builder = StateGraph(GlobalState)

    builder.add_node("claims", claims_node)
    builder.add_node("fraud", fraud_node)
    builder.add_node("approval", approval_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("error_sink", _error_sink)

    builder.add_edge(START, "claims")
    builder.add_conditional_edges("claims", _route_after_claims, {
        "fraud": "fraud",
        "error_sink": "error_sink",
    })
    builder.add_conditional_edges("fraud", _route_after_fraud, {
        "approval": "approval",
        "error_sink": "error_sink",
    })
    builder.add_conditional_edges("approval", _route_after_approval, {
        "human_review": "human_review",
        END: END,
    })
    builder.add_edge("human_review", END)
    builder.add_edge("error_sink", END)

    return builder.compile()


claims_graph = build_claims_graph()
