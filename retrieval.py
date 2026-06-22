"""
Retrieval layer: embed a query and fetch relevant chunks from Supabase.

Usage:
    from retrieval import retrieve_chunks
    
    chunks = retrieve_chunks(
        query="Yasuo top vs Zed jungle and Ahri mid",
        champion_filter="Yasuo",
        top_k=10
    )
"""

import os
from typing import Any

from dotenv import load_dotenv
import supabase

from ingestion.embedding import get_embedding_model, embed_text

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def get_supabase_client():
    """Create and return a Supabase client."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    return supabase.create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def retrieve_chunks(
    query: str,
    champion_filter: str | None = None,
    top_k: int = 10
) -> list[dict[str, Any]]:
    """
    Retrieve the top-K chunks most similar to the query.
    
    Args:
        query: User's natural language query (e.g. "Yasuo top vs Zed and Ahri")
        champion_filter: Optional champion name to filter results (e.g. "Yasuo")
        top_k: Number of results to return
    
    Returns:
        List of dicts with keys: id, champion, section, content, similarity
    """
    # Embed the query
    model = get_embedding_model()
    query_embedding = embed_text(query, model=model)
    
    # Call Supabase's match_chunks function
    client = get_supabase_client()
    
    response = client.rpc(
        "match_chunks",
        {
            "query_embedding": query_embedding,
            "match_count": top_k,
            "filter_champion": champion_filter,
        }
    ).execute()
    
    if response.data:
        return response.data
    else:
        return []


if __name__ == "__main__":
    # Quick test
    results = retrieve_chunks(
        query="Yasuo top laning phase against Zed",
        champion_filter="Yasuo",
        top_k=5
    )
    
    print(f"Found {len(results)} relevant chunks:\n")
    for i, chunk in enumerate(results, 1):
        print(f"[{i}] {chunk['champion']} - {chunk['section']} (similarity: {chunk['similarity']:.3f})")
        print(f"    {chunk['content'][:150]}...\n")
