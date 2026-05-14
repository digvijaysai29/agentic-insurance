from __future__ import annotations

import operator
from datetime import date, datetime, timezone
from typing import Annotated, Literal

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# ── Shared primitives ─────────────────────────────────────────────────────────

class ToolCall(BaseModel):
    tool_name: str
    args: dict
    result: str | None = None


class AgentScratchpad(BaseModel):
    agent: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    action: str
    result: str
    tool_calls: list[ToolCall] = []


class AuditEntry(BaseModel):
    """Single compliance/audit log record appended by the compliance node."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent: str
    event: str
    detail: str
    compliant: bool = True


# ── Customer & Policy ─────────────────────────────────────────────────────────

class CustomerProfile(BaseModel):
    customer_id: str
    name: str
    policy_number: str
    policy_start_date: date
    policy_end_date: date
    coverage_limit: float
    policy_type: Literal["auto", "home", "health", "life"]


# ── Domain-specific sub-state models ─────────────────────────────────────────

class BillingState(BaseModel):
    """State carried through the Billing subgraph."""
    invoice_id: str | None = None
    invoice_amount: float | None = None
    payment_status: Literal["unpaid", "paid", "overdue", "written_off"] | None = None
    due_date: date | None = None
    collection_escalated: bool = False
    write_off_requires_human: bool = False


class MarketingState(BaseModel):
    """State carried through the Marketing subgraph."""
    lead_score: float | None = None
    customer_segment: Literal["high_value", "mid_tier", "at_risk", "new_prospect"] | None = None
    campaign_id: str | None = None
    offer_generated: str | None = None
    channel: Literal["email", "sms", "push", "agent_call"] | None = None


class RenewalState(BaseModel):
    """State carried through the Renewals subgraph."""
    days_until_expiry: int | None = None
    renewal_offer_amount: float | None = None
    negotiation_notes: str | None = None
    renewal_status: Literal["pending", "auto_renewed", "negotiating", "lapsed", "cancelled"] | None = None
    customer_responded: bool = False


class OnboardingState(BaseModel):
    """State carried through the Onboarding subgraph."""
    kyc_passed: bool | None = None
    kyc_failure_reason: str | None = None
    initial_risk_score: float | None = None
    assigned_policy_number: str | None = None
    onboarding_complete: bool = False


class PolicyDocument(BaseModel):
    """Structured policy document produced by the Policy Writer agent."""
    policy_number: str
    policy_type: Literal["auto", "home", "health", "life"]
    customer_id: str
    coverage_limit: float
    annual_premium: float
    effective_date: date
    expiry_date: date
    terms_summary: str
    exclusions: list[str] = []
    issued_by_agent: str = "policy_writer"


# ── Global State ──────────────────────────────────────────────────────────────

class GlobalState(BaseModel):
    """Shared state threaded through the supervisor and all domain subgraphs.

    Nodes return ``dict`` updates; LangGraph merges them via the annotated
    reducers below.  Domain-specific fields are ``None`` until the relevant
    subgraph populates them.
    """
    ticket_id: str
    customer_profile: CustomerProfile | None = None

    current_stage: Literal[
        "intake", "routing",
        # claims pipeline
        "claims", "fraud", "approval", "human_review",
        # underwriting pipeline
        "underwriting", "policy_writing", "compliance",
        # billing pipeline
        "billing", "invoicing", "collections",
        # marketing pipeline
        "marketing", "lead_scoring", "campaign",
        # renewals pipeline
        "renewals", "negotiation", "auto_renew",
        # onboarding pipeline
        "onboarding", "kyc", "policy_assignment",
        # cross-cutting
        "support", "audit", "resolved", "error",
    ] = "intake"

    # Primary routing field used by the supervisor
    domain: Literal[
        "claims", "underwriting", "billing",
        "marketing", "renewals", "onboarding", "support",
    ] | None = None

    # Legacy alias kept so existing routing functions continue to work
    intent: Literal["claims", "underwriting", "support"] | None = None

    # ── Claims domain ─────────────────────────────────────────────────────────
    claim_amount: float | None = None
    fraud_flags: list[str] = []
    approval_status: Literal["pending", "approved", "denied", "human_required"] | None = None

    # ── Underwriting domain ───────────────────────────────────────────────────
    risk_score: float | None = None
    policy_document: PolicyDocument | None = None

    # ── Billing domain ────────────────────────────────────────────────────────
    billing: BillingState | None = None

    # ── Marketing domain ──────────────────────────────────────────────────────
    marketing: MarketingState | None = None

    # ── Renewals domain ───────────────────────────────────────────────────────
    renewal: RenewalState | None = None

    # ── Onboarding domain ─────────────────────────────────────────────────────
    onboarding: OnboardingState | None = None

    # ── Human-in-the-loop ─────────────────────────────────────────────────────
    requires_human_review: bool = False
    human_review_reason: str | None = None

    # ── Error ─────────────────────────────────────────────────────────────────
    error: str | None = None

    # ── Append-only reducers ──────────────────────────────────────────────────
    agent_scratchpad: Annotated[list[AgentScratchpad], operator.add] = []
    audit_log: Annotated[list[AuditEntry], operator.add] = []
    messages: Annotated[list[AnyMessage], add_messages] = []
