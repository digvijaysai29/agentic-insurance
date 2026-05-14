# Project: Agentic Insurance (LangGraph System)

## Core Architecture
- **Framework:** LangGraph (Stateful multi-agent orchestration)
- **Language:** Python 3.12+
- **State Management:** Pydantic models for strict typing of the global `State`.
- **Database:** Postgres (for transactional data), Vector DB (for policy/fraud search).

## Build & Run Commands
- Start Server: `uvicorn app.main:app --reload`
- Run Tests: `pytest tests/`
- Type Check: `mypy .`

## Coding Standards
- **Typed Everything:** All agent nodes must take `State` as input and return a `dict` update.
- **No Hallucinations:** Agents must use tools for *all* data retrieval (Policy lookup, Claim history).
- **Error Handling:** If a tool fails, return a specific error flag in the state, do not retry infinitely.
- **Docstrings:** Use Google-style docstrings for all complex node functions.

## Agent Personalities & Responsibilities
1. **Router:** Classifies intent -> [Claims, Underwriting, Support].
2. **Claims:** Validates coverage dates -> Routes to Fraud or Approval.
3. **Underwriting:** Calculates risk scores based on rules engine.
4. **Fraud:** Checks vector DB for anomaly patterns.
