# Project: Agentic Insurance (LangGraph System)

## Core Architecture

- **Framework:** LangGraph >=0.4 (Stateful multi-agent orchestration with Command API)
- **Language:** Python 3.12+
- **State Management:** Pydantic models for strict typing of the global `State`.
- **Database:** Postgres (for transactional data + LangGraph checkpointing), Vector DB (for policy/fraud search).
- **Orchestration Pattern:** Supervisor + compiled domain subgraphs

## Build & Run Commands

- Start Server: `uvicorn app.main:app --reload`
- Run Tests: `pytest tests/`
- Type Check: `mypy .`
- Production requires `DATABASE_URL` env var for PostgresSaver checkpointing.

## Graph Architecture

The system uses a **supervisor + subgraph** pattern. The main graph has a single
`supervisor_node` that classifies incoming requests and returns a `Command(goto=<domain>)`
to route execution into one of 7 isolated domain subgraphs.

```
intake → supervisor → claims        (subgraph) → END
                   ├→ underwriting  (subgraph) → END
                   ├→ billing       (subgraph) → END
                   ├→ marketing     (subgraph) → END
                   ├→ renewals      (subgraph) → END
                   ├→ onboarding    (subgraph) → END
                   ├→ support       (leaf node) → END
                   └→ error_node    (leaf node) → END
```

## Domain Responsibilities

### 1. Supervisor (`agents/supervisor.py`)
- Classifies the incoming request into exactly one domain using `ChatAnthropic`.
- Returns `Command(goto=domain, update={...})` — no explicit edges needed.
- On unknown domain: routes to `error_node`.

### 2. Claims (`graph/claims_graph.py`)
Nodes: `claims → fraud → approval → human_review`
- **claims**: Validates policy coverage, extracts claim amount via `tools/policy_lookup`.
- **fraud**: Searches vector DB for anomaly patterns via `tools/fraud_search`.
- **approval**: Approves or denies; sets `requires_human_review` for edge cases.
- **human_review**: Interrupts via `interrupt()` for human decision on paused tickets.

### 3. Underwriting (`graph/underwriting_graph.py`)
Nodes: `underwriting → policy_writer → compliance`
- **underwriting**: Calculates risk scores via rules engine.
- **policy_writer**: Drafts `PolicyDocument` from risk score; interrupts for high premiums (>$50k).
- **compliance**: Validates regulatory rules and appends audit trail entries.

### 4. Billing (`graph/billing_graph.py`)
Nodes: `invoice → payment → collections → compliance`
- **billing_invoice**: Generates invoice with 30-day due date.
- **billing_payment**: Checks payment status; marks overdue.
- **billing_collections**: Escalates overdue invoices; interrupts for write-offs >$10k.
- **compliance**: Final audit logging.

### 5. Marketing (`graph/marketing_graph.py`)
Nodes: `lead_score → segment → campaign`
- **marketing_lead_score**: Scores customer (0.0-1.0) from profile signals.
- **marketing_segment**: Assigns `high_value | mid_tier | at_risk | new_prospect`.
- **marketing_campaign**: Generates personalised offer text and delivery channel via LLM.

### 6. Renewals (`graph/renewals_graph.py`)
Nodes: `expiry_check → negotiate → auto_renew`
- **renewals_expiry**: Calculates days until policy expiry.
- **renewals_negotiate**: Generates personalised renewal offer amount via LLM.
- **renewals_autorenew**: Auto-renews if within 60-day threshold; marks lapsed if expired.

### 7. Onboarding (`graph/onboarding_graph.py`)
Nodes: `kyc → risk_profile → policy_assign`
- **onboarding_kyc**: LLM-based KYC identity verification; blocks synthetic/invalid IDs.
- **onboarding_risk_profile**: Computes initial risk score for new customer.
- **onboarding_policy_assign**: Assigns a new policy number and marks onboarding complete.

### 8. Support (`agents/support.py`)
- Handles general inquiries, account updates, complaints (leaf node, no subgraph).

### 9. Compliance (`agents/compliance.py`)
- Cross-cutting node used inside underwriting and billing subgraphs.
- Validates 5 regulatory rules; fatal violations route to error; warnings log-only.
- Always appends `AuditEntry` objects to the append-only `audit_log` reducer.

## Coding Standards

- **Typed Everything:** All agent nodes must take `State` as input and return a `dict` update.
- **No Hallucinations:** Agents must use tools for *all* data retrieval (Policy lookup, Claim history).
- **Error Handling:** If a tool fails, return a specific error flag in the state, do not retry infinitely.
- **Docstrings:** Use Google-style docstrings for all complex node functions.

## Human-in-the-Loop Points

| Domain       | Trigger                              | Resume via                   |
|--------------|--------------------------------------|------------------------------|
| Claims       | Fraud flags or edge case approval    | `POST /tickets/{id}/review`  |
| Underwriting | Annual premium > $50,000             | `POST /tickets/{id}/review`  |
| Billing      | Write-off amount > $10,000           | `POST /tickets/{id}/review`  |

## API Endpoints

| Method | Path                       | Description                          |
|--------|----------------------------|--------------------------------------|
| POST   | `/tickets/submit`          | Universal entry point (any domain)   |
| POST   | `/tickets/{id}/review`     | Resume human-in-the-loop interrupt   |
| GET    | `/tickets/{id}/status`     | Inspect persisted state              |
| POST   | `/billing/invoice`         | Trigger billing pipeline             |
| POST   | `/marketing/campaign`      | Trigger marketing pipeline           |
| POST   | `/renewals/check`          | Trigger renewal check                |
| POST   | `/onboarding/register`     | Onboard new customer (KYC first)     |
| GET    | `/health`                  | Liveness probe                       |

## State Schema (`schema/state.py`)

- `GlobalState`: Shared across all subgraphs; contains domain sub-states as optional fields.
- `BillingState`: Invoice, payment status, collections flags.
- `MarketingState`: Lead score, segment, campaign offer, channel.
- `RenewalState`: Days until expiry, offer amount, renewal status.
- `OnboardingState`: KYC result, risk score, assigned policy number.
- `PolicyDocument`: Issued policy with terms, exclusions, premium.
- `AuditEntry`: Compliance audit log record (append-only via reducer).
