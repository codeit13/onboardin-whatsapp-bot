"""
Twilio WhatsApp webhook routes
"""
import logging
from fastapi import APIRouter, Request, HTTPException, status, Header
from fastapi.responses import Response

from app.core.config import get_settings
from app.services.integrations.twilio_service import TwilioIntegrationService
from app.services.whatsapp_service import WhatsAppService
from app.tasks.whatsapp_tasks import process_whatsapp_message

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
        
        # Verify request signature using integration service
        if x_twilio_signature and settings.TWILIO_AUTH_TOKEN:
            url = str(request.url)
            if not twilio_service.verify_signature(url, form_dict, x_twilio_signature):
                logger.warning("Invalid Twilio signature")
                # In production, you might want to reject invalid signatures
                # For now, we'll log and continue for development
        
        # Parse webhook payload using integration service
        message_data = twilio_service.parse_webhook_payload(form_dict)
        
        logger.info(
            f"Received WhatsApp message from {message_data.get('from_number')}: "
            f"{message_data.get('body')[:50]}..."
        )
        
        # Process message asynchronously via Celery
        task = process_whatsapp_message.delay(message_data)
        logger.info(f"WhatsApp message task queued: {task.id}")
        
        # Return immediate response to Twilio (TwiML)
        # You can customize this response based on your bot logic
        response_message = "Message received! We'll get back to you shortly."
        
        # Create TwiML response using integration service
        twiml_response = twilio_service.create_twiml_response(response_message)
        
        return Response(content=twiml_response, media_type="application/xml")
        
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
