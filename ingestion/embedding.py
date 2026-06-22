"""
Embedding module using all-MiniLM-L6-v2 for semantic search.

all-MiniLM-L6-v2 produces 384-dimensional vectors.
"""

from sentence_transformers import SentenceTransformer


def get_embedding_model():
    """Load the model once (cached in memory after first call)."""
    return SentenceTransformer("all-MiniLM-L6-v2")


def embed_text(text: str, model=None) -> list[float]:
    """Embed a single string to a vector.

    Args:
        text: The text to embed
        model: Pre-loaded model (optional; creates one if None)

    Returns:
        A list of 384 floats
    """
    if model is None:
        model = get_embedding_model()

    embedding = model.encode(text, convert_to_tensor=False)
    return embedding.tolist()


def embed_batch(texts: list[str], model=None) -> list[list[float]]:
    """Embed multiple texts efficiently in a batch.

    Args:
        texts: List of strings
        model: Pre-loaded model (optional)

    Returns:
        List of embedding vectors
    """
    if model is None:
        model = get_embedding_model()

    embeddings = model.encode(texts, convert_to_tensor=False)
    return embeddings.tolist()