"""
Embedding Service - Abstracted embedding provider interface
Supports multiple providers (sentence-transformers, OpenAI, etc.)
"""
import logging
from typing import List, Optional
from abc import ABC, abstractmethod
import numpy as np
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingService(ABC):
    """Abstract base class for embedding services"""
    
    @abstractmethod
    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for a single text"""
        pass
    
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts"""
        pass
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        """Get embedding dimension"""
        pass


class SentenceTransformersEmbeddingService(EmbeddingService):
    """Sentence Transformers embedding service implementation"""
    
    def __init__(self, model_name: Optional[str] = None, load_immediately: bool = True):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self._model = None
        self._dimension = None
        logger.info(f"Initializing Sentence Transformers with model: {self.model_name}")
        
        # Load model immediately if requested (default for singleton usage)
        if load_immediately:
            self._load_model()
    
    def _load_model(self):
        """Load the model (called during initialization)"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading Sentence Transformers model: {self.model_name}...")
                self._model = SentenceTransformer(self.model_name)
                # Get dimension from model
                test_embedding = self._model.encode("test")
                self._dimension = len(test_embedding)
                logger.info(f"✅ Loaded Sentence Transformers model: {self.model_name} (dim={self._dimension})")
            except ImportError:
                raise ImportError("sentence-transformers package is required. Install with: pip install sentence-transformers")
            except Exception as e:
                logger.error(f"❌ Failed to load Sentence Transformers model: {str(e)}")
                raise
    
    @property
    def model(self):
        """Get the model (loads if not already loaded)"""
        if self._model is None:
            self._load_model()
        return self._model
    
    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for a single text"""
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise
    
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts"""
        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            return embeddings
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {str(e)}")
            raise
    
    @property
    def dimension(self) -> int:
        """Get embedding dimension"""
        if self._dimension is None:
            # Trigger model load
            _ = self.model
        return self._dimension or settings.VECTOR_DIMENSION


def get_embedding_service(provider: Optional[str] = None,
                         model_name: Optional[str] = None,
                         load_immediately: bool = True) -> EmbeddingService:
    """
    Factory function to get embedding service based on provider
    
    Args:
        provider: Embedding provider name (sentence-transformers, openai, etc.)
        model_name: Model name to use
        load_immediately: Whether to load the model immediately (default: True)
        
    Returns:
        EmbeddingService instance
    """
    provider = provider or settings.EMBEDDING_PROVIDER
    
    if provider.lower() == "sentence-transformers":
        return SentenceTransformersEmbeddingService(model_name=model_name, load_immediately=load_immediately)
    else:
        raise ValueError(f"Unsupported embedding provider: {provider}. Supported: sentence-transformers")
