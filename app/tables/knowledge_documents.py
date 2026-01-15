"""
Knowledge Documents table - Company-wide knowledge base documents
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Integer, Enum as SQLEnum
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.tables.base import Base
import enum
import logging

logger = logging.getLogger(__name__)


class DocumentType(str, enum.Enum):
    """Document type enumeration"""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"
    HTML = "html"
    CSV = "csv"
    XLSX = "xlsx"
    IMAGE = "image"
    WEBSITE = "website"
    OTHER = "other"


class DocumentStatus(str, enum.Enum):
    """Document processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class KnowledgeDocument(Base):
    """Knowledge Document table model"""
    __tablename__ = "knowledge_documents"
    
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    document_type = Column(SQLEnum(DocumentType), nullable=False)
    file_path = Column(String(1000), nullable=True)  # Local filesystem path
    source_url = Column(String(1000), nullable=True)  # For website sources
    file_size = Column(Integer, nullable=True)  # Size in bytes
    mime_type = Column(String(100), nullable=True)
    status = Column(SQLEnum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False)
    metadata_json = Column(Text, nullable=True)  # JSON string for additional metadata
    created_by = Column(String(100), nullable=True)  # User who added the document
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert document to dictionary"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "document_type": self.document_type.value if self.document_type else None,
            "file_path": self.file_path,
            "source_url": self.source_url,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "status": self.status.value if self.status else None,
            "metadata_json": self.metadata_json,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "error_message": self.error_message,
        }


class KnowledgeDocumentRepository:
    """Repository for Knowledge Document table operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, document_id: int) -> Optional[KnowledgeDocument]:
        """Get document by ID"""
        try:
            return self.db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting document {document_id}: {str(e)}")
            raise
    
    def create(self, title: str, document_type: DocumentType, 
               file_path: Optional[str] = None, source_url: Optional[str] = None,
               description: Optional[str] = None, file_size: Optional[int] = None,
               mime_type: Optional[str] = None, created_by: Optional[str] = None,
               metadata_json: Optional[str] = None, status: Optional[DocumentStatus] = None) -> KnowledgeDocument:
        """Create a new knowledge document"""
        try:
            # Use default status if not provided
            if status is None:
                status = DocumentStatus.PENDING
            
            doc = KnowledgeDocument(
                title=title,
                description=description,
                document_type=document_type,
                file_path=file_path,
                source_url=source_url,
                file_size=file_size,
                mime_type=mime_type,
                created_by=created_by,
                metadata_json=metadata_json,
                status=status,
            )
            self.db.add(doc)
            self.db.commit()
            self.db.refresh(doc)
            return doc
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error creating knowledge document: {str(e)}")
            raise
    
    def update(self, document_id: int, **kwargs) -> Optional[KnowledgeDocument]:
        """Update document by ID"""
        try:
            doc = self.get_by_id(document_id)
            if not doc:
                return None
            
            for key, value in kwargs.items():
                if hasattr(doc, key):
                    setattr(doc, key, value)
            
            doc.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(doc)
            return doc
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error updating document {document_id}: {str(e)}")
            raise
    
    def delete(self, document_id: int) -> bool:
        """Delete document by ID"""
        try:
            doc = self.get_by_id(document_id)
            if not doc:
                return False
            
            self.db.delete(doc)
            self.db.commit()
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error deleting document {document_id}: {str(e)}")
            raise
    
    def list_all(self, skip: int = 0, limit: int = 100, 
                 status: Optional[DocumentStatus] = None,
                 document_type: Optional[DocumentType] = None) -> List[KnowledgeDocument]:
        """List all documents with filters and pagination"""
        try:
            query = self.db.query(KnowledgeDocument)
            
            if status:
                query = query.filter(KnowledgeDocument.status == status)
            if document_type:
                query = query.filter(KnowledgeDocument.document_type == document_type)
            
            return query.order_by(KnowledgeDocument.created_at.desc()).offset(skip).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Error listing documents: {str(e)}")
            raise
