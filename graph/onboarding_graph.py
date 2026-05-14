"""Onboarding domain subgraph: KYC → risk profiling → policy assignment.

Compiled as a standalone StateGraph and added as a single node in the main
supervisor graph.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.onboarding import (
    onboarding_kyc_node,
    onboarding_policy_assign_node,
    onboarding_risk_profile_node,
)
from schema.state import GlobalState


def _error_sink(state: GlobalState) -> dict:
    """Terminal node for internal onboarding subgraph error routing."""
    return {"current_stage": "error"}


def build_onboarding_graph() -> StateGraph:
    """Compile the onboarding domain subgraph.

    Returns:
        Compiled StateGraph for the onboarding domain.
    """
    builder = StateGraph(GlobalState)

    builder.add_node("kyc", onboarding_kyc_node)
    builder.add_node("risk_profile", onboarding_risk_profile_node)
    builder.add_node("policy_assign", onboarding_policy_assign_node)
    builder.add_node("error_sink", _error_sink)

    builder.add_edge(START, "kyc")
    builder.add_conditional_edges(
        "kyc",
        lambda s: "error_sink" if s.error else "risk_profile",
        {"risk_profile": "risk_profile", "error_sink": "error_sink"},
    )
    builder.add_conditional_edges(
        "risk_profile",
        lambda s: "error_sink" if s.error else "policy_assign",
        {"policy_assign": "policy_assign", "error_sink": "error_sink"},
    )
    builder.add_edge("policy_assign", END)
    builder.add_edge("error_sink", END)

    return builder.compile()


onboarding_graph = build_onboarding_graph()
