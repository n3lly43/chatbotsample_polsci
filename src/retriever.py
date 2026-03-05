"""Dual retriever: ChromaDB vector search + optional web search."""

from src.search import search, format_web_results_as_context

NO_SOURCES_REFUSAL = (
    "I don't have any information on this topic in my knowledge base. "
    "No relevant local documents or web sources were found. "
    "Please try a different question, or add relevant materials to "
    "the knowledge_base/ folder and run ingestion again."
)


def retrieve_from_vectordb(query: str, cfg: dict) -> list[dict]:
    """Retrieve relevant chunks from ChromaDB."""
    from src.ingest import get_chroma_collection

    top_k = cfg.get("retrieval", {}).get("top_k", 10)
    collection = get_chroma_collection(cfg)

    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
    )

    chunks = []
    for i in range(len(results["documents"][0])):
        chunks.append({
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })
    return chunks


def format_db_results_as_context(chunks: list[dict]) -> str:
    """Format vector DB results with CHUNK-LOCAL IDs for citation anchoring."""
    if not chunks:
        return ""

    parts = ["=== Local Document Results (PRIMARY — always trust these over web sources) ===\n"]
    for i, chunk in enumerate(chunks, 1):
        meta = chunk["metadata"]
        dataset = meta.get("dataset", "")
        dataset_label = f" [Dataset: {dataset}]" if dataset else ""
        source_path = f"knowledge_base/{meta.get('source', 'unknown')}"
        parts.append(
            f"[CHUNK-LOCAL-{i:03d}] From: {meta.get('source', 'unknown')}, "
            f"Page/Section {meta.get('page', '?')}{dataset_label}\n"
            f"  Path: {source_path}\n"
            f"  {chunk['text']}\n"
        )
    return "\n".join(parts)


def build_combined_context(db_results: list[dict], web_results: list[dict]) -> str:
    """Build combined context string from local and web results."""
    db_context = format_db_results_as_context(db_results)
    web_context = format_web_results_as_context(web_results)

    if not db_results and not web_results:
        return NO_SOURCES_REFUSAL

    if not db_results and web_results:
        return (
            "NOTE: No local documents are indexed. All sources below come from "
            "academic web search. You MUST include the URL link for every source cited. "
            "State clearly that you have no curated local sources.\n\n"
            + web_context
        )

    if db_results and not web_results:
        return (
            "ONLY use the local sources below. Do not add any outside knowledge.\n\n"
            + db_context
        )

    # Both local and web
    return (
        "IMPORTANT: Local document sources are the PRIMARY authority. "
        "Web sources are SUPPLEMENTARY only. If any web source contradicts "
        "a local document, trust the local document.\n\n"
        + db_context + "\n\n" + web_context
    )


def retrieve(query: str, cfg: dict) -> dict:
    """Run dual retrieval: vector DB + optional web search.

    Returns dict with: context, db_results, web_results, has_sources.
    """
    db_results = retrieve_from_vectordb(query, cfg)

    web_enabled = cfg.get("web_search", {}).get("enabled", False)
    web_results = []
    if web_enabled:
        backend = cfg.get("web_search", {}).get("backend", "semantic_scholar")
        max_results = cfg.get("web_search", {}).get("max_results", 5)
        # Double web results when no local docs
        if not db_results:
            max_results *= 2
        web_results = search(query, backend=backend, limit=max_results)

    combined_context = build_combined_context(db_results, web_results)
    has_sources = bool(db_results) or bool(web_results)

    return {
        "context": combined_context,
        "db_results": db_results,
        "web_results": web_results,
        "has_sources": has_sources,
    }
