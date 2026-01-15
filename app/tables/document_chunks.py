"""
Document Chunks table - Stores metadata about document chunks for vector search
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, Index
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.tables.base import Base
import logging

logger = logging.getLogger(__name__)


class DocumentChunk(Base):
    """Document Chunk table model"""
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index('idx_document_chunk', 'document_id', 'chunk_index'),
        Index('idx_user_document', 'user_phone_number', 'document_id'),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    document_id = Column(Integer, ForeignKey("knowledge_documents.id"), nullable=False, index=True)
    user_phone_number = Column(String(20), nullable=True, index=True)  # NULL for global docs, set for user-specific
    chunk_index = Column(Integer, nullable=False)  # Order of chunk in document
    chunk_text = Column(Text, nullable=False)  # The actual chunk text
    chunk_start = Column(Integer, nullable=True)  # Start position in original document
    chunk_end = Column(Integer, nullable=True)  # End position in original document
    vector_id = Column(String(200), nullable=True, index=True)  # ID in vector database
    metadata_json = Column(Text, nullable=True)  # JSON string for additional metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert document chunk to dictionary"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "user_phone_number": self.user_phone_number,
            "chunk_index": self.chunk_index,
            "chunk_text": self.chunk_text,
            "chunk_start": self.chunk_start,
            "chunk_end": self.chunk_end,
            "vector_id": self.vector_id,
            "metadata_json": self.metadata_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DocumentChunkRepository:
    """Repository for Document Chunk table operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, chunk_id: int) -> Optional[DocumentChunk]:
        """Get document chunk by ID"""
        try:
            return self.db.query(DocumentChunk).filter(DocumentChunk.id == chunk_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting document chunk {chunk_id}: {str(e)}")
            raise
    
    def get_by_document(self, document_id: int, user_phone_number: Optional[str] = None) -> List[DocumentChunk]:
        """Get all chunks for a document"""
        try:
            query = self.db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id)
            
            if user_phone_number:
                query = query.filter(DocumentChunk.user_phone_number == user_phone_number)
            else:
                query = query.filter(DocumentChunk.user_phone_number.is_(None))
            
            return query.order_by(DocumentChunk.chunk_index.asc()).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting document chunks: {str(e)}")
            raise
    
    def get_by_vector_id(self, vector_id: str) -> Optional[DocumentChunk]:
        """Get chunk by vector database ID"""
        try:
            return self.db.query(DocumentChunk).filter(DocumentChunk.vector_id == vector_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting chunk by vector_id {vector_id}: {str(e)}")
            raise
    
    def create(self, document_id: int, chunk_index: int, chunk_text: str,
               chunk_start: Optional[int] = None, chunk_end: Optional[int] = None,
               user_phone_number: Optional[str] = None, vector_id: Optional[str] = None,
               metadata_json: Optional[str] = None) -> DocumentChunk:
        """Create a new document chunk"""
        try:
            chunk = DocumentChunk(
                document_id=document_id,
                user_phone_number=user_phone_number,
                chunk_index=chunk_index,
                chunk_text=chunk_text,
                chunk_start=chunk_start,
                chunk_end=chunk_end,
                vector_id=vector_id,
                metadata_json=metadata_json,
            )
            self.db.add(chunk)
            self.db.commit()
            self.db.refresh(chunk)
            return chunk
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error creating document chunk: {str(e)}")
            raise
    
    def delete_by_document(self, document_id: int, user_phone_number: Optional[str] = None) -> int:
        """Delete all chunks for a document"""
        try:
            query = self.db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id)
            
            if user_phone_number:
                query = query.filter(DocumentChunk.user_phone_number == user_phone_number)
            else:
                query = query.filter(DocumentChunk.user_phone_number.is_(None))
            
            count = query.delete()
            self.db.commit()
            return count
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error deleting document chunks: {str(e)}")
            raise
    
    def update_vector_id(self, chunk_id: int, vector_id: str) -> Optional[DocumentChunk]:
        """Update vector ID for a chunk"""
        try:
            chunk = self.get_by_id(chunk_id)
            if not chunk:
                return None
            
            chunk.vector_id = vector_id
            self.db.commit()
            self.db.refresh(chunk)
            return chunk
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error updating vector_id for chunk {chunk_id}: {str(e)}")
            raise
