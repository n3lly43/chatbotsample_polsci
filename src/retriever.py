"""Dual retriever: ChromaDB vector search + optional web search + SQL retrieval."""

import re

from src.search import search, format_web_results_as_context

NO_SOURCES_REFUSAL = (
    "I don't have any information on this topic in my knowledge base. "
    "No relevant local documents or web sources were found. "
    "Please try a different question, or add relevant materials to "
    "the knowledge_base/ folder and run ingestion again."
)


def retrieve_from_vectordb(query: str, cfg: dict) -> list[dict]:
    """Retrieve all relevant chunks from ChromaDB using a distance threshold.

    Queries a large candidate pool, then filters to keep only chunks
    with cosine distance below ``max_distance``.  The ``top_k`` setting
    acts as a hard cap to prevent overwhelming the LLM context.
    """
    from src.ingest import get_chroma_collection

    retrieval_cfg = cfg.get("retrieval", {})
    top_k = retrieval_cfg.get("top_k", 50)
    max_distance = retrieval_cfg.get("max_distance", 0.55)
    collection = get_chroma_collection(cfg)

    if collection.count() == 0:
        return []

    # Query a large candidate pool, then filter by relevance
    candidate_count = min(top_k, collection.count())
    results = collection.query(
        query_texts=[query],
        n_results=candidate_count,
    )

    chunks = []
    documents = results.get("documents", [[]])[0]
    distances = results.get("distances", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    for i in range(len(documents)):
        distance = distances[i]
        if distance > max_distance:
            continue
        chunks.append({
            "text": documents[i],
            "metadata": metadatas[i],
            "distance": distance,
        })
    return chunks


def format_db_results_as_context(chunks: list[dict]) -> str:
    """Format vector DB results with CHUNK-LOCAL IDs for citation anchoring."""
    if not chunks:
        return ""

    parts = ["=== Local Document Results (PRIMARY — always trust these over web sources) ===\n"]
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        dataset = meta.get("dataset", "")
        dataset_label = f" [Dataset: {dataset}]" if dataset else ""
        source_path = f"knowledge_base/{meta.get('source', 'unknown')}"
        parts.append(
            f"[CHUNK-LOCAL-{i:03d}] From: {meta.get('source', 'unknown')}, "
            f"Page/Section {meta.get('page', '?')}{dataset_label}\n"
            f"  Path: {source_path}\n"
            f"  {chunk.get('text', '')}\n"
        )
    return "\n".join(parts)


def build_combined_context(
    db_results: list[dict], web_results: list[dict], sql_context: str = "",
) -> str:
    """Build combined context string from local, SQL, and web results."""
    db_context = format_db_results_as_context(db_results)
    web_context = format_web_results_as_context(web_results)

    has_local = bool(db_results) or bool(sql_context)
    has_web = bool(web_results)

    if not has_local and not has_web:
        return NO_SOURCES_REFUSAL

    parts = []

    if has_local and not has_web:
        parts.append("ONLY use the local sources below. Do not add any outside knowledge.\n")

    if has_local and has_web:
        parts.append(
            "IMPORTANT: Local document sources are the PRIMARY authority. "
            "Web sources are SUPPLEMENTARY only. If any web source contradicts "
            "a local document, trust the local document.\n"
        )

    if not has_local and has_web:
        parts.append(
            "NOTE: No local documents are indexed. All sources below come from "
            "academic web search. You MUST include the URL link for every source cited. "
            "State clearly that you have no curated local sources.\n"
        )

    if sql_context:
        parts.append(sql_context)
    if db_context:
        parts.append(db_context)
    if web_context:
        parts.append(web_context)

    return "\n\n".join(parts)


def _extract_table_from_query(sql_query: str) -> str:
    """Extract the first table name from a SQL query (best-effort)."""
    match = re.search(r'\bFROM\s+"?(\w+)"?', sql_query, re.IGNORECASE)
    return match.group(1) if match else ""


def _run_sql_retrieval(sql_query: str, cfg: dict) -> tuple[list[dict], str]:
    """Execute SQL query and format results as context.

    Returns (sql_rows, sql_context).
    """
    import json as _json
    import os
    from src.sql_retriever import execute_sql_query, format_sql_results_as_context, _lookup_source_file

    sql_rows = execute_sql_query(sql_query, cfg)
    if not sql_rows:
        return [], ""

    sql_db_dir = cfg.get("paths", {}).get("sql_db", "sql_db")
    if not os.path.isabs(sql_db_dir):
        from pathlib import Path
        project_root = Path(__file__).resolve().parent.parent
        sql_db_dir = os.path.join(str(project_root), sql_db_dir)
    schema_path = os.path.join(sql_db_dir, "sql_schemas.json")
    schema = {}
    if os.path.exists(schema_path):
        try:
            with open(schema_path) as f:
                schema = _json.load(f)
        except Exception:
            pass
    table_name = _extract_table_from_query(sql_query)
    source_file = _lookup_source_file(table_name, schema)
    sql_context = format_sql_results_as_context(sql_rows, sql_query, source_file)
    return sql_rows, sql_context


def retrieve(
    query: str, cfg: dict, route: str = "vector", sql_query: str = None,
) -> dict:
    """Run retrieval with SQL/vector routing and fallback.

    Returns dict with: context, db_results, web_results, sql_results, has_sources.
    """
    sql_enabled = cfg.get("sql", {}).get("enabled", True)
    sql_context = ""
    sql_rows = []

    # ── SQL retrieval ────────────────────────────────────────────────
    if sql_enabled and route in ("sql", "both") and sql_query:
        sql_rows, sql_context = _run_sql_retrieval(sql_query, cfg)

    # ── Vector retrieval ─────────────────────────────────────────────
    db_results = []
    if route in ("vector", "both") or (route == "sql" and not sql_rows):
        db_results = retrieve_from_vectordb(query, cfg)

    # ── Fallback: vector found nothing, try SQL ──────────────────────
    if sql_enabled and not db_results and not sql_rows and route == "vector" and sql_query:
        sql_rows, sql_context = _run_sql_retrieval(sql_query, cfg)

    # ── Web search ───────────────────────────────────────────────────
    web_enabled = cfg.get("web_search", {}).get("enabled", False)
    web_results = []
    if web_enabled:
        backend = cfg.get("web_search", {}).get("backend", "semantic_scholar")
        max_results = cfg.get("web_search", {}).get("max_results", 5)
        if not db_results and not sql_rows:
            max_results *= 2
        web_results = search(query, backend=backend, limit=max_results)

    combined_context = build_combined_context(db_results, web_results, sql_context=sql_context)
    has_sources = bool(db_results) or bool(web_results) or bool(sql_rows)

    return {
        "context": combined_context,
        "db_results": db_results,
        "web_results": web_results,
        "sql_results": sql_rows,
        "has_sources": has_sources,
    }
