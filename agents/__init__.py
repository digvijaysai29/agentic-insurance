from agents.approval import approval_node
from agents.billing import (
    billing_collections_node,
    billing_invoice_node,
    billing_payment_node,
)
from agents.claims import claims_node
from agents.compliance import compliance_node
from agents.error import error_node
from agents.fraud import fraud_node
from agents.human_review import human_review_node
from agents.intake import intake_node
from agents.marketing import (
    marketing_campaign_node,
    marketing_lead_score_node,
    marketing_segment_node,
)
from agents.onboarding import (
    onboarding_kyc_node,
    onboarding_policy_assign_node,
    onboarding_risk_profile_node,
)
from agents.policy_writer import policy_writer_node
from agents.renewals import (
    renewals_autorenew_node,
    renewals_expiry_node,
    renewals_negotiate_node,
)
from agents.router import router_node
from agents.supervisor import supervisor_node
from agents.support import support_node
from agents.underwriting import underwriting_node

__all__ = [
    # original nodes
    "approval_node",
    "claims_node",
    "error_node",
    "fraud_node",
    "human_review_node",
    "intake_node",
    "router_node",
    "support_node",
    "underwriting_node",
    # new orchestration
    "supervisor_node",
    "compliance_node",
    # billing domain
    "billing_invoice_node",
    "billing_payment_node",
    "billing_collections_node",
    # marketing domain
    "marketing_lead_score_node",
    "marketing_segment_node",
    "marketing_campaign_node",
    # renewals domain
    "renewals_expiry_node",
    "renewals_negotiate_node",
    "renewals_autorenew_node",
    # onboarding domain
    "onboarding_kyc_node",
    "onboarding_risk_profile_node",
    "onboarding_policy_assign_node",
    # underwriting domain
    "policy_writer_node",
]
