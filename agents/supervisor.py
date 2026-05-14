"""Supervisor orchestrator: classifies incoming requests and routes to the
correct domain subgraph using the LangGraph Command API.

The supervisor is the single entry point after intake.  It returns a
``Command`` that names the target subgraph node and carries any state updates,
giving each domain full isolation and independent failure handling.
"""
from __future__ import annotations

from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Command

from schema.state import AgentScratchpad, GlobalState

_llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)

DomainLiteral = Literal[
    "claims", "underwriting", "billing",
    "marketing", "renewals", "onboarding", "support",
]

_SYSTEM = """\
You are the central orchestration supervisor for an autonomous insurance company.
Classify the incoming request into exactly one domain:

- claims      : filing or checking on an insurance claim, FNOL
- underwriting: risk assessment, policy quote, new policy evaluation
- billing     : invoice questions, payment processing, overdue balances, write-offs
- marketing   : lead generation, targeted offers, campaign interactions
- renewals    : policy renewal, expiring policy, lapse prevention
- onboarding  : new customer registration, KYC, first policy assignment
- support     : anything else — account updates, general inquiries, complaints

Respond with only the domain name, lowercase, no punctuation.
"""

_VALID_DOMAINS: frozenset[str] = frozenset(
    {"claims", "underwriting", "billing", "marketing", "renewals", "onboarding", "support"}
)


def supervisor_node(state: GlobalState) -> Command[DomainLiteral]:
    """LLM-powered supervisor that routes to a domain subgraph via Command.

    Args:
        state: Global state after intake; must contain at least one message.

    Returns:
        Command directing execution to the appropriate domain subgraph node,
        with ``domain`` and ``current_stage`` updated in shared state.
    """
    customer_text = str(state.messages[-1].content) if state.messages else ""

    if not customer_text:
        return Command(
            goto="error_node",
            update={
                "error": "Supervisor received empty message",
                "current_stage": "error",
                "agent_scratchpad": [AgentScratchpad(
                    agent="supervisor",
                    action="classify_domain",
                    result="ERROR: empty message",
                )],
            },
        )

    response = _llm.invoke([
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=customer_text),
    ])
    raw = response.content.strip().lower()
    domain = raw if raw in _VALID_DOMAINS else None

    if domain is None:
        return Command(
            goto="error_node",
            update={
                "error": f"Supervisor could not classify domain: {raw!r}",
                "current_stage": "error",
                "agent_scratchpad": [AgentScratchpad(
                    agent="supervisor",
                    action="classify_domain",
                    result=f"ERROR: unknown domain {raw!r}",
                )],
            },
        )

    return Command(
        goto=domain,
        update={
            "domain": domain,
            # Keep intent populated for backward-compat with existing claims path
            "intent": domain if domain in {"claims", "underwriting", "support"} else None,
            "current_stage": "routing",
            "agent_scratchpad": [AgentScratchpad(
                agent="supervisor",
                action="classify_domain",
                result=f"routed to {domain}",
            )],
        },
    )
