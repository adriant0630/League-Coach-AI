"""
Ingestion script: read cleaned_chunks.json, embed each chunk, and insert
into Supabase.

Usage:
    python ingest.py
"""

import json
import os
import sys
from typing import Any

from dotenv import load_dotenv
import supabase
from embedding import get_embedding_model, embed_batch

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# Adjust this if your folder is named differently - this assumes ingest.py
# lives in a sibling folder to "cleaner/" (e.g. lol-tool/ingestion/ingest.py
# and lol-tool/cleaner/cleaned_chunks.json)
CLEANED_CHUNKS_PATH = "../cleaner/cleaned_chunks.json"


def get_supabase_client():
    """Create and return a Supabase client."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    return supabase.create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def load_chunks(filepath: str) -> list[dict[str, Any]]:
    """Load cleaned chunks from JSON."""
    if not os.path.exists(filepath):
        print(f"[ERROR] Could not find {filepath}")
        print("Check that CLEANED_CHUNKS_PATH matches your actual folder layout,")
        print("and that you've run clean.py to generate this file first.")
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def clear_existing_chunks(client):
    """Delete all existing rows from champion_chunks before re-ingesting.

    This prevents duplicate rows if you run this script more than once
    (e.g. after fixing a bug in clean.py and regenerating the corpus).
    """
    print("Clearing existing chunks from champion_chunks...")
    try:
        # Supabase requires a filter for delete; this matches all rows
        # since every row has a positive id.
        client.table("champion_chunks").delete().gt("id", 0).execute()
        print("  Cleared.")
    except Exception as e:
        print(f"  [WARN] Could not clear existing rows: {e}")
        print("  Continuing anyway - you may end up with duplicate rows.")


def ingest_chunks():
    """Main ingestion: embed and insert chunks into Supabase."""
    print("Loading chunks...")
    chunks = load_chunks(CLEANED_CHUNKS_PATH)
    print(f"Loaded {len(chunks)} chunks")

    if not chunks:
        print("[ERROR] No chunks found in the file. Nothing to ingest.")
        sys.exit(1)

    print("Loading embedding model (this may take a moment on first run)...")
    model = get_embedding_model()

    client = get_supabase_client()
    clear_existing_chunks(client)

    texts_to_embed = [chunk["content"] for chunk in chunks]

    print(f"Embedding {len(texts_to_embed)} chunks...")
    embeddings = embed_batch(texts_to_embed, model=model)

    rows = []
    for chunk, embedding in zip(chunks, embeddings):
        rows.append({
            "champion": chunk["champion"],
            "section": chunk["section"],
            "content": chunk["content"],
            "embedding": embedding,
        })

    print(f"Inserting {len(rows)} rows into Supabase...")

    succeeded = 0
    failed = 0

    # Insert in batches of 500 (conservative; Supabase/Postgres can handle
    # more, but smaller batches make it easier to identify which batch
    # failed if something goes wrong).
    batch_size = 500
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        try:
            client.table("champion_chunks").insert(batch).execute()
            succeeded += len(batch)
            print(f"  Inserted batch {i // batch_size + 1} ({len(batch)} rows)")
        except Exception as e:
            failed += len(batch)
            print(f"  [ERROR] Batch {i // batch_size + 1} failed: {e}")

    print(f"\nDone. {succeeded} rows inserted, {failed} rows failed.")
    if failed > 0:
        print("Some rows failed to insert - check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    ingest_chunks()