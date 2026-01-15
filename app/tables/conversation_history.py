"""
Conversation History table - Stores chat history for context/memory
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy import Column, String, DateTime, Text, Integer, Index
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.tables.base import Base
import logging

logger = logging.getLogger(__name__)


class ConversationHistory(Base):
    """Conversation History table model"""
    __tablename__ = "conversation_history"
    __table_args__ = (
        Index('idx_user_session', 'user_phone_number', 'session_id'),
        Index('idx_user_created', 'user_phone_number', 'created_at'),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_phone_number = Column(String(20), nullable=False, index=True)
    session_id = Column(String(100), nullable=False, index=True)  # Session identifier
    message_type = Column(String(20), nullable=False)  # 'user' or 'assistant'
    message = Column(Text, nullable=False)  # The actual message content
    metadata_json = Column(Text, nullable=True)  # JSON string for additional metadata (e.g., sources used)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert conversation history to dictionary"""
        return {
            "id": self.id,
            "user_phone_number": self.user_phone_number,
            "session_id": self.session_id,
            "message_type": self.message_type,
            "message": self.message,
            "metadata_json": self.metadata_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ConversationHistoryRepository:
    """Repository for Conversation History table operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, history_id: int) -> Optional[ConversationHistory]:
        """Get conversation history by ID"""
        try:
            return self.db.query(ConversationHistory).filter(ConversationHistory.id == history_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting conversation history {history_id}: {str(e)}")
            raise
    
    def create(self, user_phone_number: str, session_id: str, message_type: str,
               message: str, metadata_json: Optional[str] = None) -> ConversationHistory:
        """Create a new conversation history entry"""
        try:
            history = ConversationHistory(
                user_phone_number=user_phone_number,
                session_id=session_id,
                message_type=message_type,
                message=message,
                metadata_json=metadata_json,
            )
            self.db.add(history)
            self.db.commit()
            self.db.refresh(history)
            return history
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error creating conversation history: {str(e)}")
            raise
    
    def get_session_history(self, user_phone_number: str, session_id: str,
                            limit: int = 50) -> List[ConversationHistory]:
        """Get conversation history for a specific session"""
        try:
            return self.db.query(ConversationHistory).filter(
                ConversationHistory.user_phone_number == user_phone_number,
                ConversationHistory.session_id == session_id
            ).order_by(ConversationHistory.created_at.asc()).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting session history: {str(e)}")
            raise
    
    def get_user_recent_history(self, user_phone_number: str, limit: int = 50) -> List[ConversationHistory]:
        """Get recent conversation history for a user"""
        try:
            return self.db.query(ConversationHistory).filter(
                ConversationHistory.user_phone_number == user_phone_number
            ).order_by(ConversationHistory.created_at.desc()).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting user recent history: {str(e)}")
            raise
    
    def delete_session(self, user_phone_number: str, session_id: str) -> int:
        """Delete all history for a session"""
        try:
            count = self.db.query(ConversationHistory).filter(
                ConversationHistory.user_phone_number == user_phone_number,
                ConversationHistory.session_id == session_id
            ).delete()
            self.db.commit()
            return count
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error deleting session history: {str(e)}")
            raise
    
    def delete_old_history(self, days: int = 90) -> int:
        """Delete conversation history older than specified days"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            count = self.db.query(ConversationHistory).filter(
                ConversationHistory.created_at < cutoff_date
            ).delete()
            self.db.commit()
            return count
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error deleting old history: {str(e)}")
            raise
