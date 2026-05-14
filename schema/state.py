from __future__ import annotations

import operator
from datetime import date, datetime, timezone
from typing import Annotated, Literal

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


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


class CustomerProfile(BaseModel):
    customer_id: str
    name: str
    policy_number: str
    policy_start_date: date
    policy_end_date: date
    coverage_limit: float
    policy_type: Literal["auto", "home", "health", "life"]


class GlobalState(BaseModel):
    ticket_id: str
    customer_profile: CustomerProfile | None = None

    current_stage: Literal[
        "intake", "routing", "claims", "underwriting",
        "fraud", "approval", "human_review", "support",
        "resolved", "error",
    ] = "intake"

    intent: Literal["claims", "underwriting", "support"] | None = None
    claim_amount: float | None = None
    risk_score: float | None = None
    fraud_flags: list[str] = []
    approval_status: Literal["pending", "approved", "denied", "human_required"] | None = None

    requires_human_review: bool = False
    human_review_reason: str | None = None

    error: str | None = None

    # LangGraph reducers: each node appends; never overwrites
    agent_scratchpad: Annotated[list[AgentScratchpad], operator.add] = []
    messages: Annotated[list[AnyMessage], add_messages] = []
