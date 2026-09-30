"""Wraps a local sentence-transformers model for paragraph embeddings.

Embeddings are computed with plain code, not Jev or an LLM -- there's no
judgment call here, just a vector, so there's nothing for either of those
to add.
"""

from __future__ import annotations

from sentence_transformers import SentenceTransformer

EMBEDDING_DIM = 384  # matches the default all-MiniLM-L6-v2 model


class Embedder:
    def __init__(self, model_name: str) -> None:
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return vectors.tolist()
