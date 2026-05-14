"""Billing domain subgraph: invoice generation → payment check → collections.

Compiled as a standalone StateGraph and added as a single node in the main
supervisor graph.
"""
from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from agents.billing import (
    billing_collections_node,
    billing_invoice_node,
    billing_payment_node,
)
from agents.compliance import compliance_node
from schema.state import GlobalState


def _route_after_payment(
    state: GlobalState,
) -> Literal["collections", "compliance", "error_sink"]:
    if state.error:
        return "error_sink"
    if state.billing and state.billing.payment_status == "overdue":
        return "collections"
    return "compliance"


def _route_after_collections(state: GlobalState) -> Literal["compliance", "error_sink"]:
    return "error_sink" if state.error else "compliance"


def _error_sink(state: GlobalState) -> dict:
    """Terminal node for internal billing subgraph error routing."""
    return {"current_stage": "error"}


def build_billing_graph() -> StateGraph:
    """Compile the billing domain subgraph.

    Returns:
        Compiled StateGraph for the billing domain.
    """
    builder = StateGraph(GlobalState)

    builder.add_node("invoice", billing_invoice_node)
    builder.add_node("payment", billing_payment_node)
    builder.add_node("collections", billing_collections_node)
    builder.add_node("compliance", compliance_node)
    builder.add_node("error_sink", _error_sink)

    builder.add_edge(START, "invoice")
    builder.add_edge("invoice", "payment")
    builder.add_conditional_edges("payment", _route_after_payment, {
        "collections": "collections",
        "compliance": "compliance",
        "error_sink": "error_sink",
    })
    builder.add_conditional_edges("collections", _route_after_collections, {
        "compliance": "compliance",
        "error_sink": "error_sink",
    })
    builder.add_edge("compliance", END)
    builder.add_edge("error_sink", END)

    return builder.compile()


billing_graph = build_billing_graph()
