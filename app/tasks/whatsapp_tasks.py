"""
WhatsApp message processing Celery tasks
"""
import logging
from typing import Dict, Any
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def process_whatsapp_message(
    self,
    message_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process incoming WhatsApp message
    
    Args:
        message_data: Message data from Twilio webhook
        
    Returns:
        Processing result
    """
    try:
        from_number = message_data.get("from_number", "unknown")
        body = message_data.get("body", "")
        message_sid = message_data.get("message_sid")
        
        logger.info("=" * 80)
        logger.info(f"🔄 Processing WhatsApp message from {from_number}: {body[:100]}")
        logger.info(f"   Message SID: {message_sid}")
        
        # Extract phone number (remove whatsapp: prefix)
        phone_number = from_number.replace("whatsapp:", "") if from_number.startswith("whatsapp:") else from_number
        
        # Process message based on content
        logger.info(f"📝 Processing message content...")
        result = _process_message_content(body, phone_number, message_data)
        logger.info(f"   Generated response: {result.get('response', 'No response')[:100]}")
        
        # Send response to user
        logger.info(f"📤 Sending response to user...")
        _handle_message_response(phone_number, body, result)
        
        logger.info(f"✅ WhatsApp message processed successfully: {message_sid}")
        logger.info("=" * 80)
        
        return {
            "success": True,
            "message_sid": message_sid,
            "from": from_number,
            "result": result,
        }
        
    except Exception as exc:
        logger.error(f"WhatsApp message processing failed: {str(exc)}", exc_info=True)
        
        # Retry on failure
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


def _process_message_content(
    body: str,
    phone_number: str,
    message_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process message content and determine response using RAG
    
    Args:
        body: Message text
        phone_number: Sender's phone number
        message_data: Full message data
        
    Returns:
        Processing result
    """
    try:
        # Initialize database session
        from app.core.database import SessionLocal, init_database
        from app.services.rag.rag_service import RAGService
        from app.tables.users import UserRepository
        
        # Initialize database if not already done
        try:
            init_database()
        except:
            pass  # Already initialized
        
        db = SessionLocal()
        try:
            # Verify user exists, create if not
            user_repo = UserRepository(db)
            user = user_repo.get_by_phone(phone_number)
            if not user:
                # Create user if doesn't exist
                logger.info(f"Creating new user for phone number: {phone_number}")
                user = user_repo.create(phone_number=phone_number)
            
            # Use RAG service for intelligent responses
            rag_service = RAGService(db)
            rag_result = rag_service.query(
                user_phone_number=phone_number,
                query=body,
            )
            
            return {
                "action": "rag_query",
                "response": rag_result.get("response", "I didn't understand that."),
                "intent": "rag_query",
                "session_id": rag_result.get("session_id"),
                "sources": rag_result.get("sources", []),
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error processing message with RAG: {str(e)}", exc_info=True)
        # Fallback to simple response
        return {
            "action": "error",
            "response": "I'm sorry, I encountered an error processing your message. Please try again.",
            "intent": "error",
        }


def _handle_message_response(
    phone_number: str,
    original_message: str,
    result: Dict[str, Any],
) -> None:
    """
    Handle sending response to WhatsApp message
    
    Args:
        phone_number: Recipient phone number
        original_message: Original message received
        result: Processing result with response text
    """
    try:
        from app.services.integrations.twilio_service import TwilioIntegrationService
        
        twilio_service = TwilioIntegrationService()
        
        response_text = result.get("response")
        if not response_text:
            logger.warning(f"No response text generated for message: {original_message}")
            return
        
        # Format phone number for WhatsApp
        whatsapp_number = phone_number
        if not whatsapp_number.startswith("whatsapp:"):
            whatsapp_number = f"whatsapp:{whatsapp_number}"
        
        logger.info(f"📤 Sending WhatsApp response to {whatsapp_number}: {response_text[:100]}")
        
        # Send response using integration service
        send_result = twilio_service.send_message(
            to=whatsapp_number,
            message=response_text,
        )
        
        logger.info(f"✅ Response sent successfully to {whatsapp_number}: {send_result.get('message_sid')}")
        
    except ValueError as e:
        # Configuration errors (missing credentials, etc.)
        logger.error(f"❌ Configuration error sending WhatsApp response: {str(e)}")
        logger.error("   Please check TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_WHATSAPP_NUMBER are set")
        # Don't raise - we don't want to fail the task if response sending fails
    except Exception as e:
        logger.error(f"❌ Failed to send WhatsApp response: {str(e)}", exc_info=True)
        # Don't raise - we don't want to fail the task if response sending fails

