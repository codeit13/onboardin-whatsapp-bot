"""
Users table - User information with phone number as primary key
"""
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Boolean
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.tables.base import Base
import logging

logger = logging.getLogger(__name__)


class User(Base):
    """User table model"""
    __tablename__ = "users"
    
    phone_number = Column(String(20), primary_key=True, index=True)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    metadata_json = Column(Text, nullable=True)  # JSON string for additional metadata
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary"""
        return {
            "phone_number": self.phone_number,
            "name": self.name,
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active,
            "metadata_json": self.metadata_json,
        }


class UserRepository:
    """Repository for User table operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_phone(self, phone_number: str) -> Optional[User]:
        """Get user by phone number"""
        try:
            return self.db.query(User).filter(User.phone_number == phone_number).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting user by phone {phone_number}: {str(e)}")
            raise
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        try:
            return self.db.query(User).filter(User.email == email).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting user by email {email}: {str(e)}")
            raise
    
    def create(self, phone_number: str, name: Optional[str] = None, 
               email: Optional[str] = None, metadata_json: Optional[str] = None) -> User:
        """Create a new user"""
        try:
            user = User(
                phone_number=phone_number,
                name=name,
                email=email,
                metadata_json=metadata_json,
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            return user
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error creating user {phone_number}: {str(e)}")
            raise
    
    def update(self, phone_number: str, **kwargs) -> Optional[User]:
        """Update user by phone number"""
        try:
            user = self.get_by_phone(phone_number)
            if not user:
                return None
            
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            
            user.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(user)
            return user
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error updating user {phone_number}: {str(e)}")
            raise
    
    def delete(self, phone_number: str) -> bool:
        """Delete user by phone number"""
        try:
            user = self.get_by_phone(phone_number)
            if not user:
                return False
            
            self.db.delete(user)
            self.db.commit()
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error deleting user {phone_number}: {str(e)}")
            raise
    
    def list_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        """List all users with pagination"""
        try:
            return self.db.query(User).offset(skip).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Error listing users: {str(e)}")
            raise
