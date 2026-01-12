"""
WhatsApp API endpoints - for sending messages and managing conversations
"""
import logging
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from app.core.config import get_settings
from app.services.integrations.twilio_service import TwilioIntegrationService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()
twilio_service = TwilioIntegrationService()


class SendMessageRequest(BaseModel):
    """Request model for sending WhatsApp message"""
    to: str
    message: str
    media_url: Optional[str] = None


@router.post("/send", tags=["whatsapp"])
async def send_whatsapp_message(request: SendMessageRequest):
    """
    Send WhatsApp message via Twilio
    
    - **to**: Recipient WhatsApp number (format: whatsapp:+1234567890)
    - **message**: Message text to send
    - **media_url**: Optional media URL to send with message
    """
    try:
        result = twilio_service.send_message(
            to=request.to,
            message=request.message,
            media_url=request.media_url,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}",
        )
