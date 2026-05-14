"""Compliance agent: appends audit trail entries and validates regulatory rules.

This is a cross-cutting node that runs after any domain subgraph completes.
It checks business invariants and appends a structured ``AuditEntry`` to the
append-only ``audit_log`` reducer in ``GlobalState``.
"""
from __future__ import annotations

from schema.state import AgentScratchpad, AuditEntry, GlobalState

# Regulatory rules: (description, check_callable, is_fatal)
# Fatal violations set error and route to the error node.
_RULES: list[tuple[str, object, bool]] = [
    (
        "claim_amount_within_coverage_limit",
        lambda s: (
            s.claim_amount is None
            or s.customer_profile is None
            or s.claim_amount <= s.customer_profile.coverage_limit
        ),
        True,
    ),
    (
        "high_risk_policy_not_auto_approved",
        lambda s: not (
            s.risk_score is not None
            and s.risk_score > 0.85
            and s.approval_status == "approved"
            and not s.requires_human_review
        ),
        True,
    ),
    (
        "fraud_flags_require_human_review",
        lambda s: not (s.fraud_flags and not s.requires_human_review),
        True,
    ),
    (
        "onboarding_kyc_required",
        lambda s: (
            s.domain != "onboarding"
            or s.onboarding is None
            or s.onboarding.kyc_passed is True
        ),
        True,
    ),
    (
        "billing_overdue_escalation_logged",
        lambda s: not (
            s.billing is not None
            and s.billing.payment_status == "overdue"
            and not s.billing.collection_escalated
        ),
        False,
    ),
]


def compliance_node(state: GlobalState) -> dict:
    """Validate all regulatory rules and append a compliance audit entry.

    Runs after domain subgraphs complete.  Fatal rule violations set
    ``state.error`` and route to the error node.  Non-fatal violations
    log a warning in the audit trail only.

    Args:
        state: Full global state post-domain-execution.

    Returns:
        State update with audit_log entries appended; may set error on
        fatal violations.
    """
    violations: list[str] = []
    warnings: list[str] = []
    new_audit_entries: list[AuditEntry] = []

    for rule_name, check_fn, is_fatal in _RULES:
        try:
            passed = bool(check_fn(state))  # type: ignore[operator]
        except Exception as exc:
            passed = False
            warnings.append(f"{rule_name}: evaluation error ({exc})")

        if not passed:
            (violations if is_fatal else warnings).append(rule_name)
            new_audit_entries.append(AuditEntry(
                agent="compliance",
                event="rule_violation" if is_fatal else "rule_warning",
                detail=rule_name,
                compliant=False,
            ))

    if not violations and not warnings:
        new_audit_entries.append(AuditEntry(
            agent="compliance",
            event="compliance_check",
            detail=f"all rules passed for ticket {state.ticket_id}",
            compliant=True,
        ))

    scratchpad = AgentScratchpad(
        agent="compliance",
        action="validate_rules",
        result=(
            f"VIOLATIONS={violations}" if violations
            else f"OK (warnings={warnings})" if warnings
            else "OK: all rules passed"
        ),
    )

    if violations:
        return {
            "error": f"Compliance violations: {', '.join(violations)}",
            "current_stage": "error",
            "audit_log": new_audit_entries,
            "agent_scratchpad": [scratchpad],
        }

    return {
        "current_stage": "resolved",
        "audit_log": new_audit_entries,
        "agent_scratchpad": [scratchpad],
    }
