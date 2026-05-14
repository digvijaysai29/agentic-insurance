"""Billing agent pipeline: invoice generation → payment check → collections.

Three nodes are defined here and wired together in ``graph/billing_graph.py``:
  1. ``billing_invoice_node`` — creates the invoice record in state
  2. ``billing_payment_node`` — checks payment status and marks overdue
  3. ``billing_collections_node`` — escalates overdue invoices; interrupts for
     write-off decisions above the write-off threshold
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from langgraph.types import interrupt

from schema.state import AgentScratchpad, BillingState, GlobalState

_OVERDUE_DAYS = 30
_WRITE_OFF_THRESHOLD = 10_000.0


def billing_invoice_node(state: GlobalState) -> dict:
    """Generate an invoice for the customer's outstanding premium.

    Args:
        state: Global state; uses policy_document if present, else claim_amount.

    Returns:
        State update with billing sub-state initialised.
    """
    if not state.customer_profile:
        return _error("billing_invoice", "No customer profile for invoice generation")

    amount = (
        state.policy_document.annual_premium
        if state.policy_document
        else state.claim_amount or 0.0
    )

    billing = BillingState(
        invoice_id=f"INV-{uuid.uuid4().hex[:8].upper()}",
        invoice_amount=amount,
        payment_status="unpaid",
        due_date=date.today() + timedelta(days=_OVERDUE_DAYS),
    )

    return {
        "billing": billing,
        "current_stage": "invoicing",
        "agent_scratchpad": [AgentScratchpad(
            agent="billing_invoice",
            action="generate_invoice",
            result=f"OK: {billing.invoice_id} for ${amount:,.2f} due {billing.due_date}",
        )],
    }


def billing_payment_node(state: GlobalState) -> dict:
    """Check payment status and flag overdue invoices.

    In production this integrates with the payment gateway; here it checks
    whether the due date has passed.

    Args:
        state: Global state with billing sub-state populated.

    Returns:
        State update with payment_status updated.
    """
    if not state.billing:
        return _error("billing_payment", "No billing state for payment check")

    billing = state.billing
    today = date.today()
    overdue = billing.due_date is not None and today > billing.due_date

    updated = BillingState(
        **billing.model_dump(exclude={"payment_status"}),
        payment_status="overdue" if overdue else "unpaid",
    )

    return {
        "billing": updated,
        "current_stage": "collections" if overdue else "audit",
        "agent_scratchpad": [AgentScratchpad(
            agent="billing_payment",
            action="check_payment",
            result=f"{'OVERDUE' if overdue else 'CURRENT'}: {billing.invoice_id}",
        )],
    }


def billing_collections_node(state: GlobalState) -> dict:
    """Escalate overdue invoices; interrupt for human write-off decisions.

    Args:
        state: Global state with billing sub-state showing overdue status.

    Returns:
        State update with collection_escalated flag set.
    """
    if not state.billing:
        return _error("billing_collections", "No billing state for collections")

    billing = state.billing

    if billing.payment_status != "overdue":
        return {
            "current_stage": "audit",
            "agent_scratchpad": [AgentScratchpad(
                agent="billing_collections",
                action="collections_check",
                result="SKIP: invoice not overdue",
            )],
        }

    amount = billing.invoice_amount or 0.0
    write_off_needed = amount > _WRITE_OFF_THRESHOLD

    if write_off_needed:
        interrupt({
            "reason": "write_off_approval",
            "invoice_id": billing.invoice_id,
            "amount": amount,
            "message": (
                f"Invoice {billing.invoice_id} for ${amount:,.2f} is overdue and exceeds "
                f"write-off threshold ${_WRITE_OFF_THRESHOLD:,.2f}. Approve write-off?"
            ),
        })

    updated = BillingState(
        **billing.model_dump(exclude={"collection_escalated", "write_off_requires_human"}),
        collection_escalated=True,
        write_off_requires_human=write_off_needed,
    )

    return {
        "billing": updated,
        "current_stage": "audit",
        "agent_scratchpad": [AgentScratchpad(
            agent="billing_collections",
            action="escalate_collections",
            result=f"ESCALATED: {billing.invoice_id}, write_off={write_off_needed}",
        )],
    }


def _error(agent: str, msg: str) -> dict:
    return {
        "error": msg,
        "current_stage": "error",
        "agent_scratchpad": [AgentScratchpad(
            agent=agent,
            action="billing_op",
            result=f"ERROR: {msg}",
        )],
    }
