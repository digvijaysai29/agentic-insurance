import os

import numpy as np
import psycopg2


def search_fraud_patterns(
    query: str,
    top_k: int = 5,
    similarity_threshold: float = 0.85,
) -> list[str]:
    """Search the vector DB for fraud patterns similar to the claim profile.

    Uses pgvector cosine similarity. Returns pattern labels whose similarity
    score meets or exceeds the threshold.

    Args:
        query: Text description of the current claim (policy type, amount, customer id).
        top_k: Number of nearest neighbours to retrieve from the vector index.
        similarity_threshold: Minimum cosine similarity (0.0–1.0) to flag a match.

    Returns:
        List of matched fraud pattern labels. Empty list means no flags found.
    """
    embedding = _embed(query)
    url = os.environ["VECTOR_DB_URL"]
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT label, 1 - (embedding <=> %s::vector) AS similarity
                FROM fraud_patterns
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (embedding.tolist(), embedding.tolist(), top_k),
            )
            rows = cur.fetchall()
    return [label for label, sim in rows if sim >= similarity_threshold]


def _embed(text: str) -> np.ndarray:
    """Return a deterministic stub embedding vector for the given text.

    Replace with a real embedding call (e.g. a sentence-transformer or the
    Anthropic embeddings API) before deploying to production.
    """
    rng = np.random.default_rng(hash(text) % (2**32))
    vec = rng.random(1536).astype(np.float32)
    return vec / np.linalg.norm(vec)
