"""
Twilio WhatsApp webhook routes
"""
import json
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
        
        # Process message asynchronously via Celery
        # The intelligent response will be sent by the Celery task
        task = process_whatsapp_message.delay(message_data)
        logger.info(f"\n✅ WhatsApp message task queued: {task.id}")
        logger.info(f"📤 From: {message_data.get('from_number')}")
        logger.info(f"💬 Message: {message_data.get('body')}")
        logger.info("=" * 80)
        
        # Return empty TwiML response
        # The actual intelligent response will be sent by the Celery task
        # This prevents duplicate messages
        twiml_response = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
        
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
