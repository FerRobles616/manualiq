import hashlib
from collections.abc import Sequence
from functools import lru_cache
from typing import Any, Protocol

import numpy as np

from app.core.config import get_settings
from app.services.text import tokenize


class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> np.ndarray: ...


class HashEmbeddingProvider:
    """Deterministic lexical embeddings for tests and offline fallback."""

    def __init__(self, dimension: int = 256) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self._dimension), dtype=np.float32)

        for row, text in enumerate(texts):
            for token in tokenize(text):
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % self._dimension
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vectors[row, index] += sign

            norm = np.linalg.norm(vectors[row])
            if norm > 0:
                vectors[row] /= norm

        return vectors


class Model2VecEmbeddingProvider:
    """Static multilingual embeddings without PyTorch or a GPU."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            from model2vec import StaticModel

            self._model = StaticModel.from_pretrained(self._model_name)
        return self._model

    @property
    def dimension(self) -> int:
        return int(self._load().dim)

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        vectors = self._load().encode(list(texts))
        return np.asarray(vectors, dtype=np.float32)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "hash":
        return HashEmbeddingProvider(settings.embedding_dim)
    return Model2VecEmbeddingProvider(settings.embedding_model)
