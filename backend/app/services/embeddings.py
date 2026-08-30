import asyncio
import functools
import logging
import numpy as np
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Singleton service for generating text embeddings using SentenceTransformers."""

    _instance: Optional["EmbeddingService"] = None
    _model = None

    def __init__(self):
        raise RuntimeError("Use EmbeddingService.get_instance() instead")

    @classmethod
    def get_instance(cls) -> "EmbeddingService":
        """Get or create the singleton instance."""
        if cls._instance is None:
            instance = object.__new__(cls)
            instance._load_model()
            cls._instance = instance
        return cls._instance

    def _load_model(self):
        """Load the SentenceTransformer model."""
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
            logger.info(f"Embedding model loaded. Dimension: {settings.EMBEDDING_DIMENSION}")
        except ImportError:
            logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
            raise
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    def encode(self, text: str) -> list[float]:
        """Encode a single text string to an embedding vector."""
        if self._model is None:
            raise RuntimeError("Embedding model not loaded")
        embedding = self._model.encode(
            text,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embedding.tolist()

    def encode_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Encode a batch of texts to embedding vectors."""
        if self._model is None:
            raise RuntimeError("Embedding model not loaded")
        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=True,
        )
        return embeddings.tolist()

    async def aencode(self, text: str) -> list[float]:
        """Async wrapper for encode."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.encode, text)

    async def aencode_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Async wrapper for encode_batch."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, functools.partial(self.encode_batch, texts, batch_size=batch_size))

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return settings.EMBEDDING_DIMENSION
