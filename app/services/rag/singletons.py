"""
Singleton instances for embedding service and vector store
These are initialized at app startup and reused throughout the application
"""
import logging
from typing import Optional
from app.services.rag.embedding_service import EmbeddingService, get_embedding_service
from app.services.rag.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)

# Global singleton instances
_embedding_service: Optional[EmbeddingService] = None
_vector_store: Optional[VectorStore] = None


def initialize_rag_services():
    """Initialize embedding service and vector store at app startup"""
    global _embedding_service, _vector_store
    
    try:
        logger.info("🔄 Initializing RAG services...")
        
        # Initialize embedding service (loads model immediately)
        logger.info("Loading embedding model...")
        _embedding_service = get_embedding_service()
        logger.info("✅ Embedding service initialized")
        
        # Initialize vector store (loads FAISS index immediately)
        logger.info("Loading FAISS vector store...")
        _vector_store = get_vector_store(
            dimension=_embedding_service.dimension,
            load_immediately=True  # Load index immediately
        )
        logger.info("✅ Vector store initialized")
        
        logger.info("✅ All RAG services initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize RAG services: {str(e)}", exc_info=True)
        raise


def get_embedding_service_instance() -> EmbeddingService:
    """Get the singleton embedding service instance"""
    if _embedding_service is None:
        raise RuntimeError("Embedding service not initialized. Call initialize_rag_services() first.")
    return _embedding_service


def get_vector_store_instance() -> VectorStore:
    """Get the singleton vector store instance"""
    if _vector_store is None:
        raise RuntimeError("Vector store not initialized. Call initialize_rag_services() first.")
    return _vector_store
