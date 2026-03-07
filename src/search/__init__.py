"""Search backend registry."""
from src.search.semantic_scholar import search_papers as _ss_search

BACKENDS = {
    "semantic_scholar": _ss_search,
    "none": lambda query, limit=5: [],
}

def search(query: str, backend: str = "none", limit: int = 5) -> list[dict]:
    fn = BACKENDS.get(backend)
    if fn is None:
        return []
    try:
        return fn(query, limit=limit)
    except Exception:
        return []

def format_web_results_as_context(results: list[dict]) -> str:
    if not results:
        return ""
    parts = ["=== Web Search Results (Academic Papers — SUPPLEMENTARY ONLY) ===\n"]
    for i, r in enumerate(results, 1):
        year_str = f" ({r.get('year', '')})" if r.get("year") else ""
        parts.append(
            f"[CHUNK-WEB-{i:03d}] From: {r.get('authors', 'Unknown')}{year_str}. \"{r.get('title', 'Untitled')}\"\n"
            f"  URL: {r.get('url', 'N/A')}\n"
            f"  Abstract: {r.get('abstract', 'N/A')}\n"
        )
    return "\n".join(parts)
