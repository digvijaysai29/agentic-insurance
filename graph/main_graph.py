"""Main supervisor graph: intake → supervisor → domain subgraph → end.

The supervisor receives the customer request after intake, classifies it into
one of 7 domains using the LangGraph Command API, and dispatches to the
corresponding compiled subgraph node.  Each subgraph handles its own internal
routing and error recovery.

Architecture::

    intake ──→ supervisor ──→ claims        ──→ END
                          ├──→ underwriting  ──→ END
                          ├──→ billing       ──→ END
                          ├──→ marketing     ──→ END
                          ├──→ renewals      ──→ END
                          ├──→ onboarding    ──→ END
                          ├──→ support       ──→ END
                          └──→ error_node    ──→ END
"""
from __future__ import annotations

import os

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph

from agents.error import error_node
from agents.intake import intake_node
from agents.supervisor import supervisor_node
from agents.support import support_node
from graph.billing_graph import billing_graph
from graph.claims_graph import claims_graph
from graph.marketing_graph import marketing_graph
from graph.onboarding_graph import onboarding_graph
from graph.renewals_graph import renewals_graph
from graph.underwriting_graph import underwriting_graph
from schema.state import GlobalState


def build_graph(checkpointer=None):
    """Assemble and compile the full autonomous insurance supervisor graph.

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

    # ── Entry nodes ───────────────────────────────────────────────────────────
    builder.add_node("intake", intake_node)
    builder.add_node("supervisor", supervisor_node)

    # ── Domain subgraph nodes ─────────────────────────────────────────────────
    builder.add_node("claims", claims_graph)
    builder.add_node("underwriting", underwriting_graph)
    builder.add_node("billing", billing_graph)
    builder.add_node("marketing", marketing_graph)
    builder.add_node("renewals", renewals_graph)
    builder.add_node("onboarding", onboarding_graph)

    # ── Support and error leaf nodes ──────────────────────────────────────────
    builder.add_node("support", support_node)
    builder.add_node("error_node", error_node)

    # ── Edges ─────────────────────────────────────────────────────────────────
    builder.add_edge(START, "intake")
    builder.add_edge("intake", "supervisor")

    # supervisor_node returns Command(goto=<domain>) so routing is implicit.
    # All domain nodes and leaf nodes terminate to END.
    for domain in ("claims", "underwriting", "billing", "marketing",
                   "renewals", "onboarding", "support", "error_node"):
        builder.add_edge(domain, END)

    return builder.compile(checkpointer=checkpointer)


# Module-level graph instance (MemorySaver) for use by FastAPI
graph = build_graph()
