"""Onboarding agent pipeline: KYC verification → risk profiling → policy assignment.

Three nodes wired in ``graph/onboarding_graph.py``:
  1. ``onboarding_kyc_node``            — identity and compliance checks
  2. ``onboarding_risk_profile_node``   — initial risk score for new customer
  3. ``onboarding_policy_assign_node``  — assigns a policy number and activates
"""
from __future__ import annotations

import json
import uuid

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from schema.state import AgentScratchpad, GlobalState, OnboardingState

_llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)

_KYC_SYSTEM = """\
You are a KYC compliance officer. Given the customer details below, evaluate whether
KYC passes. Respond with a JSON object:
{
  "passed": true | false,
  "reason": "<brief reason if failed, or 'KYC passed' if succeeded>"
}
Fail KYC if:
- customer_id appears synthetic (e.g., 'test', 'demo', 'fake')
- name contains special characters other than spaces and hyphens
Respond ONLY with valid JSON, no markdown.
"""

_RISK_SYSTEM = """\
You are an insurance actuarial analyst. Given the customer profile, compute an
initial risk score as a JSON object:
{
  "risk_score": <float 0.0-1.0>
}
Heuristics:
- health/life policy: base 0.4
- auto/home policy: base 0.3
- coverage_limit > 500000: +0.2
- coverage_limit > 100000: +0.1
Respond ONLY with valid JSON, no markdown.
"""


def onboarding_kyc_node(state: GlobalState) -> dict:
    """Run KYC identity verification on the new customer.

    Args:
        state: Global state with customer_profile.

    Returns:
        State update with onboarding.kyc_passed set; routes to error on failure.
    """
    if not state.customer_profile:
        return _error("onboarding_kyc", "No customer profile for KYC")

    profile = state.customer_profile
    prompt = (
        f"customer_id: {profile.customer_id}\n"
        f"name: {profile.name}\n"
        f"policy_type: {profile.policy_type}\n"
    )

    response = _llm.invoke([
        SystemMessage(content=_KYC_SYSTEM),
        HumanMessage(content=prompt),
    ])

    try:
        data = json.loads(response.content.strip())
    except Exception:
        data = {"passed": False, "reason": "KYC LLM response unparseable"}

    kyc_passed = bool(data.get("passed", False))
    reason = str(data.get("reason", ""))

    onboarding = OnboardingState(
        kyc_passed=kyc_passed,
        kyc_failure_reason=None if kyc_passed else reason,
    )

    if not kyc_passed:
        return {
            "onboarding": onboarding,
            "error": f"KYC failed: {reason}",
            "current_stage": "error",
            "agent_scratchpad": [AgentScratchpad(
                agent="onboarding_kyc",
                action="kyc_check",
                result=f"FAIL: {reason}",
            )],
        }

    return {
        "onboarding": onboarding,
        "current_stage": "kyc",
        "agent_scratchpad": [AgentScratchpad(
            agent="onboarding_kyc",
            action="kyc_check",
            result="PASS",
        )],
    }


def onboarding_risk_profile_node(state: GlobalState) -> dict:
    """Compute an initial risk score for the new customer.

    Args:
        state: Global state with customer_profile and onboarding sub-state.

    Returns:
        State update with risk_score and onboarding.initial_risk_score set.
    """
    if not state.customer_profile:
        return _error("onboarding_risk", "No customer profile for risk profiling")
    if not state.onboarding or not state.onboarding.kyc_passed:
        return _error("onboarding_risk", "KYC must pass before risk profiling")

    profile = state.customer_profile
    prompt = (
        f"policy_type: {profile.policy_type}\n"
        f"coverage_limit: {profile.coverage_limit}\n"
    )

    response = _llm.invoke([
        SystemMessage(content=_RISK_SYSTEM),
        HumanMessage(content=prompt),
    ])

    try:
        data = json.loads(response.content.strip())
        risk = float(data.get("risk_score", 0.35))
    except Exception:
        risk = 0.35

    risk = max(0.0, min(1.0, risk))

    updated = OnboardingState(
        **state.onboarding.model_dump(exclude={"initial_risk_score"}),
        initial_risk_score=risk,
    )

    return {
        "onboarding": updated,
        "risk_score": risk,
        "current_stage": "onboarding",
        "agent_scratchpad": [AgentScratchpad(
            agent="onboarding_risk",
            action="compute_risk",
            result=f"OK: risk_score={risk:.3f}",
        )],
    }


def onboarding_policy_assign_node(state: GlobalState) -> dict:
    """Assign a new policy number and mark onboarding complete.

    Args:
        state: Global state with onboarding sub-state.

    Returns:
        State update with assigned_policy_number and onboarding_complete=True.
    """
    if not state.onboarding:
        return _error("onboarding_assign", "No onboarding state for policy assignment")

    policy_number = f"NEW-{uuid.uuid4().hex[:8].upper()}"

    updated = OnboardingState(
        **state.onboarding.model_dump(exclude={"assigned_policy_number", "onboarding_complete"}),
        assigned_policy_number=policy_number,
        onboarding_complete=True,
    )

    return {
        "onboarding": updated,
        "current_stage": "policy_assignment",
        "agent_scratchpad": [AgentScratchpad(
            agent="onboarding_assign",
            action="assign_policy",
            result=f"OK: assigned {policy_number}",
        )],
    }


def _error(agent: str, msg: str) -> dict:
    return {
        "error": msg,
        "current_stage": "error",
        "agent_scratchpad": [AgentScratchpad(
            agent=agent,
            action="onboarding_op",
            result=f"ERROR: {msg}",
        )],
    }
