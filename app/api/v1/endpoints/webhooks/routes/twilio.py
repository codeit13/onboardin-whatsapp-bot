"""
Twilio WhatsApp webhook routes
"""
import json
import logging
from fastapi import APIRouter, Request, HTTPException, status, Header
from fastapi.responses import Response

from app.core.config import get_settings
from app.core.database import SessionLocal, init_database
from app.services.integrations.twilio_service import TwilioIntegrationService
from app.services.whatsapp_service import WhatsAppService
# from app.tasks.whatsapp_tasks import process_whatsapp_message  # Commented out - using direct RAG call for now
from app.services.rag.rag_service import RAGService
from app.tables.users import UserRepository

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()
twilio_service = TwilioIntegrationService()
whatsapp_service = WhatsAppService()


@router.post("/whatsapp", tags=["twilio"])
async def twilio_whatsapp_webhook(
    request: Request,
    x_twilio_signature: str = Header(None, alias="X-Twilio-Signature"),
):
    """
    Twilio WhatsApp webhook endpoint
    
    This endpoint receives messages from Twilio WhatsApp sandbox.
    Configure this URL in your Twilio Console under WhatsApp Sandbox settings.
    
    URL Format: https://your-domain.com/api/v1/webhooks/twilio/whatsapp
    """
    try:
        # Get form data (Twilio sends data as form-urlencoded)
        form_data = await request.form()
        form_dict = dict(form_data)
        
        # Log raw payload received
        logger.info("=" * 80)
        logger.info("📥 TWILIO WEBHOOK RECEIVED")
        logger.info("=" * 80)
        logger.info(f"🔗 URL: {request.url}")
        logger.info(f"🌐 Method: {request.method}")
        logger.info(f"📋 Headers:")
        for key, value in request.headers.items():
            logger.info(f"   {key}: {value}")
        logger.info(f"\n📦 Raw Form Data (as received):")
        logger.info(json.dumps(form_dict, indent=2, ensure_ascii=False))
        
        # Verify request signature using integration service
        if x_twilio_signature and settings.TWILIO_AUTH_TOKEN:
            url = str(request.url)
            if not twilio_service.verify_signature(url, form_dict, x_twilio_signature):
                logger.warning("⚠️  Invalid Twilio signature")
                # In production, you might want to reject invalid signatures
                # For now, we'll log and continue for development
            else:
                logger.info("✅ Twilio signature verified successfully")
        
        # Parse webhook payload using integration service
        message_data = twilio_service.parse_webhook_payload(form_dict)
        
        # Log parsed message data
        logger.info(f"\n📨 Parsed Message Data:")
        logger.info(json.dumps(message_data, indent=2, ensure_ascii=False))
        
        # Send typing indicator immediately (user will see "typing..." status)
        # Note: Typing indicators may not work for all message types or trial accounts
        message_sid = message_data.get("message_sid")
        if message_sid:
            result = twilio_service.send_typing_indicator(message_sid)
            if result.get("success"):
                logger.info(f"⌨️  Typing indicator sent for message: {message_sid}")
            else:
                # Log as debug since this is optional and may fail for valid reasons
                logger.debug(
                    f"⏭️  Typing indicator not sent: {result.get('reason', 'Unknown reason')}. "
                    f"This is optional and won't affect message processing."
                )
        
        # Process message directly using RAG pipeline (same as /api/v1/rag/chat endpoint)
        # TODO: Re-enable Celery task for async processing later
        # task = process_whatsapp_message.delay(message_data)
        
        from_number = message_data.get("from_number", "unknown")
        body = message_data.get("body", "")
        
        # Extract phone number (remove whatsapp: prefix)
        phone_number = from_number.replace("whatsapp:", "") if from_number.startswith("whatsapp:") else from_number
        
        logger.info(f"\n📝 Processing message directly with RAG pipeline...")
        logger.info(f"📤 From: {from_number}")
        logger.info(f"💬 Message: {body}")
        
        # Get database session (ensure database is initialized)
        init_database()
        if SessionLocal is None:
            raise RuntimeError("Database not initialized. Check DATABASE_URL configuration.")
        
        db = SessionLocal()
        try:
            # Get or create user
            user_repo = UserRepository(db)
            user = user_repo.get_by_phone(phone_number)
            if not user:
                logger.info(f"Creating new user for phone number: {phone_number}")
                user = user_repo.create(phone_number=phone_number)
            
            # Get user's name if available
            user_name = user.name if user and user.name else None
            if user_name:
                logger.info(f"User name found: {user_name}")
            
            # Use RAG service for intelligent responses (same pipeline as /api/v1/rag/chat endpoint)
            rag_service = RAGService(db)
            rag_result = rag_service.query(
                user_phone_number=phone_number,
                query=body,
                user_name=user_name,  # Pass user name for personalized responses
            )
            
            response_text = rag_result.get("response", "I didn't understand that.")
            logger.info(f"✅ Generated response: {response_text[:100]}")
            
            # Send response directly via Twilio
            whatsapp_number = from_number if from_number.startswith("whatsapp:") else f"whatsapp:{phone_number}"
            logger.info(f"📤 Sending response to {whatsapp_number}...")
            
            send_result = twilio_service.send_message(
                to=whatsapp_number,
                message=response_text,
            )
            
            logger.info(f"✅ Response sent successfully: {send_result.get('message_sid')}")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"❌ Error processing message with RAG: {str(e)}", exc_info=True)
            # Send error message to user
            try:
                whatsapp_number = from_number if from_number.startswith("whatsapp:") else f"whatsapp:{phone_number}"
                twilio_service.send_message(
                    to=whatsapp_number,
                    message="I'm sorry, I encountered an error processing your message. Please try again.",
                )
            except:
                pass  # Ignore errors in error handling
        finally:
            db.close()
        
        # Return empty TwiML response (message already sent directly via Twilio API)
        try:
            from twilio.twiml.messaging_response import MessagingResponse
            response = MessagingResponse()
            # Don't add any message - already sent directly
            empty_twiml = str(response)
        except ImportError:
            # Fallback if Twilio SDK not available
            empty_twiml = "<?xml version='1.0' encoding='UTF-8'?><Response></Response>"
        
        return Response(content=empty_twiml, media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error processing Twilio webhook: {str(e)}", exc_info=True)
        # Return error response to Twilio
        error_response = twilio_service.create_twiml_response(
            "Sorry, we encountered an error processing your message."
        )
        return Response(content=error_response, media_type="application/xml")


@router.get("/whatsapp", tags=["twilio"])
async def twilio_whatsapp_verify(request: Request):
    """
    Twilio webhook verification endpoint
    
    Twilio may send a GET request to verify the webhook URL.
    This endpoint handles that verification.
    """
    return {"status": "ok", "message": "Twilio webhook endpoint is active"}
