"""Knowledge Base meta-overview: LLM-generated summary of indexed content.

Generates a high-level overview of all documents and SQL tables in the
knowledge base using the LLM to understand content and connections.

This overview is:

1. Stored as a special chunk in ChromaDB so meta-questions can find it
   via vector search (solving the "what data do you have?" problem).
2. Injected into the query understanding prompt so the LLM can route
   and reformulate queries with full KB awareness.
3. Injected into the system prompt so the LLM always has the "general
   picture" when generating answers.
"""

import json
import os
from pathlib import Path


META_CHUNK_ID = "kb_meta_overview_001"
META_SOURCE = "Knowledge Base Overview"
META_DATASET = "meta"

_META_GENERATION_PROMPT = """\
You are a knowledge base analyst. Given the following information about
documents and data tables in a research knowledge base, write a concise
overview (200-500 words) that covers:

1. **What is in the knowledge base**: List each document/dataset, its type,
   and a 1-sentence description of what it contains (based on the sample text).
2. **Key topics and themes**: What subjects does this knowledge base cover?
3. **Connections**: How do the different documents/datasets relate to each
   other? Do they share countries, time periods, variables, or methodologies?
4. **Structured datasets**: For each structured data table, describe:
   - **Unit of observation**: What does each row represent? (e.g., a country-year,
     a person, a transaction, an event)
   - **Key columns**: What do the most important columns measure or contain?
     Use the column descriptions and codebook information provided below.
   - If codebook-derived descriptions are provided, use them. If only column
     names and sample values are available, infer the meaning and note that
     the interpretation is inferred.

Write in plain text, organized with clear headings. Be factual — only
describe what you can see in the provided samples. Do not speculate.

--- DOCUMENT INVENTORY ---
{inventory}
--- END INVENTORY ---

--- SAMPLE CONTENT (first chunk from each document) ---
{samples}
--- END SAMPLES ---

{sql_section}
Write the overview now:"""


def generate_kb_overview(
    file_records: list[dict],
    sample_chunks: dict[str, str],
    sql_schema: dict | None = None,
) -> str:
    """Build a deterministic (no-LLM) overview as fallback.

    Args:
        file_records: List of dicts with keys: source, dataset, chunk_count, ext.
        sample_chunks: Dict mapping source name -> first chunk text.
        sql_schema: SQL schema dict from sql_schemas.json (optional).

    Returns:
        A plain-text overview string suitable for prompt injection.
    """
    if not file_records and not sql_schema:
        return ""

    lines = ["=== KNOWLEDGE BASE OVERVIEW ===", ""]

    # ── Group files by dataset ───────────────────────────────────────
    datasets: dict[str, list[dict]] = {}
    for rec in file_records:
        ds = rec.get("dataset", "general")
        datasets.setdefault(ds, []).append(rec)

    if datasets:
        total_files = sum(len(v) for v in datasets.values())
        total_chunks = sum(r.get("chunk_count", 0) for r in file_records)
        lines.append(
            f"Documents: {total_files} files, {total_chunks} chunks "
            f"across {len(datasets)} dataset(s)."
        )
        lines.append("")

        for ds_name in sorted(datasets):
            ds_files = datasets[ds_name]
            lines.append(f"  [{ds_name}]")
            for rec in sorted(ds_files, key=lambda r: r.get("source", "")):
                name = rec.get("source", "unknown")
                ext = rec.get("ext", "")
                chunks = rec.get("chunk_count", 0)
                lines.append(f"    - {name} ({ext}, {chunks} chunks)")
            lines.append("")

    # ── SQL tables ───────────────────────────────────────────────────
    if sql_schema:
        lines.append(f"Structured data: {len(sql_schema)} SQL table(s).")
        lines.append("")
        for table_name, info in sql_schema.items():
            row_count = info.get("row_count", 0)
            source = info.get("source_file", table_name)
            table_desc = info.get("table_description", "")

            lines.append(f"  [{table_name}] from {source}")
            header = f"    {row_count} rows"
            if table_desc:
                header += f" | {table_desc}"
            lines.append(header)

            for c in info.get("columns", []):
                col_name = c.get("name", "unknown")
                col_type = c.get("type", "TEXT")
                desc = c.get("description", "")
                stats = c.get("stats", {})
                samples_list = c.get("sample", [])

                parts = [f"      {col_name} ({col_type})"]
                if stats.get("unique_count"):
                    parts.append(f"{stats['unique_count']} unique")
                if stats.get("min") is not None:
                    parts.append(f"range {stats['min']}\u2013{stats['max']}")
                if samples_list:
                    quoted = ", ".join(str(s) for s in samples_list[:3])
                    parts.append(f"e.g. {quoted}")
                if desc:
                    parts.append(f"\u2014 {desc}")

                lines.append(", ".join(parts) if len(parts) > 1 else parts[0])
            lines.append("")

    # ── Connection note ──────────────────────────────────────────────
    if len(datasets) > 1:
        ds_names = ", ".join(sorted(datasets))
        lines.append(
            f"All {len(datasets)} datasets ({ds_names}) are part of the same "
            "knowledge base and may share related topics, countries, or time periods."
        )
        lines.append("")

    lines.append("=== END OVERVIEW ===")
    return "\n".join(lines)


def generate_kb_overview_with_llm(
    file_records: list[dict],
    sample_chunks: dict[str, str],
    sql_schema: dict | None,
    cfg: dict,
) -> str:
    """Use the LLM to generate a rich KB overview with topic analysis.

    Falls back to the deterministic overview if LLM call fails.

    Args:
        file_records: List of dicts with keys: source, dataset, chunk_count, ext.
        sample_chunks: Dict mapping source name -> first chunk text.
        sql_schema: SQL schema dict from sql_schemas.json (optional).
        cfg: App config for LLM access.

    Returns:
        LLM-generated overview text.
    """
    from src.llm import generate

    if not file_records and not sql_schema:
        return ""

    # Build inventory section
    inv_lines = []
    for rec in sorted(file_records, key=lambda r: (r.get("dataset", ""), r.get("source", ""))):
        inv_lines.append(
            f"- {rec['source']} | dataset: {rec.get('dataset', 'general')} | "
            f"type: {rec.get('ext', '?')} | chunks: {rec.get('chunk_count', 0)}"
        )
    inventory = "\n".join(inv_lines) if inv_lines else "(no documents)"

    # Build sample section (truncate each to 500 chars)
    sample_lines = []
    for source, text in sorted(sample_chunks.items()):
        preview = text[:500] + "..." if len(text) > 500 else text
        sample_lines.append(f"[{source}]\n{preview}\n")
    samples = "\n".join(sample_lines) if sample_lines else "(no samples available)"

    # Build SQL section with full column detail
    sql_section = ""
    if sql_schema:
        sql_lines = ["--- STRUCTURED DATASETS (SQL TABLES) ---"]
        for table_name, info in sql_schema.items():
            row_count = info.get("row_count", 0)
            source = info.get("source_file", "?")
            table_desc = info.get("table_description", "")

            sql_lines.append(f"\nTable: {table_name} ({row_count} rows, from {source})")
            if table_desc:
                sql_lines.append(f"  Description: {table_desc}")

            # Determine if descriptions came from a codebook or were inferred
            has_descriptions = any(
                c.get("description") for c in info.get("columns", [])
            )
            if has_descriptions:
                sql_lines.append("  Column descriptions (from codebook or LLM analysis):")
            else:
                sql_lines.append("  Columns (no codebook found — infer from names and samples):")

            for c in info.get("columns", []):
                col_name = c.get("name", "unknown")
                col_type = c.get("type", "TEXT")
                desc = c.get("description", "")
                samples_list = c.get("sample", [])
                stats = c.get("stats", {})

                parts = [f"    - {col_name} [{col_type}]"]
                if stats.get("unique_count"):
                    parts.append(f"({stats['unique_count']} unique)")
                if stats.get("min") is not None:
                    parts.append(f"range: {stats['min']}\u2013{stats['max']}")
                if samples_list:
                    quoted = ", ".join(str(s) for s in samples_list[:5])
                    parts.append(f"e.g. {quoted}")
                if desc:
                    parts.append(f"\u2014 {desc}")

                sql_lines.append(" ".join(parts))

        sql_lines.append("\n--- END STRUCTURED DATASETS ---\n")
        sql_section = "\n".join(sql_lines)

    prompt = _META_GENERATION_PROMPT.format(
        inventory=inventory,
        samples=samples,
        sql_section=sql_section,
    )

    try:
        overview = generate(
            "You are a knowledge base analyst. Be concise and factual.",
            prompt,
            cfg,
            max_tokens=1024,
        )
        # Wrap in markers for consistent parsing
        return f"=== KNOWLEDGE BASE OVERVIEW ===\n\n{overview}\n\n=== END OVERVIEW ==="
    except Exception:
        # Fall back to deterministic overview
        return generate_kb_overview(file_records, sample_chunks, sql_schema)


def _collect_all_data(collection) -> tuple[list[str], list[dict]]:
    """Fetch all documents and metadatas from ChromaDB in a single call."""
    if collection.count() == 0:
        return [], []
    all_data = collection.get(include=["documents", "metadatas"])
    return all_data.get("documents", []), all_data.get("metadatas", [])


def collect_file_records(collection, *, _cache: tuple = None) -> list[dict]:
    """Extract unique file records from ChromaDB metadata.

    Args:
        _cache: Optional (documents, metadatas) tuple to avoid redundant
            collection.get() calls when used alongside collect_sample_chunks.
    """
    if _cache is not None:
        _, metadatas = _cache
    else:
        _, metadatas = _collect_all_data(collection)

    source_info: dict[str, dict] = {}
    for meta in metadatas:
        source = meta.get("source", "unknown")
        if source == META_SOURCE:
            continue
        if source not in source_info:
            ext = Path(source).suffix if "." in source else ""
            source_info[source] = {
                "source": source,
                "dataset": meta.get("dataset", "general"),
                "ext": ext,
                "chunk_count": 0,
            }
        source_info[source]["chunk_count"] += 1

    return list(source_info.values())


def collect_sample_chunks(collection, *, _cache: tuple = None) -> dict[str, str]:
    """Get the first chunk from each unique source for LLM analysis.

    Args:
        _cache: Optional (documents, metadatas) tuple to avoid redundant
            collection.get() calls when used alongside collect_file_records.
    """
    if _cache is not None:
        documents, metadatas = _cache
    else:
        documents, metadatas = _collect_all_data(collection)

    samples: dict[str, str] = {}
    for doc, meta in zip(documents, metadatas):
        source = meta.get("source", "unknown")
        if source == META_SOURCE:
            continue
        # Keep the first chunk seen for each source
        if source not in samples:
            samples[source] = doc

    return samples


def load_sql_schema(cfg: dict) -> dict | None:
    """Load SQL schema from sql_schemas.json if it exists."""
    sql_db_dir = cfg.get("paths", {}).get("sql_db", "sql_db")
    if not os.path.isabs(sql_db_dir):
        project_root = Path(__file__).resolve().parent.parent
        sql_db_dir = os.path.join(str(project_root), sql_db_dir)

    schema_path = os.path.join(sql_db_dir, "sql_schemas.json")
    if not os.path.exists(schema_path):
        return None
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_kb_meta(overview_text: str, cfg: dict) -> None:
    """Save the overview text to a file alongside the vector DB."""
    db_path = cfg.get("paths", {}).get("vector_db", "chroma_db")
    if not os.path.isabs(db_path):
        project_root = Path(__file__).resolve().parent.parent
        db_path = os.path.join(str(project_root), db_path)
    os.makedirs(db_path, exist_ok=True)
    meta_path = os.path.join(db_path, "kb_meta.txt")
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write(overview_text)


def load_kb_meta(cfg: dict) -> str:
    """Load the KB overview text from file. Returns empty string if not found."""
    db_path = cfg.get("paths", {}).get("vector_db", "chroma_db")
    if not os.path.isabs(db_path):
        project_root = Path(__file__).resolve().parent.parent
        db_path = os.path.join(str(project_root), db_path)
    meta_path = os.path.join(db_path, "kb_meta.txt")
    if not os.path.exists(meta_path):
        return ""
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def upsert_meta_chunk(collection, overview_text: str) -> None:
    """Insert or update the meta overview as a special chunk in ChromaDB."""
    if not overview_text:
        return
    collection.upsert(
        ids=[META_CHUNK_ID],
        documents=[overview_text],
        metadatas=[{
            "source": META_SOURCE,
            "dataset": META_DATASET,
            "page": "1",
            "chunk_index": 0,
        }],
    )


def build_and_store_overview(collection, cfg: dict) -> str:
    """Generate, store, and index the KB overview.  Called after ingestion.

    Uses the LLM to produce a rich summary. Falls back to deterministic
    overview if LLM is unavailable.

    Returns the overview text.
    """
    cache = _collect_all_data(collection)
    file_records = collect_file_records(collection, _cache=cache)
    sample_chunks = collect_sample_chunks(collection, _cache=cache)
    sql_schema = load_sql_schema(cfg)

    overview = generate_kb_overview_with_llm(
        file_records, sample_chunks, sql_schema, cfg,
    )
    if not overview:
        # LLM failed and deterministic also empty — nothing to store
        return ""

    save_kb_meta(overview, cfg)
    upsert_meta_chunk(collection, overview)
    return overview


_WELCOME_SUMMARY_PROMPT = """\
Given the following knowledge base overview, write a brief, friendly
welcome summary (3-6 sentences) for the chatbot's landing page.

Tell the user:
- What topics and datasets are available to ask about
- Roughly how much data there is (number of files, datasets, or data points)
- 2-3 example questions they could ask based on the actual content

Keep it conversational and concise. Do NOT use bullet points or headings.
Do NOT include technical details like column names, file extensions, or chunk counts.

--- KNOWLEDGE BASE OVERVIEW ---
{kb_overview}
--- END ---

Write the welcome summary now:"""


def summarize_kb_for_welcome(cfg: dict) -> str:
    """Generate a short, friendly welcome summary from the KB meta overview.

    Uses the LLM to produce a conversational summary suitable for the
    welcome page. Falls back to the raw overview text (stripped of markers)
    if the LLM call fails.

    Returns empty string if no KB meta exists.
    """
    kb_overview = load_kb_meta(cfg)
    if not kb_overview:
        return ""

    # Strip markers for clean input
    clean = kb_overview
    for marker in ("=== KNOWLEDGE BASE OVERVIEW ===", "=== END OVERVIEW ==="):
        clean = clean.replace(marker, "")
    clean = clean.strip()
    if not clean:
        return ""

    try:
        from src.llm import generate
        prompt = _WELCOME_SUMMARY_PROMPT.format(kb_overview=clean)
        summary = generate(
            "You are a friendly research assistant. Be concise.",
            prompt,
            cfg,
            max_tokens=512,
        )
        if summary and summary.strip():
            return summary.strip()
    except Exception:
        pass

    # Fallback: return truncated raw overview
    if len(clean) > 600:
        clean = clean[:600].rsplit("\n", 1)[0] + "\n..."
    return clean
