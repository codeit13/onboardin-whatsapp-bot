"""
Vector Store Service - Abstracted vector database interface
Supports multiple providers (FAISS, Pinecone, Weaviate, etc.)
"""
import logging
import os
import pickle
from typing import List, Optional, Dict, Any, Tuple
from abc import ABC, abstractmethod
import numpy as np
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VectorStore(ABC):
    """Abstract base class for vector stores"""
    
    @abstractmethod
    def add_vectors(self, vectors: np.ndarray, ids: List[str], metadata: Optional[List[Dict[str, Any]]] = None):
        """Add vectors to the store"""
        pass
    
    @abstractmethod
    def search(self, query_vector: np.ndarray, top_k: int = 5,
              filter_metadata: Optional[Dict[str, Any]] = None) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Search for similar vectors"""
        pass
    
    @abstractmethod
    def delete_vectors(self, ids: List[str]):
        """Delete vectors by IDs"""
        pass
    
    @abstractmethod
    def get_vector_count(self) -> int:
        """Get total number of vectors"""
        pass
    
    @abstractmethod
    def save(self, path: Optional[str] = None):
        """Save the vector store"""
        pass
    
    @abstractmethod
    def load(self, path: Optional[str] = None):
        """Load the vector store"""
        pass


class FAISSVectorStore(VectorStore):
    """FAISS vector store implementation"""
    
    def __init__(self, dimension: int, index_path: Optional[str] = None, load_immediately: bool = True):
        self.dimension = dimension
        self.index_path = index_path or settings.VECTOR_STORE_PATH
        self._index = None
        self._id_to_index = {}  # Map vector IDs to FAISS indices
        self._index_to_id = {}  # Map FAISS indices to vector IDs
        self._metadata = {}  # Store metadata by vector ID
        self._next_index = 0
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.index_path) if os.path.dirname(self.index_path) else ".", exist_ok=True)
        
        logger.info(f"Initializing FAISS vector store (dim={dimension}, path={self.index_path})")
        
        # Load index immediately if requested (default for singleton usage)
        if load_immediately:
            self._load_index()
    
    def _load_index(self):
        """Load or create the FAISS index (called during initialization)"""
        if self._index is None:
            try:
                import faiss
                
                # Try to load existing index
                if os.path.exists(f"{self.index_path}.index"):
                    logger.info(f"Loading existing FAISS index from {self.index_path}.index...")
                    self._index = faiss.read_index(f"{self.index_path}.index")
                    # Load ID mappings and metadata
                    self._load_metadata()
                    logger.info(f"✅ Loaded existing FAISS index with {self.get_vector_count()} vectors")
                else:
                    # Create new index (L2 distance)
                    logger.info("Creating new FAISS index...")
                    self._index = faiss.IndexFlatL2(self.dimension)
                    logger.info("✅ Created new FAISS index")
            except ImportError:
                raise ImportError("faiss-cpu or faiss-gpu package is required. Install with: pip install faiss-cpu")
            except Exception as e:
                logger.error(f"❌ Failed to initialize FAISS index: {str(e)}")
                raise
    
    @property
    def index(self):
        """Get the FAISS index (loads if not already loaded)"""
        if self._index is None:
            self._load_index()
        return self._index
    
    def add_vectors(self, vectors: np.ndarray, ids: List[str], metadata: Optional[List[Dict[str, Any]]] = None):
        """Add vectors to the store"""
        try:
            if len(vectors) != len(ids):
                raise ValueError("Number of vectors must match number of IDs")
            
            # Normalize vectors for cosine similarity (FAISS uses L2, so we normalize)
            import faiss as faiss_lib
            faiss_lib.normalize_L2(vectors)
            
            # Add to index
            start_idx = self._next_index
            self.index.add(vectors.astype('float32'))
            
            # Update mappings
            for i, vector_id in enumerate(ids):
                faiss_idx = start_idx + i
                self._id_to_index[vector_id] = faiss_idx
                self._index_to_id[faiss_idx] = vector_id
                if metadata and i < len(metadata):
                    self._metadata[vector_id] = metadata[i]
            
            self._next_index += len(vectors)
            self._save_metadata()
            
            logger.debug(f"Added {len(vectors)} vectors to FAISS index")
        except Exception as e:
            logger.error(f"Error adding vectors to FAISS: {str(e)}")
            raise
    
    def search(self, query_vector: np.ndarray, top_k: int = 5,
              filter_metadata: Optional[Dict[str, Any]] = None) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Search for similar vectors"""
        try:
            # Normalize query vector
            import faiss as faiss_lib
            query_vector = query_vector.reshape(1, -1).astype('float32')
            faiss_lib.normalize_L2(query_vector)
            
            # Search
            distances, indices = self.index.search(query_vector, top_k * 2)  # Get more to filter
            
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx == -1:  # FAISS returns -1 for empty slots
                    continue
                
                vector_id = self._index_to_id.get(idx)
                if not vector_id:
                    continue
                
                # Apply metadata filter if provided
                if filter_metadata:
                    metadata = self._metadata.get(vector_id, {})
                    if not all(metadata.get(k) == v for k, v in filter_metadata.items()):
                        continue
                
                # Convert L2 distance to similarity (1 / (1 + distance))
                similarity = 1.0 / (1.0 + float(dist))
                
                results.append((
                    vector_id,
                    similarity,
                    self._metadata.get(vector_id, {})
                ))
                
                if len(results) >= top_k:
                    break
            
            return results
        except Exception as e:
            logger.error(f"Error searching FAISS index: {str(e)}")
            raise
    
    def delete_vectors(self, ids: List[str]):
        """Delete vectors by IDs (FAISS doesn't support deletion, so we mark as deleted)"""
        # FAISS doesn't support deletion efficiently, so we'll mark them in metadata
        # In production, you might want to rebuild the index periodically
        logger.warning("FAISS doesn't support efficient deletion. Vectors are marked as deleted in metadata.")
        for vector_id in ids:
            if vector_id in self._metadata:
                self._metadata[vector_id]["deleted"] = True
            if vector_id in self._id_to_index:
                del self._id_to_index[vector_id]
        self._save_metadata()
    
    def get_vector_count(self) -> int:
        """Get total number of vectors"""
        return self.index.ntotal if self._index else 0
    
    def save(self, path: Optional[str] = None):
        """Save the vector store"""
        save_path = path or self.index_path
        try:
            if self._index:
                import faiss
                faiss.write_index(self.index, f"{save_path}.index")
                self._save_metadata(save_path)
                logger.info(f"✅ Saved FAISS index to {save_path}")
        except Exception as e:
            logger.error(f"Error saving FAISS index: {str(e)}")
            raise
    
    def load(self, path: Optional[str] = None):
        """Load the vector store (reloads if already loaded)"""
        if path and path != self.index_path:
            self.index_path = path
        # Reload index and metadata
        self._index = None
        self._load_index()
    
    def _save_metadata(self, path: Optional[str] = None):
        """Save ID mappings and metadata"""
        save_path = path or self.index_path
        metadata_file = f"{save_path}.metadata"
        try:
            with open(metadata_file, 'wb') as f:
                pickle.dump({
                    "id_to_index": self._id_to_index,
                    "index_to_id": self._index_to_id,
                    "metadata": self._metadata,
                    "next_index": self._next_index,
                }, f)
        except Exception as e:
            logger.error(f"Error saving metadata: {str(e)}")
    
    def _load_metadata(self, path: Optional[str] = None):
        """Load ID mappings and metadata"""
        load_path = path or self.index_path
        metadata_file = f"{load_path}.metadata"
        try:
            if os.path.exists(metadata_file):
                with open(metadata_file, 'rb') as f:
                    data = pickle.load(f)
                    self._id_to_index = data.get("id_to_index", {})
                    self._index_to_id = data.get("index_to_id", {})
                    self._metadata = data.get("metadata", {})
                    self._next_index = data.get("next_index", 0)
        except Exception as e:
            logger.error(f"Error loading metadata: {str(e)}")


def get_vector_store(store_type: Optional[str] = None,
                    dimension: Optional[int] = None,
                    index_path: Optional[str] = None,
                    load_immediately: bool = True) -> VectorStore:
    """
    Factory function to get vector store based on type
    
    Args:
        store_type: Vector store type (faiss, pinecone, etc.)
        dimension: Vector dimension
        index_path: Path to store the index
        load_immediately: Whether to load the index immediately (default: True)
        
    Returns:
        VectorStore instance
    """
    store_type = store_type or settings.VECTOR_STORE_TYPE
    dimension = dimension or settings.VECTOR_DIMENSION
    
    if store_type.lower() == "faiss":
        return FAISSVectorStore(dimension=dimension, index_path=index_path, load_immediately=load_immediately)
    else:
        raise ValueError(f"Unsupported vector store type: {store_type}. Supported: faiss")
