"""Dual retriever: ChromaDB vector search + optional web search + SQL retrieval."""

import re

from src.search import search, format_web_results_as_context

_collection_cache = {}


def clear_collection_cache():
    """Clear the cached ChromaDB collection so it's re-read after re-ingestion."""
    _collection_cache.clear()


def _get_cached_collection(cfg: dict):
    """Get or create cached ChromaDB collection."""
    from src.ingest import get_chroma_collection
    db_path = cfg.get("paths", {}).get("vector_db", "chroma_db")
    embed_provider = cfg.get("embeddings", {}).get("provider", "local")
    cache_key = f"{db_path}:{embed_provider}"
    if cache_key not in _collection_cache:
        _collection_cache[cache_key] = get_chroma_collection(cfg)
    return _collection_cache[cache_key]


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

    When no chunks pass the distance filter, the KB meta overview chunk
    is included as a fallback so that meta-questions about the knowledge
    base can still be answered.
    """
    retrieval_cfg = cfg.get("retrieval", {})
    top_k = retrieval_cfg.get("top_k", 50)
    max_distance = retrieval_cfg.get("max_distance", 0.55)
    collection = _get_cached_collection(cfg)

    total = collection.count()
    if total == 0:
        return []

    # Query a large candidate pool, then filter by relevance
    candidate_count = min(top_k, total)
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

    # Fallback: if no chunks passed the distance filter, include the KB
    # meta overview chunk so meta-questions can still be answered.
    if not chunks:
        from src.kb_meta import META_CHUNK_ID
        try:
            meta_result = collection.get(
                ids=[META_CHUNK_ID],
                include=["documents", "metadatas"],
            )
            if meta_result.get("documents") and meta_result["documents"][0]:
                chunks.append({
                    "text": meta_result["documents"][0],
                    "metadata": meta_result["metadatas"][0],
                    "distance": 1.0,  # fallback — not a real distance match
                })
        except Exception:
            pass

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
        source_path = meta.get('source', 'unknown')
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
    match = re.search(r'\bFROM\s+["`]?(\w+)["`]?', sql_query, re.IGNORECASE)
    return match.group(1) if match else ""


def _build_fallback_sql_query(query: str, cfg: dict) -> str | None:
    """Build a simple keyword search SQL query as a last-resort fallback.

    Loads the SQL schema, finds TEXT columns in the first table, and builds
    a LIKE-based search across those columns. Returns None if no schema
    or no text columns exist.
    """
    import json as _json
    import os
    from pathlib import Path

    sql_db_dir = cfg.get("paths", {}).get("sql_db", "sql_db")
    if not os.path.isabs(sql_db_dir):
        project_root = Path(__file__).resolve().parent.parent
        sql_db_dir = os.path.join(str(project_root), sql_db_dir)
    schema_path = os.path.join(sql_db_dir, "sql_schemas.json")

    try:
        with open(schema_path) as f:
            schema = _json.load(f)
    except Exception:
        return None

    if not schema:
        return None

    max_rows = cfg.get("sql", {}).get("max_rows", 200)

    # Extract meaningful search words (3+ chars, skip common stopwords)
    stopwords = {"the", "and", "for", "are", "but", "not", "you", "all",
                 "can", "had", "her", "was", "one", "our", "out", "has",
                 "what", "how", "who", "which", "when", "where", "with",
                 "from", "that", "this", "than", "then", "they", "been"}
    words = [w for w in re.split(r'\W+', query.lower()) if len(w) >= 3 and w not in stopwords]
    if not words:
        return None

    # Try first table with TEXT columns
    for table_name, info in schema.items():
        text_cols = [
            c.get("name") for c in info.get("columns", [])
            if c.get("type", "").upper() == "TEXT" and c.get("name")
        ]
        if not text_cols:
            continue

        conditions = []
        for col in text_cols:
            for word in words:
                safe_word = word.replace("'", "''")
                if not re.match(r'^\w+$', safe_word):
                    continue  # Skip non-alphanumeric words
                safe_word = safe_word.replace('%', '\\%').replace('_', '\\_')
                conditions.append(f'"{col}" LIKE \'%{safe_word}%\' ESCAPE \'\\\'')

        if conditions:
            where_clause = " OR ".join(conditions)
            return f'SELECT * FROM "{table_name}" WHERE {where_clause} LIMIT {max_rows}'

    return None


def _try_alternate_columns(sql_query: str, cfg: dict) -> tuple[list[dict], str] | None:
    """Try phrase-level LIKE on other TEXT columns of the same table.

    When ``WHERE "Country" LIKE '%South Korea%'`` fails because the value
    is stored in a different column (e.g. ``Country_OLD``), this function
    tries each TEXT column in the table until one matches.

    Returns (rows, effective_query) or None if nothing found.
    """
    import json as _json
    import os

    # Extract table name and search value from the query
    table_name = _extract_table_from_query(sql_query)
    if not table_name:
        return None

    # Extract the LIKE value or = value from the WHERE clause
    value_match = re.search(
        r"LIKE\s+'%([^%]+)%'|=\s*'([^']+)'",
        sql_query, re.IGNORECASE,
    )
    if not value_match:
        return None
    search_value = value_match.group(1) or value_match.group(2)
    if not search_value:
        return None

    # Extract the column currently being searched
    col_match = re.search(
        r'["`]?(\w+)["`]?\s*(?:LIKE|=)\s*',
        sql_query, re.IGNORECASE,
    )
    current_col = col_match.group(1) if col_match else ""

    # Load schema to find other TEXT columns
    sql_db_dir = cfg.get("paths", {}).get("sql_db", "sql_db")
    if not os.path.isabs(sql_db_dir):
        from pathlib import Path
        project_root = Path(__file__).resolve().parent.parent
        sql_db_dir = os.path.join(str(project_root), sql_db_dir)
    schema_path = os.path.join(sql_db_dir, "sql_schemas.json")
    try:
        with open(schema_path) as f:
            schema = _json.load(f)
    except Exception:
        return None

    table_info = schema.get(table_name)
    if not table_info:
        return None

    text_cols = [
        c.get("name") for c in table_info.get("columns", [])
        if c.get("type", "").upper() == "TEXT"
        and c.get("name")
        and c.get("name") != current_col
    ]

    from src.sql_retriever import execute_sql_query

    max_rows = cfg.get("sql", {}).get("max_rows", 200)
    safe_value = search_value.replace("'", "''")
    # Strip dangerous characters for defense-in-depth
    if not re.match(r"^[\w\s.,'-]+$", safe_value):
        safe_value = re.sub(r"[;'\\\"]", "", safe_value)
    safe_value = safe_value.replace('%', '\\%').replace('_', '\\_')
    for col in text_cols:
        alt_query = f'SELECT * FROM "{table_name}" WHERE "{col}" LIKE \'%{safe_value}%\' ESCAPE \'\\\' LIMIT {max_rows}'
        rows = execute_sql_query(alt_query, cfg)
        if rows:
            return rows, alt_query

    return None


def _run_sql_retrieval(sql_query: str, cfg: dict) -> tuple[list[dict], str, str]:
    """Execute SQL query and format results as context.

    Tries the exact query first.  If it returns zero rows, automatically
    retries with fuzzy matching (``=`` → ``LIKE '%…%'``).

    Returns (sql_rows, sql_context, match_type) where match_type is
    ``"exact"``, ``"fuzzy"``, or ``""`` (no results).
    """
    import json as _json
    import os
    from src.sql_retriever import (
        execute_sql_query, format_sql_results_as_context,
        _lookup_source_file, make_fuzzy_query,
    )

    max_rows = cfg.get("sql", {}).get("max_rows", 200)

    # Step 1: try exact query
    sql_rows = execute_sql_query(sql_query, cfg)
    effective_query = sql_query
    match_type = "exact"

    # Step 2: if no results, try phrase-level fuzzy (LIKE '%South Korea%')
    if not sql_rows:
        fuzzy = make_fuzzy_query(sql_query)
        if fuzzy:
            sql_rows = execute_sql_query(fuzzy, cfg)
            if sql_rows:
                effective_query = fuzzy
                match_type = "fuzzy (phrase)"

    # Step 2.5: if phrase fuzzy failed on original column, try other TEXT columns
    if not sql_rows:
        alt = _try_alternate_columns(fuzzy or sql_query, cfg)
        if alt:
            sql_rows, effective_query = alt
            match_type = "fuzzy (alt column)"

    # Step 3: if still no results, try word-level fuzzy (LIKE '%Korea%')
    if not sql_rows:
        word_fuzzy = make_fuzzy_query(sql_query, word_level=True)
        if word_fuzzy and word_fuzzy != (fuzzy or ""):
            sql_rows = execute_sql_query(word_fuzzy, cfg)
            if sql_rows:
                effective_query = word_fuzzy
                match_type = "fuzzy (word)"

    if not sql_rows:
        return [], "", ""

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
    table_name = _extract_table_from_query(effective_query)
    source_file = _lookup_source_file(table_name, schema)
    table_info = schema.get(table_name)
    sql_context = format_sql_results_as_context(
        sql_rows, effective_query, source_file, table_info=table_info,
        max_rows=max_rows,
    )
    return sql_rows, sql_context, match_type


def retrieve(
    query: str, cfg: dict, route: str = "vector", sql_query: str = None,
) -> dict:
    """Run retrieval with SQL/vector routing and fallback.

    Returns dict with: context, db_results, web_results, sql_results, has_sources.
    """
    sql_enabled = cfg.get("sql", {}).get("enabled", True)
    sql_context = ""
    sql_rows = []
    sql_match_type = ""

    # ── SQL retrieval ────────────────────────────────────────────────
    if sql_enabled and route in ("sql", "both") and sql_query:
        sql_rows, sql_context, sql_match_type = _run_sql_retrieval(sql_query, cfg)

    # ── Vector retrieval ─────────────────────────────────────────────
    db_results = []
    if route in ("vector", "both") or (route == "sql" and not sql_rows):
        db_results = retrieve_from_vectordb(query, cfg)

    # ── Fallback: try keyword-based SQL when primary path returned nothing ─
    #   - route "vector"/"both": vector found nothing → try SQL keyword search
    #   - route "sql": LLM SQL query failed → try SQL keyword search as last resort
    sql_fallback_needed = (
        sql_enabled
        and not sql_rows
        and (
            (route in ("vector", "both") and not db_results)
            or (route == "sql" and not db_results)
        )
    )
    if sql_fallback_needed:
        if route == "sql":
            # LLM-generated sql_query already failed; build a fresh keyword query
            fallback_query = _build_fallback_sql_query(query, cfg)
            if fallback_query:
                sql_rows, sql_context, sql_match_type = _run_sql_retrieval(fallback_query, cfg)
        else:
            # route is "vector" or "both" — build fresh keyword query
            # (if sql_query exists, it was already tried above and returned nothing)
            fallback_sql = _build_fallback_sql_query(query, cfg)
            if fallback_sql:
                sql_rows, sql_context, sql_match_type = _run_sql_retrieval(fallback_sql, cfg)

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
        "sql_match_type": sql_match_type,
        "has_sources": has_sources,
    }
