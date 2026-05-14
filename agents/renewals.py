"""Renewals agent pipeline: expiry scanning → negotiation → auto-renewal.

Three nodes wired in ``graph/renewals_graph.py``:
  1. ``renewals_expiry_node``   — checks days until policy expiry
  2. ``renewals_negotiate_node``— generates a renewal offer via LLM
  3. ``renewals_autorenew_node``— executes auto-renewal or marks as lapsed
"""
from __future__ import annotations

import json
from datetime import date

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from schema.state import AgentScratchpad, GlobalState, RenewalState

_llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0.1)

_NEGOTIATE_SYSTEM = """\
You are an insurance renewal specialist. Given a customer's expiring policy,
generate a renewal offer as JSON:
{
  "renewal_offer_amount": <float — annual premium for the renewed policy>,
  "negotiation_notes": "<1-2 sentences explaining the offer rationale>"
}
Rules:
- If risk_score > 0.6, increase premium by 10%.
- If customer has no fraud flags, offer a 5% loyalty discount.
- Base premium = coverage_limit * 0.015.
Respond ONLY with valid JSON, no markdown.
"""

_AUTO_RENEW_THRESHOLD_DAYS = 60


def renewals_expiry_node(state: GlobalState) -> dict:
    """Calculate days until policy expiry and initialise renewal state.

    Args:
        state: Global state with customer_profile.

    Returns:
        State update with renewal.days_until_expiry set.
    """
    if not state.customer_profile:
        return _error("renewals_expiry", "No customer profile for expiry check")

    today = date.today()
    days_left = (state.customer_profile.policy_end_date - today).days

    renewal = RenewalState(
        days_until_expiry=days_left,
        renewal_status="pending",
    )

    return {
        "renewal": renewal,
        "current_stage": "renewals",
        "agent_scratchpad": [AgentScratchpad(
            agent="renewals_expiry",
            action="check_expiry",
            result=f"OK: {days_left} days until expiry",
        )],
    }


def renewals_negotiate_node(state: GlobalState) -> dict:
    """Generate a personalised renewal offer.

    Args:
        state: Global state with customer_profile, risk_score, fraud_flags,
               and renewal sub-state.

    Returns:
        State update with renewal offer amount and negotiation notes.
    """
    if not state.customer_profile:
        return _error("renewals_negotiate", "No customer profile for negotiation")
    if not state.renewal:
        return _error("renewals_negotiate", "No renewal state for negotiation")

    profile = state.customer_profile
    prompt = (
        f"Policy type: {profile.policy_type}\n"
        f"Coverage limit: ${profile.coverage_limit:,.2f}\n"
        f"Risk score: {state.risk_score or 0.3:.3f}\n"
        f"Fraud flags: {state.fraud_flags or []}\n"
        f"Days until expiry: {state.renewal.days_until_expiry}\n"
    )

    response = _llm.invoke([
        SystemMessage(content=_NEGOTIATE_SYSTEM),
        HumanMessage(content=prompt),
    ])

    try:
        data = json.loads(response.content.strip())
    except json.JSONDecodeError:
        data = {
            "renewal_offer_amount": profile.coverage_limit * 0.015,
            "negotiation_notes": "Standard renewal rate applied.",
        }

    updated = RenewalState(
        **state.renewal.model_dump(exclude={"renewal_offer_amount", "negotiation_notes"}),
        renewal_offer_amount=float(data.get("renewal_offer_amount", 0.0)),
        negotiation_notes=str(data.get("negotiation_notes", "")),
    )

    return {
        "renewal": updated,
        "current_stage": "negotiation",
        "agent_scratchpad": [AgentScratchpad(
            agent="renewals_negotiate",
            action="generate_offer",
            result=f"OK: offer=${updated.renewal_offer_amount:,.2f}",
        )],
    }


def renewals_autorenew_node(state: GlobalState) -> dict:
    """Execute auto-renewal for policies expiring within the threshold.

    Policies with more days remaining than ``_AUTO_RENEW_THRESHOLD_DAYS``
    are deferred.

    Args:
        state: Global state with renewal sub-state and offer amount.

    Returns:
        State update with renewal_status finalised.
    """
    if not state.renewal:
        return _error("renewals_autorenew", "No renewal state for auto-renewal")

    days_left = state.renewal.days_until_expiry or 999
    if days_left > _AUTO_RENEW_THRESHOLD_DAYS:
        return {
            "current_stage": "audit",
            "agent_scratchpad": [AgentScratchpad(
                agent="renewals_autorenew",
                action="auto_renew",
                result=f"DEFERRED: {days_left} days remaining",
            )],
        }

    if days_left <= 0:
        status = "lapsed"
        result = "LAPSED: policy expired"
    else:
        status = "auto_renewed"
        result = f"AUTO_RENEWED: offer=${state.renewal.renewal_offer_amount:,.2f}"

    updated = RenewalState(
        **state.renewal.model_dump(exclude={"renewal_status"}),
        renewal_status=status,  # type: ignore[arg-type]
    )

    return {
        "renewal": updated,
        "current_stage": "audit",
        "agent_scratchpad": [AgentScratchpad(
            agent="renewals_autorenew",
            action="auto_renew",
            result=result,
        )],
    }


def _error(agent: str, msg: str) -> dict:
    return {
        "error": msg,
        "current_stage": "error",
        "agent_scratchpad": [AgentScratchpad(
            agent=agent,
            action="renewals_op",
            result=f"ERROR: {msg}",
        )],
    }
