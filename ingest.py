"""
Ingestion script: read cleaned_chunks.json, embed each chunk, and insert into Supabase.

Usage:
    python ingest.py
"""

import json
import os
from typing import Any

from dotenv import load_dotenv
import supabase
from embedding import get_embedding_model, embed_batch

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
CLEANED_CHUNKS_PATH = "cleaner/cleaned_chunks.json"
BATCH_SIZE = 50


def get_supabase_client():
    """Create and return a Supabase client."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    return supabase.create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def load_chunks(filepath: str) -> list[dict[str, Any]]:
    """Load cleaned chunks from JSON."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def ingest_chunks():
    """Main ingestion: embed and insert chunks into Supabase."""
    print("Loading chunks...")
    chunks = load_chunks(CLEANED_CHUNKS_PATH)
    print(f"Loaded {len(chunks)} chunks")

    print("Loading embedding model...")
    model = get_embedding_model()
    
    client = get_supabase_client()
    
    # Prepare batch for embedding
    texts_to_embed = [chunk["content"] for chunk in chunks]
    
    print(f"Embedding {len(texts_to_embed)} chunks in batches of {BATCH_SIZE}...")
    embeddings = embed_batch(texts_to_embed, model=model)
    
    # Prepare rows for insertion
    rows = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        rows.append({
            "champion": chunk["champion"],
            "section": chunk["section"],
            "content": chunk["content"],
            "embedding": embedding,
        })
    
    print(f"Inserting {len(rows)} rows into Supabase...")
    # Insert in batches (Supabase has limits, typically 1000 rows at a time is safe)
    for i in range(0, len(rows), 1000):
        batch = rows[i:i+1000]
        response = client.table("champion_chunks").insert(batch).execute()
        print(f"  Inserted batch {i//1000 + 1} ({len(batch)} rows)")
    
    print("Ingestion complete!")


if __name__ == "__main__":
    ingest_chunks()