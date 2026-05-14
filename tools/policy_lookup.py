import os

import psycopg2
from psycopg2.extras import RealDictCursor

from schema.state import CustomerProfile


def lookup_policy(policy_number: str) -> CustomerProfile | None:
    """Retrieve a CustomerProfile from the policies table.

    Args:
        policy_number: The unique policy identifier.

    Returns:
        CustomerProfile if found, None if no matching policy exists.
    """
    url = os.environ["DATABASE_URL"]
    with psycopg2.connect(url) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT customer_id, name, policy_number,
                       policy_start_date, policy_end_date,
                       coverage_limit, policy_type
                FROM policies
                WHERE policy_number = %s
                """,
                (policy_number,),
            )
            row = cur.fetchone()
    if row is None:
        return None
    return CustomerProfile(**dict(row))
