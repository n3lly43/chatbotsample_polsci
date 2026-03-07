"""Semantic Scholar API search backend."""
import time
import requests

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]

def search_papers(query: str, limit: int = 5) -> list[dict]:
    params = {
        "query": query, "limit": limit,
        "fields": "title,authors,year,abstract,url,externalIds,citationCount",
    }
    data = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.get(SEMANTIC_SCHOLAR_API, params=params, timeout=10)
            if response.status_code == 429 and attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAYS[attempt])
                continue
            response.raise_for_status()
            data = response.json()
            break
        except (requests.RequestException, ValueError):
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
                continue
            return []
    if data is None:
        return []

    results = []
    for paper in data.get("data", []):
        abstract = paper.get("abstract") or ""
        if not abstract:
            continue
        authors = ", ".join(a.get("name", "Unknown") for a in (paper.get("authors") or [])[:3])
        if len(paper.get("authors") or []) > 3:
            authors += " et al."
        url = paper.get("url", "")
        external_ids = paper.get("externalIds") or {}
        if external_ids.get("DOI"):
            url = f"https://doi.org/{external_ids.get('DOI', '')}"
        results.append({
            "title": paper.get("title", "Untitled"), "authors": authors,
            "year": paper.get("year"), "abstract": abstract, "url": url,
            "citation_count": paper.get("citationCount") or 0, "source_type": "web_search",
        })
    results.sort(key=lambda x: x.get("citation_count") or 0, reverse=True)
    return results
