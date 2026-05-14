from __future__ import annotations

import logging
import os
import uuid

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from graph.main_graph import graph
from schema.state import CustomerProfile

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limiter (fix #4 — CWE-770)
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Agentic Insurance API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# CORS / security headers (fix #5 — CWE-693)
# Populate CORS_ORIGINS env var (comma-separated) before production.
# Defaults to empty list, which blocks all cross-origin requests.
# ---------------------------------------------------------------------------
allowed_origins = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# ---------------------------------------------------------------------------
# Auth skeleton (fix #2 — CWE-306)
# Wire _require_auth to real JWT validation (decode, verify sig, check exp,
# extract "sub" claim) before deploying to production.
# ---------------------------------------------------------------------------
_bearer = HTTPBearer(auto_error=False)


def _require_auth(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Auth skeleton — wire to real JWT validation before production."""
    if creds is None:
        logger.warning("Unauthenticated request — auth enforcement not yet enabled")
        return "anonymous"
    # TODO: validate token signature, expiry, audience; return the "sub" claim.
    return creds.credentials  # placeholder


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class SubmitTicketRequest(BaseModel):
    """ticket_id is intentionally absent — always generated server-side
    to prevent callers from overwriting existing tickets (fix #3 — CWE-639 IDOR).
    """

    customer_profile: CustomerProfile
    message: str


class ReviewDecisionRequest(BaseModel):
    decision: str
    # reviewer_id removed from request body — identity comes from the auth
    # token to prevent attacker-controlled reviewer attribution (fix #2 — CWE-639).


# Minimal response models — only expose fields safe for callers (fix #1 — CWE-200).
# Internal fields (agent_scratchpad, fraud_flags, raw error details, PII beyond
# what the caller submitted) must never be included here.


class TicketSubmitResponse(BaseModel):
    ticket_id: str
    status: str | None = None
    approval_status: str | None = None
    risk_score: float | None = None
    requires_human_review: bool = False


class TicketReviewResponse(BaseModel):
    ticket_id: str
    status: str | None = None
    approval_status: str | None = None


class TicketStatusResponse(BaseModel):
    ticket_id: str
    status: str | None = None
    approval_status: str | None = None
    risk_score: float | None = None
    requires_human_review: bool = False
    human_review_reason: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/tickets/submit", response_model=TicketSubmitResponse)
@limiter.limit("20/minute")
def submit_ticket(
    request: Request,
    req: SubmitTicketRequest,
    _reviewer: str = Depends(_require_auth),
) -> TicketSubmitResponse:
    """Submit a new insurance ticket for processing."""
    # ticket_id is always generated server-side (fix #3 — CWE-639 IDOR).
    ticket_id = str(uuid.uuid4())
    initial_state = {
        "ticket_id": ticket_id,
        "customer_profile": req.customer_profile,
        "messages": [HumanMessage(content=req.message)],
    }
    config = {"configurable": {"thread_id": ticket_id}}
    result = graph.invoke(initial_state, config=config)
    return TicketSubmitResponse(
        ticket_id=ticket_id,
        status=result.get("current_stage"),
        approval_status=result.get("approval_status"),
        risk_score=result.get("risk_score"),
        requires_human_review=bool(result.get("requires_human_review", False)),
    )


@app.post("/tickets/{ticket_id}/review", response_model=TicketReviewResponse)
@limiter.limit("20/minute")
def submit_review(
    request: Request,
    ticket_id: str,
    req: ReviewDecisionRequest,
    reviewer: str = Depends(_require_auth),
) -> TicketReviewResponse:
    """Resume a paused ticket with a human reviewer decision."""
    if req.decision not in {"approved", "denied"}:
        raise HTTPException(status_code=422, detail="decision must be 'approved' or 'denied'")
    config = {"configurable": {"thread_id": ticket_id}}
    # reviewer comes from the validated auth token, not the request body,
    # so the reviewer identity cannot be forged by the caller (fix #2 — CWE-639).
    result = graph.invoke(
        Command(resume={"decision": req.decision, "reviewer_id": reviewer}),
        config=config,
    )
    return TicketReviewResponse(
        ticket_id=ticket_id,
        status=result.get("current_stage"),
        approval_status=result.get("approval_status"),
    )


@app.get("/tickets/{ticket_id}/status", response_model=TicketStatusResponse)
def get_ticket_status(
    ticket_id: str,
    _reviewer: str = Depends(_require_auth),
) -> TicketStatusResponse:
    """Retrieve the current persisted state of a ticket."""
    config = {"configurable": {"thread_id": ticket_id}}
    state = graph.get_state(config)
    if not state.values:
        raise HTTPException(status_code=404, detail="Ticket not found")
    v = state.values
    return TicketStatusResponse(
        ticket_id=ticket_id,
        status=v.get("current_stage"),
        approval_status=v.get("approval_status"),
        risk_score=v.get("risk_score"),
        requires_human_review=bool(v.get("requires_human_review", False)),
        human_review_reason=v.get("human_review_reason"),
    )


@app.get("/health")
def health() -> dict:  # type: ignore[type-arg]
    return {"status": "ok"}
