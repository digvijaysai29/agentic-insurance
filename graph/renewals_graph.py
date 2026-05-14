"""Renewals domain subgraph: expiry check → offer negotiation → auto-renewal.

Compiled as a standalone StateGraph and added as a single node in the main
supervisor graph.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.renewals import (
    renewals_autorenew_node,
    renewals_expiry_node,
    renewals_negotiate_node,
)
from schema.state import GlobalState


def _error_sink(state: GlobalState) -> dict:
    """Terminal node for internal renewals subgraph error routing."""
    return {"current_stage": "error"}


def build_renewals_graph() -> StateGraph:
    """Compile the renewals domain subgraph.

    Returns:
        Compiled StateGraph for the renewals domain.
    """
    builder = StateGraph(GlobalState)

    builder.add_node("expiry_check", renewals_expiry_node)
    builder.add_node("negotiate", renewals_negotiate_node)
    builder.add_node("auto_renew", renewals_autorenew_node)
    builder.add_node("error_sink", _error_sink)

    builder.add_edge(START, "expiry_check")
    builder.add_conditional_edges(
        "expiry_check",
        lambda s: "error_sink" if s.error else "negotiate",
        {"negotiate": "negotiate", "error_sink": "error_sink"},
    )
    builder.add_conditional_edges(
        "negotiate",
        lambda s: "error_sink" if s.error else "auto_renew",
        {"auto_renew": "auto_renew", "error_sink": "error_sink"},
    )
    builder.add_edge("auto_renew", END)
    builder.add_edge("error_sink", END)

    return builder.compile()


renewals_graph = build_renewals_graph()
