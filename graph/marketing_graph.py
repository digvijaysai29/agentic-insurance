"""Marketing domain subgraph: lead scoring → segmentation → campaign offer.

Compiled as a standalone StateGraph and added as a single node in the main
supervisor graph.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.marketing import (
    marketing_campaign_node,
    marketing_lead_score_node,
    marketing_segment_node,
)
from schema.state import GlobalState


def _error_sink(state: GlobalState) -> dict:
    """Terminal node for internal marketing subgraph error routing."""
    return {"current_stage": "error"}


def build_marketing_graph() -> StateGraph:
    """Compile the marketing domain subgraph.

    Returns:
        Compiled StateGraph for the marketing domain.
    """
    builder = StateGraph(GlobalState)

    builder.add_node("lead_score", marketing_lead_score_node)
    builder.add_node("segment", marketing_segment_node)
    builder.add_node("campaign", marketing_campaign_node)
    builder.add_node("error_sink", _error_sink)

    builder.add_edge(START, "lead_score")
    builder.add_conditional_edges(
        "lead_score",
        lambda s: "error_sink" if s.error else "segment",
        {"segment": "segment", "error_sink": "error_sink"},
    )
    builder.add_conditional_edges(
        "segment",
        lambda s: "error_sink" if s.error else "campaign",
        {"campaign": "campaign", "error_sink": "error_sink"},
    )
    builder.add_edge("campaign", END)
    builder.add_edge("error_sink", END)

    return builder.compile()


marketing_graph = build_marketing_graph()
