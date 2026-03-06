"""Document ingestion pipeline: files -> chunks -> embeddings -> ChromaDB."""

import hashlib
import os
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from src.readers import read_file, READERS
from src.config_loader import load_config, get_api_key

MAX_CHUNK_CHARS = 6000


def split_text_recursive(text: str, chunk_size: int, chunk_overlap: int,
                         _sep_index: int = 0) -> list[str]:
    """Split text into overlapping chunks using recursive separators."""
    separators = ["\n\n", "\n", ". ", " "]

    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    if _sep_index >= len(separators):
        # Last resort: character split
        step = max(1, chunk_size - chunk_overlap)
        chunks = []
        for i in range(0, len(text), step):
            chunk = text[i:i + chunk_size]
            if chunk.strip():
                chunks.append(chunk.strip())
        return chunks

    sep = separators[_sep_index]

    if sep not in text:
        return split_text_recursive(text, chunk_size, chunk_overlap, _sep_index + 1)

    parts = text.split(sep)
    merged = []
    current = ""
    for part in parts:
        candidate = current + sep + part if current else part
        if len(candidate) > chunk_size and current:
            merged.append(current)
            overlap_text = current[-chunk_overlap:] if chunk_overlap else ""
            current = overlap_text + sep + part if overlap_text else part
        else:
            current = candidate
    if current.strip():
        merged.append(current)

    # Recursively split any chunks that are still too large
    result = []
    for chunk in merged:
        if len(chunk) > chunk_size:
            result.extend(split_text_recursive(chunk, chunk_size, chunk_overlap,
                                               _sep_index + 1))
        elif chunk.strip():
            result.append(chunk.strip())
    return result


def chunk_documents(pages: list[dict], source_name: str, dataset_name: str,
                    chunk_size: int = 1000, chunk_overlap: int = 100) -> list[dict]:
    """Split pages into smaller chunks with metadata."""
    chunks = []
    global_chunk_index = 0
    for page_info in pages:
        text = page_info.get("text", "")
        if not text.strip():
            continue
        if len(text) > MAX_CHUNK_CHARS:
            splits = split_text_recursive(text, MAX_CHUNK_CHARS, chunk_overlap)
        else:
            splits = split_text_recursive(text, chunk_size, chunk_overlap)

        for split in splits:
            if len(split) > MAX_CHUNK_CHARS:
                split = split[:MAX_CHUNK_CHARS]
            chunks.append({
                "text": split,
                "metadata": {
                    "source": source_name,
                    "dataset": dataset_name,
                    "page": str(page_info.get("page", "?")),
                    "chunk_index": global_chunk_index,
                },
            })
            global_chunk_index += 1
    return chunks


def discover_files(documents_dir: str) -> list[tuple[Path, str]]:
    """Recursively discover all supported files.

    Returns list of (file_path, dataset_name) tuples.
    Dataset name is the immediate subfolder name, or "general" for root files.
    """
    root = Path(documents_dir)
    supported = set(READERS.keys())
    files = []

    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in supported:
            continue
        if file_path.name.startswith("."):
            continue

        rel = file_path.relative_to(root)
        dataset_name = rel.parts[0] if len(rel.parts) > 1 else "general"
        files.append((file_path, dataset_name))

    return files


def get_chroma_collection(cfg: dict):
    """Get or create the ChromaDB collection with embeddings."""
    db_path = cfg.get("paths", {}).get("vector_db", "chroma_db")
    if not os.path.isabs(db_path):
        project_root = Path(__file__).resolve().parent.parent
        db_path = os.path.join(str(project_root), db_path)

    client = chromadb.PersistentClient(path=db_path)

    embed_provider = cfg.get("embeddings", {}).get("provider", "local")
    if embed_provider == "openai":
        api_key = get_api_key(cfg, "openai")
        model = cfg.get("embeddings", {}).get("openai_model", "text-embedding-3-small")
        ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=api_key, model_name=model,
        )
    else:
        ef = embedding_functions.DefaultEmbeddingFunction()

    collection = client.get_or_create_collection(
        name="knowledge_base",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def ingest_documents(cfg: dict = None, documents_dir: str = None) -> int:
    """Ingest all supported files from knowledge_base/ into ChromaDB.

    Returns the number of chunks ingested.
    """
    if cfg is None:
        cfg = load_config()

    if documents_dir is None:
        documents_dir = cfg.get("paths", {}).get("knowledge_base", "knowledge_base")
        if not os.path.isabs(documents_dir):
            project_root = Path(__file__).resolve().parent.parent
            documents_dir = os.path.join(str(project_root), documents_dir)

    files = discover_files(documents_dir)
    if not files:
        print(f"No supported files found in {documents_dir}")
        print(f"Supported types: {', '.join(sorted(READERS.keys()))}")
        # Clear stale data from previous ingestions
        try:
            collection = get_chroma_collection(cfg)
            existing = collection.count()
            if existing > 0:
                print(f"Clearing {existing} stale chunks from previous ingestion...")
                all_ids = collection.get().get("ids", [])
                if all_ids:
                    for ci in range(0, len(all_ids), 5000):
                        collection.delete(ids=all_ids[ci:ci + 5000])
        except Exception as e:
            print(f"Warning: Could not clear vector DB: {e}")
        # Clear SQL database
        sql_enabled = cfg.get("sql", {}).get("enabled", True)
        if sql_enabled:
            try:
                sql_db_dir = cfg.get("paths", {}).get("sql_db", "sql_db")
                if not os.path.isabs(sql_db_dir):
                    project_root = Path(__file__).resolve().parent.parent
                    sql_db_dir = os.path.join(str(project_root), sql_db_dir)
                db_file = os.path.join(sql_db_dir, "knowledge_base.db")
                schema_file = os.path.join(sql_db_dir, "sql_schemas.json")
                if os.path.exists(db_file):
                    os.remove(db_file)
                    print("Cleared stale SQL database.")
                if os.path.exists(schema_file):
                    os.remove(schema_file)
            except Exception as e:
                print(f"Warning: Could not clear SQL database: {e}")
        # Clear KB meta
        try:
            db_path = cfg.get("paths", {}).get("vector_db", "chroma_db")
            if not os.path.isabs(db_path):
                project_root = Path(__file__).resolve().parent.parent
                db_path = os.path.join(str(project_root), db_path)
            meta_file = os.path.join(db_path, "kb_meta.txt")
            if os.path.exists(meta_file):
                os.remove(meta_file)
                print("Cleared stale KB overview.")
        except Exception as e:
            print(f"Warning: Could not clear KB meta: {e}")
        return 0

    # Summarize
    datasets = {}
    for f, ds in files:
        datasets.setdefault(ds, []).append(f)
    print(f"Found {len(files)} files across {len(datasets)} dataset(s):\n")
    for ds_name, ds_files in sorted(datasets.items()):
        exts = [f.suffix for f in ds_files]
        print(f"  {ds_name}: {len(ds_files)} files ({', '.join(sorted(set(exts)))})")
    print()

    chunk_size = cfg.get("retrieval", {}).get("chunk_size", 1000)
    chunk_overlap = cfg.get("retrieval", {}).get("chunk_overlap", 100)

    # Guard: overlap >= 80% of chunk_size would cause near-duplicate chunks
    max_overlap = int(chunk_size * 0.8)
    if chunk_overlap >= max_overlap:
        print(f"Warning: chunk_overlap ({chunk_overlap}) >= 80% of chunk_size ({chunk_size}). Capping at {max_overlap}.")
        chunk_overlap = max_overlap

    collection = get_chroma_collection(cfg)

    # Defer clearing until first successful chunk generation (prevents data loss
    # if all file reads fail after clearing)
    needs_clear = True
    total_chunks = 0
    for file_path, dataset_name in files:
        rel_path = file_path.relative_to(documents_dir)
        print(f"Processing: {rel_path}")

        try:
            pages = read_file(str(file_path))
        except Exception as e:
            print(f"  Error reading {file_path.name}: {e}")
            continue

        if not pages:
            print(f"  No text extracted, skipping.")
            continue

        source_name = file_path.relative_to(Path(documents_dir)).as_posix()
        chunks = chunk_documents(pages, source_name, dataset_name, chunk_size, chunk_overlap)
        print(f"  -> {len(chunks)} chunks")

        batch_size = 100
        safe_id_prefix = hashlib.md5(source_name.encode()).hexdigest()[:12]
        file_chunks_added = 0
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            ids = [f"{safe_id_prefix}_{i + j}" for j in range(len(batch))]
            documents = [c.get("text", "") for c in batch]
            metadatas = [c.get("metadata", {}) for c in batch]
            try:
                # Clear existing data only on first successful add
                if needs_clear:
                    existing = collection.count()
                    if existing > 0:
                        print(f"Clearing {existing} existing chunks...\n")
                        all_ids = collection.get().get("ids", [])
                        if all_ids:
                            for ci in range(0, len(all_ids), 5000):
                                collection.delete(ids=all_ids[ci:ci + 5000])
                    needs_clear = False
                collection.add(ids=ids, documents=documents, metadatas=metadatas)
                file_chunks_added += len(batch)
            except Exception as e:
                print(f"  Warning: Failed to embed batch for {source_name}: {e}")

        total_chunks += file_chunks_added

    # ── SQL ingestion for tabular files ──────────────────────────────
    sql_enabled = cfg.get("sql", {}).get("enabled", True)
    if sql_enabled:
        from src.sql_ingest import ingest_to_sql, SQL_EXTENSIONS
        tabular_count = sum(1 for f, _ in files if f.suffix.lower() in SQL_EXTENSIONS)
        if tabular_count > 0:
            print(f"\nIngesting {tabular_count} tabular file(s) into SQLite...")
            try:
                schema = ingest_to_sql(files, documents_dir, cfg)
                print(f"SQL ingestion complete: {len(schema)} table(s).")
            except Exception as e:
                print(f"SQL ingestion error (non-fatal): {e}")

    # ── KB meta overview (LLM-generated) ────────────────────────────
    print("\nGenerating knowledge base overview...")
    try:
        from src.kb_meta import build_and_store_overview
        overview = build_and_store_overview(collection, cfg)
        if overview:
            print("KB overview generated and indexed.")
        else:
            print("KB overview: nothing to summarize.")
    except Exception as e:
        print(f"KB overview generation failed (non-fatal): {e}")

    print(f"\nIngestion complete: {total_chunks} chunks from {len(files)} files.")
    return total_chunks
