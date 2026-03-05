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


def _escape_braces(text: str) -> str:
    """Escape curly braces in user-supplied text for safe use with str.format()."""
    return text.replace("{", "{{").replace("}", "}}")

_META_GENERATION_PROMPT = """\
You are a knowledge base analyst. Given the following information about
documents and data tables in a research knowledge base, write a concise
overview (200-400 words) that covers:

1. **What is in the knowledge base**: List each document/dataset, its type,
   and a 1-sentence description of what it contains (based on the sample text).
2. **Key topics and themes**: What subjects does this knowledge base cover?
3. **Connections**: How do the different documents/datasets relate to each
   other? Do they share countries, time periods, variables, or methodologies?

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
            cols = [c["name"] for c in info.get("columns", [])]
            row_count = info.get("row_count", 0)
            source = info.get("source_file", table_name)
            col_list = ", ".join(cols[:10])
            if len(cols) > 10:
                col_list += f", ... ({len(cols)} total)"
            lines.append(f"  [{table_name}] from {source}")
            lines.append(f"    {row_count} rows | Columns: {col_list}")
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

    # Build SQL section
    sql_section = ""
    if sql_schema:
        sql_lines = ["--- SQL TABLES ---"]
        for table_name, info in sql_schema.items():
            cols = ", ".join(c["name"] for c in info.get("columns", []))
            sql_lines.append(
                f"- {table_name} ({info.get('row_count', 0)} rows) "
                f"from {info.get('source_file', '?')}: {cols}"
            )
        sql_lines.append("--- END SQL TABLES ---\n")
        sql_section = "\n".join(sql_lines)

    prompt = _META_GENERATION_PROMPT.format(
        inventory=_escape_braces(inventory),
        samples=_escape_braces(samples),
        sql_section=_escape_braces(sql_section),
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


def collect_file_records(collection) -> list[dict]:
    """Extract unique file records from ChromaDB metadata."""
    if collection.count() == 0:
        return []

    all_data = collection.get(include=["metadatas"])
    metadatas = all_data.get("metadatas", [])

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


def collect_sample_chunks(collection) -> dict[str, str]:
    """Get the first chunk from each unique source for LLM analysis."""
    if collection.count() == 0:
        return {}

    all_data = collection.get(include=["documents", "metadatas"])
    documents = all_data.get("documents", [])
    metadatas = all_data.get("metadatas", [])

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
    file_records = collect_file_records(collection)
    sample_chunks = collect_sample_chunks(collection)
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
