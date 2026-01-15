"""
Conversation Manager - Manages conversation history and context
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.tables.conversation_history import ConversationHistoryRepository
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ConversationManager:
    """Manage conversation history and context"""
    
    def __init__(self, db: Session):
        self.db = db
        self.history_repo = ConversationHistoryRepository(db)
        self.history_limit = settings.CONVERSATION_HISTORY_LIMIT
        self.session_timeout_hours = settings.SESSION_TIMEOUT_HOURS
        logger.info("Initialized ConversationManager")
    
    def get_session_id(self, user_phone_number: str) -> str:
        """
        Get or create session ID for user
        For now, we'll use a simple session per user (can be enhanced later)
        """
        return f"session_{user_phone_number}"
    
    def add_message(self, user_phone_number: str, session_id: str,
                   message_type: str, message: str,
                   metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a message to conversation history"""
        try:
            metadata_json = None
            if metadata:
                import json
                metadata_json = json.dumps(metadata)
            
            self.history_repo.create(
                user_phone_number=user_phone_number,
                session_id=session_id,
                message_type=message_type,
                message=message,
                metadata_json=metadata_json,
            )
            logger.debug(f"Added {message_type} message to conversation history")
        except Exception as e:
            logger.error(f"Error adding message to history: {str(e)}")
            raise
    
    def get_conversation_context(self, user_phone_number: str,
                                session_id: str) -> List[Dict[str, str]]:
        """
        Get conversation context for RAG
        
        Returns:
            List of message dictionaries in format: [{"role": "user/assistant", "content": "..."}]
        """
        try:
            history = self.history_repo.get_session_history(
                user_phone_number=user_phone_number,
                session_id=session_id,
                limit=self.history_limit * 2  # Get more to filter recent
            )
            
            # Convert to message format
            messages = []
            for entry in history[-self.history_limit:]:  # Get last N messages
                role = "user" if entry.message_type == "user" else "assistant"
                messages.append({
                    "role": role,
                    "content": entry.message,
                })
            
            return messages
        except Exception as e:
            logger.error(f"Error getting conversation context: {str(e)}")
            return []
    
    def clear_session(self, user_phone_number: str, session_id: str) -> int:
        """Clear conversation history for a session"""
        try:
            count = self.history_repo.delete_session(user_phone_number, session_id)
            logger.info(f"Cleared {count} messages from session {session_id}")
            return count
        except Exception as e:
            logger.error(f"Error clearing session: {str(e)}")
            raise
