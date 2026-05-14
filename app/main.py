from __future__ import annotations

import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from pydantic import BaseModel

from graph.main_graph import graph
from schema.state import CustomerProfile, GlobalState

load_dotenv()

app = FastAPI(title="Agentic Insurance API", version="0.1.0")


class SubmitTicketRequest(BaseModel):
    customer_profile: CustomerProfile
    message: str
    ticket_id: str | None = None


class ReviewDecisionRequest(BaseModel):
    decision: str
    reviewer_id: str


@app.post("/tickets/submit")
def submit_ticket(req: SubmitTicketRequest) -> dict:
    """Submit a new insurance ticket for processing."""
    ticket_id = req.ticket_id or str(uuid.uuid4())
    initial_state = GlobalState(
        ticket_id=ticket_id,
        customer_profile=req.customer_profile,
        messages=[HumanMessage(content=req.message)],
    )
    config = {"configurable": {"thread_id": ticket_id}}
    result = graph.invoke(initial_state, config=config)
    return {"ticket_id": ticket_id, "status": result.get("current_stage"), "result": result}


@app.post("/tickets/{ticket_id}/review")
def submit_review(ticket_id: str, req: ReviewDecisionRequest) -> dict:
    """Resume a paused ticket with a human reviewer decision."""
    if req.decision not in {"approved", "denied"}:
        raise HTTPException(status_code=422, detail="decision must be 'approved' or 'denied'")
    config = {"configurable": {"thread_id": ticket_id}}
    result = graph.invoke(
        Command(resume={"decision": req.decision, "reviewer_id": req.reviewer_id}),
        config=config,
    )
    return {"ticket_id": ticket_id, "status": result.get("current_stage"), "result": result}


@app.get("/tickets/{ticket_id}/status")
def get_ticket_status(ticket_id: str) -> dict:
    """Retrieve the current persisted state of a ticket."""
    config = {"configurable": {"thread_id": ticket_id}}
    state = graph.get_state(config)
    if not state.values:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"ticket_id": ticket_id, "state": state.values}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
