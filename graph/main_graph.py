from __future__ import annotations

import os
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

from agents import (
    approval_node,
    claims_node,
    error_node,
    fraud_node,
    human_review_node,
    intake_node,
    router_node,
    support_node,
    underwriting_node,
)
from schema.state import GlobalState


# ── Routing functions ────────────────────────────────────────────────────────

def route_by_intent(
    state: GlobalState,
) -> Literal["claims", "underwriting", "support", "error"]:
    if state.error:
        return "error"
    return state.intent or "error"  # type: ignore[return-value]


def route_after_claims(state: GlobalState) -> Literal["fraud", "error"]:
    return "error" if state.error else "fraud"


def route_after_fraud(state: GlobalState) -> Literal["approval", "error"]:
    return "error" if (state.error or state.fraud_flags) else "approval"


def route_after_approval(state: GlobalState) -> Literal["human_review", "__end__"]:
    return "human_review" if state.requires_human_review else END  # type: ignore[return-value]


# ── Graph builder ────────────────────────────────────────────────────────────

def build_graph(checkpointer=None):
    """Assemble and compile the insurance workflow graph.

    Args:
        checkpointer: Optional LangGraph checkpointer for state persistence
            and human-in-the-loop resume. When ``None``, the checkpointer is
            selected automatically:

            * If the ``DATABASE_URL`` environment variable is set **and**
              ``ENV`` is not ``"test"``, a ``PostgresSaver`` backed by that
              connection string is used so that in-flight tickets (including
              those paused at ``human_review``) survive process restarts.
            * Otherwise a ``MemorySaver`` is used, which is safe for unit
              tests and local development without a database.

    Returns:
        Compiled StateGraph ready for invocation.
    """
    if checkpointer is None:
        database_url = os.environ.get("DATABASE_URL")
        if database_url and os.environ.get("ENV") != "test":
            checkpointer = PostgresSaver.from_conn_string(database_url)
        else:
            checkpointer = MemorySaver()

    builder = StateGraph(GlobalState)

    builder.add_node("intake", intake_node)
    builder.add_node("router", router_node)
    builder.add_node("claims", claims_node)
    builder.add_node("underwriting", underwriting_node)
    builder.add_node("fraud", fraud_node)
    builder.add_node("approval", approval_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("support", support_node)
    builder.add_node("error", error_node)

    builder.add_edge(START, "intake")
    builder.add_edge("intake", "router")
    builder.add_conditional_edges("router", route_by_intent, {
        "claims": "claims",
        "underwriting": "underwriting",
        "support": "support",
        "error": "error",
    })
    builder.add_conditional_edges("claims", route_after_claims, {
        "fraud": "fraud",
        "error": "error",
    })
    builder.add_conditional_edges("fraud", route_after_fraud, {
        "approval": "approval",
        "error": "error",
    })
    builder.add_conditional_edges("approval", route_after_approval, {
        "human_review": "human_review",
        END: END,
    })
    builder.add_edge("human_review", END)
    builder.add_edge("underwriting", END)
    builder.add_edge("support", END)
    builder.add_edge("error", END)

    return builder.compile(checkpointer=checkpointer)


# Module-level graph instance (MemorySaver) for use by FastAPI
graph = build_graph()
