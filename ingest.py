"""Entry point for document ingestion."""

from src.ingest import ingest_documents
from src.config_loader import load_config


if __name__ == "__main__":
    cfg = load_config()
    count = ingest_documents(cfg)
    if count == 0:
        print("\nNo documents were ingested. Add files to knowledge_base/ and try again.")
