"""
WhatsApp bot service for handling business logic
"""
import logging
from typing import Dict, Any, Optional
from app.services.base import BaseService

logger = logging.getLogger(__name__)


class WhatsAppService(BaseService):
    """Service for WhatsApp bot business logic"""
    
    def __init__(self):
        super().__init__()
        self.user_sessions: Dict[str, Dict[str, Any]] = {}  # In-memory session storage
    
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process WhatsApp message"""
        phone_number = data.get("phone_number")
        message = data.get("message", "").strip()
        
        # Get or create user session
        session = self.get_user_session(phone_number)
        
        # Process based on current state
        result = self._process_with_state(message, session)
        
        # Update session
        self.update_user_session(phone_number, result.get("session_update", {}))
        
        return result
    
    def get_user_session(self, phone_number: str) -> Dict[str, Any]:
        """Get user session or create new one"""
        if phone_number not in self.user_sessions:
            self.user_sessions[phone_number] = {
                "state": "idle",
                "data": {},
                "step": None,
            }
        return self.user_sessions[phone_number]
    
    def update_user_session(
        self,
        phone_number: str,
        updates: Dict[str, Any],
    ) -> None:
        """Update user session"""
        if phone_number in self.user_sessions:
            self.user_sessions[phone_number].update(updates)
    
    def _process_with_state(
        self,
        message: str,
        session: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Process message based on current session state"""
        state = session.get("state", "idle")
        message_lower = message.lower().strip()
        
        # State machine for bot conversation
        if state == "idle":
            return self._handle_idle_state(message_lower, session)
        elif state == "onboarding":
            return self._handle_onboarding_state(message_lower, session)
        elif state == "document_upload":
            return self._handle_document_upload_state(message_lower, session)
        else:
            return {
                "response": "I'm not sure what to do. Type 'start' to begin.",
                "session_update": {"state": "idle"},
            }
    
    def _handle_idle_state(
        self,
        message: str,
        session: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle messages in idle state"""
        if message in ["hi", "hello", "hey", "start"]:
            return {
                "response": (
                    "Welcome! Let's start your onboarding process.\n\n"
                    "Please provide your full name:"
                ),
                "session_update": {"state": "onboarding", "step": "name"},
                "intent": "start_onboarding",
            }
        elif message in ["help", "menu"]:
            return {
                "response": (
                    "Available commands:\n"
                    "• start - Begin onboarding\n"
                    "• status - Check your status\n"
                    "• help - Show this menu"
                ),
                "intent": "help",
            }
        else:
            return {
                "response": (
                    "Hello! Type 'start' to begin onboarding or 'help' for options."
                ),
                "intent": "unknown",
            }
    
    def _handle_onboarding_state(
        self,
        message: str,
        session: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle messages during onboarding flow"""
        step = session.get("step")
        
        if step == "name":
            # Store name and ask for email
            return {
                "response": "Great! Now please provide your email address:",
                "session_update": {
                    "step": "email",
                    "data": {**session.get("data", {}), "name": message},
                },
                "intent": "collect_email",
            }
        
        elif step == "email":
            # Validate email (simple check)
            if "@" in message and "." in message:
                return {
                    "response": (
                        "Thank you! Your information has been saved.\n"
                        "Type 'start' anytime to begin again or 'help' for options."
                    ),
                    "session_update": {
                        "state": "idle",
                        "step": None,
                        "data": {**session.get("data", {}), "email": message},
                    },
                    "intent": "onboarding_complete",
                }
            else:
                return {
                    "response": "Please provide a valid email address:",
                    "intent": "invalid_email",
                }
        
        else:
            return {
                "response": "Let's start over. Please provide your full name:",
                "session_update": {"step": "name"},
                "intent": "restart",
            }
    
    def _handle_document_upload_state(
        self,
        message: str,
        session: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle document upload state"""
        # This would handle file uploads when implemented
        return {
            "response": "Document upload feature coming soon!",
            "session_update": {"state": "idle"},
            "intent": "document_upload",
        }

