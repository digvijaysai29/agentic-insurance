"""Policy Writer agent: drafts a structured insurance policy document after
underwriting has produced a risk score.

The agent uses the LLM to generate human-readable terms and exclusions, then
wraps them in a validated ``PolicyDocument`` Pydantic model stored in state.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, timedelta

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from schema.state import AgentScratchpad, GlobalState, PolicyDocument

_llm = ChatAnthropic(model="claude-sonnet-4-5-20251001", temperature=0.2)

_SYSTEM = """\
You are an expert insurance policy writer. Given customer details and a risk score,
produce a JSON object with these exact fields:
{
  "annual_premium": <float — computed as coverage_limit * risk_score * 0.02>,
  "terms_summary": "<2-3 sentence plain-English summary of coverage>",
  "exclusions": ["<exclusion 1>", "<exclusion 2>", ...]
}

Rules:
- Higher risk scores (>0.7) must add at least 2 exclusions.
- Always include 'Pre-existing conditions not disclosed at onboarding' for health policies.
- Respond ONLY with valid JSON, no markdown fences.
"""

_HIGH_PREMIUM_THRESHOLD = 50_000.0


def policy_writer_node(state: GlobalState) -> dict:
    """Draft and store a policy document from underwriting outputs.

    Interrupts for human approval when the computed annual premium exceeds
    the high-premium threshold.

    Args:
        state: Global state containing customer_profile and risk_score.

    Returns:
        State update dict with policy_document set and current_stage advanced.
    """
    if not state.customer_profile:
        return _error("No customer profile available for policy writing")
    if state.risk_score is None:
        return _error("No risk score available for policy writing")

    profile = state.customer_profile
    risk = state.risk_score

    prompt = (
        f"Policy type: {profile.policy_type}\n"
        f"Coverage limit: ${profile.coverage_limit:,.2f}\n"
        f"Risk score: {risk:.3f}\n"
        f"Customer ID: {profile.customer_id}\n"
    )

    response = _llm.invoke([
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=prompt),
    ])

    try:
        data = json.loads(response.content.strip())
    except json.JSONDecodeError as exc:
        return _error(f"Policy writer LLM returned invalid JSON: {exc}")

    annual_premium = float(data.get("annual_premium", 0.0))

    if annual_premium > _HIGH_PREMIUM_THRESHOLD:
        interrupt({
            "reason": "high_premium_policy",
            "annual_premium": annual_premium,
            "customer_id": profile.customer_id,
            "message": (
                f"Policy for {profile.customer_id} has premium ${annual_premium:,.2f} "
                f"exceeding threshold ${_HIGH_PREMIUM_THRESHOLD:,.2f}. Approve issuance?"
            ),
        })

    today = date.today()
    policy_doc = PolicyDocument(
        policy_number=f"POL-{uuid.uuid4().hex[:8].upper()}",
        policy_type=profile.policy_type,
        customer_id=profile.customer_id,
        coverage_limit=profile.coverage_limit,
        annual_premium=annual_premium,
        effective_date=today,
        expiry_date=today + timedelta(days=365),
        terms_summary=str(data.get("terms_summary", "")),
        exclusions=list(data.get("exclusions", [])),
    )

    return {
        "policy_document": policy_doc,
        "current_stage": "compliance",
        "agent_scratchpad": [AgentScratchpad(
            agent="policy_writer",
            action="draft_policy",
            result=f"OK: issued {policy_doc.policy_number}, premium=${annual_premium:,.2f}",
        )],
    }


def _error(msg: str) -> dict:
    return {
        "error": msg,
        "current_stage": "error",
        "agent_scratchpad": [AgentScratchpad(
            agent="policy_writer",
            action="draft_policy",
            result=f"ERROR: {msg}",
        )],
    }
