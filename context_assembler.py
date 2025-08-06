import math


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

def assemble_context(
    query_embedding: list[float],
    snippet_embeddings: dict[str, list[float]],
    snippets: dict[str, str],
    top_k: int = 8,
    token_limit: int = 2048,
) -> str:
    """
    Select top_k snippets by cosine similarity and concatenate them
    into a context string without exceeding token_limit (approx. by char count).
    """
    # Compute similarities
    sims = [
        (cosine_similarity(query_embedding, snippet_embeddings[sid]), sid)
        for sid in snippet_embeddings
    ]
    # Sort and select top_k
    top_ids = [sid for _, sid in sorted(sims, key=lambda x: x[0], reverse=True)[:top_k]]
    # Build context respecting token limit (approx. by length)
    context = ""
    for sid in top_ids:
        snippet = snippets.get(sid, "")
        if len(context) + len(snippet) > token_limit:
            break
        context += snippet + "\n"
    return context
