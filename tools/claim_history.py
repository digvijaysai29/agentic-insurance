import os
from dataclasses import dataclass
from datetime import date

import psycopg2
from psycopg2.extras import RealDictCursor


@dataclass
class ClaimRecord:
    claim_id: str
    policy_number: str
    amount: float
    filed_date: date
    status: str


def get_claim_history(policy_number: str, limit: int = 10) -> list[ClaimRecord]:
    """Fetch prior claim records for a policy, ordered by most recent first.

    Args:
        policy_number: The policy to retrieve history for.
        limit: Maximum number of records to return.

    Returns:
        List of ClaimRecord ordered by filed_date descending.
    """
    url = os.environ["DATABASE_URL"]
    with psycopg2.connect(url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT claim_id, policy_number, amount, filed_date, status
                FROM claims
                WHERE policy_number = %s
                ORDER BY filed_date DESC
                LIMIT %s
                """,
                (policy_number, limit),
            )
            rows = cur.fetchall()
    return [ClaimRecord(**dict(r)) for r in rows]
