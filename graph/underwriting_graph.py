"""Underwriting domain subgraph: risk scoring → policy writing → compliance check.

Compiled as a standalone StateGraph and added as a single node in the main
supervisor graph.
"""
from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from agents.compliance import compliance_node
from agents.policy_writer import policy_writer_node
from agents.underwriting import underwriting_node
from schema.state import GlobalState


def _route_after_underwriting(state: GlobalState) -> Literal["policy_writer", "error_sink"]:
    return "error_sink" if state.error else "policy_writer"


def _route_after_policy_writer(state: GlobalState) -> Literal["compliance", "error_sink"]:
    return "error_sink" if state.error else "compliance"


def _error_sink(state: GlobalState) -> dict:
    """Terminal node for internal underwriting subgraph error routing."""
    return {"current_stage": "error"}


def build_underwriting_graph() -> StateGraph:
    """Compile the underwriting domain subgraph.

    Returns:
        Compiled StateGraph for the underwriting domain.
    """
    builder = StateGraph(GlobalState)

    builder.add_node("underwriting", underwriting_node)
    builder.add_node("policy_writer", policy_writer_node)
    builder.add_node("compliance", compliance_node)
    builder.add_node("error_sink", _error_sink)

    builder.add_edge(START, "underwriting")
    builder.add_conditional_edges("underwriting", _route_after_underwriting, {
        "policy_writer": "policy_writer",
        "error_sink": "error_sink",
    })
    builder.add_conditional_edges("policy_writer", _route_after_policy_writer, {
        "compliance": "compliance",
        "error_sink": "error_sink",
    })
    builder.add_edge("compliance", END)
    builder.add_edge("error_sink", END)

    return builder.compile()


underwriting_graph = build_underwriting_graph()
