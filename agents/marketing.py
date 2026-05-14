"""Marketing agent pipeline: lead scoring → customer segmentation → campaign
offer generation.

Three nodes wired in ``graph/marketing_graph.py``:
  1. ``marketing_lead_score_node`` — scores the customer based on profile signals
  2. ``marketing_segment_node``    — assigns a segment from the lead score
  3. ``marketing_campaign_node``   — generates a targeted offer for the segment
"""
from __future__ import annotations

import json
import uuid

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from schema.state import AgentScratchpad, GlobalState, MarketingState

_llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0.3)

_OFFER_SYSTEM = """\
You are an insurance marketing specialist. Given a customer segment and policy details,
generate a compelling, personalised offer as a single JSON object:
{
  "offer": "<1-2 sentence personalised offer text>",
  "channel": "<email|sms|push|agent_call>"
}
Rules:
- high_value   → premium bundle offer via email
- mid_tier     → loyalty discount via email or sms
- at_risk      → retention offer via agent_call or sms
- new_prospect → welcome offer via email
Respond ONLY with valid JSON, no markdown.
"""


def marketing_lead_score_node(state: GlobalState) -> dict:
    """Compute a lead score (0.0–1.0) from the customer profile.

    Scoring heuristic (production would query CRM/CDP):
    - policy_type life/health: +0.3
    - coverage_limit > 100 000: +0.2
    - renewal days_until_expiry < 30: +0.3
    - baseline: 0.2

    Args:
        state: Global state with customer_profile.

    Returns:
        State update with marketing.lead_score populated.
    """
    if not state.customer_profile:
        return _error("marketing_lead_score", "No customer profile for lead scoring")

    profile = state.customer_profile
    score = 0.2
    if profile.policy_type in {"life", "health"}:
        score += 0.3
    if profile.coverage_limit > 100_000:
        score += 0.2
    if state.renewal and state.renewal.days_until_expiry is not None:
        if state.renewal.days_until_expiry < 30:
            score += 0.3
    score = min(score, 1.0)

    mkt = MarketingState(lead_score=round(score, 3))

    return {
        "marketing": mkt,
        "current_stage": "lead_scoring",
        "agent_scratchpad": [AgentScratchpad(
            agent="marketing_lead_score",
            action="score_lead",
            result=f"OK: lead_score={score:.3f}",
        )],
    }


def marketing_segment_node(state: GlobalState) -> dict:
    """Assign a customer segment based on lead score.

    Thresholds:
    - score >= 0.8 → high_value
    - score >= 0.5 → mid_tier
    - score >= 0.3 → at_risk
    - score <  0.3 → new_prospect

    Args:
        state: Global state with marketing.lead_score.

    Returns:
        State update with marketing.customer_segment set.
    """
    if not state.marketing or state.marketing.lead_score is None:
        return _error("marketing_segment", "No lead score for segmentation")

    score = state.marketing.lead_score
    if score >= 0.8:
        segment = "high_value"
    elif score >= 0.5:
        segment = "mid_tier"
    elif score >= 0.3:
        segment = "at_risk"
    else:
        segment = "new_prospect"

    updated = MarketingState(
        **state.marketing.model_dump(exclude={"customer_segment"}),
        customer_segment=segment,
    )

    return {
        "marketing": updated,
        "current_stage": "campaign",
        "agent_scratchpad": [AgentScratchpad(
            agent="marketing_segment",
            action="assign_segment",
            result=f"OK: segment={segment}",
        )],
    }


def marketing_campaign_node(state: GlobalState) -> dict:
    """Generate a targeted campaign offer for the customer's segment.

    Args:
        state: Global state with marketing.customer_segment.

    Returns:
        State update with marketing.offer_generated and channel set.
    """
    if not state.marketing or not state.marketing.customer_segment:
        return _error("marketing_campaign", "No segment for campaign generation")
    if not state.customer_profile:
        return _error("marketing_campaign", "No customer profile for campaign")

    profile = state.customer_profile
    segment = state.marketing.customer_segment

    prompt = (
        f"Customer segment: {segment}\n"
        f"Policy type: {profile.policy_type}\n"
        f"Coverage limit: ${profile.coverage_limit:,.2f}\n"
        f"Customer name: {profile.name}\n"
    )

    response = _llm.invoke([
        SystemMessage(content=_OFFER_SYSTEM),
        HumanMessage(content=prompt),
    ])

    try:
        data = json.loads(response.content.strip())
    except json.JSONDecodeError:
        data = {"offer": response.content.strip(), "channel": "email"}

    updated = MarketingState(
        **state.marketing.model_dump(exclude={"offer_generated", "channel", "campaign_id"}),
        campaign_id=f"CAMP-{uuid.uuid4().hex[:6].upper()}",
        offer_generated=str(data.get("offer", "")),
        channel=data.get("channel", "email"),  # type: ignore[arg-type]
    )

    return {
        "marketing": updated,
        "current_stage": "audit",
        "agent_scratchpad": [AgentScratchpad(
            agent="marketing_campaign",
            action="generate_offer",
            result=f"OK: campaign {updated.campaign_id} via {updated.channel}",
        )],
    }


def _error(agent: str, msg: str) -> dict:
    return {
        "error": msg,
        "current_stage": "error",
        "agent_scratchpad": [AgentScratchpad(
            agent=agent,
            action="marketing_op",
            result=f"ERROR: {msg}",
        )],
    }
