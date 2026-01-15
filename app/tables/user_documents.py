"""
User Documents table - Maps user-specific documents to users
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Session, relationship
from sqlalchemy.exc import SQLAlchemyError
from app.tables.base import Base
import logging

logger = logging.getLogger(__name__)


class UserDocument(Base):
    """User Document mapping table model"""
    __tablename__ = "user_documents"
    __table_args__ = (
        UniqueConstraint('user_phone_number', 'document_id', name='uq_user_document'),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_phone_number = Column(String(20), ForeignKey("users.phone_number"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("knowledge_documents.id"), nullable=False, index=True)
    assigned_by = Column(String(100), nullable=True)  # HR/admin who assigned the document
    notes = Column(String(1000), nullable=True)  # Notes about why this document is assigned
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships (optional, for easier querying)
    # user = relationship("User", backref="user_documents")
    # document = relationship("KnowledgeDocument", backref="user_documents")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user document mapping to dictionary"""
        return {
            "id": self.id,
            "user_phone_number": self.user_phone_number,
            "document_id": self.document_id,
            "assigned_by": self.assigned_by,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class UserDocumentRepository:
    """Repository for User Document table operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, mapping_id: int) -> Optional[UserDocument]:
        """Get user document mapping by ID"""
        try:
            return self.db.query(UserDocument).filter(UserDocument.id == mapping_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting user document mapping {mapping_id}: {str(e)}")
            raise
    
    def get_by_user_and_document(self, user_phone_number: str, document_id: int) -> Optional[UserDocument]:
        """Get mapping by user and document"""
        try:
            return self.db.query(UserDocument).filter(
                UserDocument.user_phone_number == user_phone_number,
                UserDocument.document_id == document_id
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting user document mapping: {str(e)}")
            raise
    
    def get_user_documents(self, user_phone_number: str) -> List[UserDocument]:
        """Get all documents assigned to a user"""
        try:
            return self.db.query(UserDocument).filter(
                UserDocument.user_phone_number == user_phone_number
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting user documents for {user_phone_number}: {str(e)}")
            raise
    
    def get_document_users(self, document_id: int) -> List[UserDocument]:
        """Get all users assigned to a document"""
        try:
            return self.db.query(UserDocument).filter(
                UserDocument.document_id == document_id
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting document users for {document_id}: {str(e)}")
            raise
    
    def create(self, user_phone_number: str, document_id: int,
               assigned_by: Optional[str] = None, notes: Optional[str] = None) -> UserDocument:
        """Create a new user document mapping"""
        try:
            # Check if mapping already exists
            existing = self.get_by_user_and_document(user_phone_number, document_id)
            if existing:
                return existing
            
            mapping = UserDocument(
                user_phone_number=user_phone_number,
                document_id=document_id,
                assigned_by=assigned_by,
                notes=notes,
            )
            self.db.add(mapping)
            self.db.commit()
            self.db.refresh(mapping)
            return mapping
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error creating user document mapping: {str(e)}")
            raise
    
    def update(self, mapping_id: int, **kwargs) -> Optional[UserDocument]:
        """Update user document mapping by ID"""
        try:
            mapping = self.get_by_id(mapping_id)
            if not mapping:
                return None
            
            for key, value in kwargs.items():
                if hasattr(mapping, key):
                    setattr(mapping, key, value)
            
            mapping.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(mapping)
            return mapping
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error updating user document mapping {mapping_id}: {str(e)}")
            raise
    
    def delete(self, mapping_id: int) -> bool:
        """Delete user document mapping by ID"""
        try:
            mapping = self.get_by_id(mapping_id)
            if not mapping:
                return False
            
            self.db.delete(mapping)
            self.db.commit()
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error deleting user document mapping {mapping_id}: {str(e)}")
            raise
    
    def delete_by_user_and_document(self, user_phone_number: str, document_id: int) -> bool:
        """Delete mapping by user and document"""
        try:
            mapping = self.get_by_user_and_document(user_phone_number, document_id)
            if not mapping:
                return False
            
            self.db.delete(mapping)
            self.db.commit()
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error deleting user document mapping: {str(e)}")
            raise
