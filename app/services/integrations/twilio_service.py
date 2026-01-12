"""
Twilio integration service - handles Twilio-specific adapter logic
"""
import logging
from typing import Dict, Any, Optional
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TwilioIntegrationService:
    """
    Twilio integration service - adapter for Twilio webhook format
    
    Responsibilities:
    - Verify Twilio webhook signatures
    - Parse Twilio webhook payloads
    - Format TwiML responses
    - Convert Twilio format to internal format
    """
    
    def __init__(self):
        self.validator = None
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            try:
                from twilio.request_validator import RequestValidator
                self.validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
            except ImportError:
                logger.warning("Twilio SDK not installed")
    
    def verify_signature(
        self,
        url: str,
        params: Dict[str, Any],
        signature: str,
    ) -> bool:
        """
        Verify Twilio webhook request signature
        
        Args:
            url: The full URL of the request
            params: Request parameters (form data)
            signature: X-Twilio-Signature header value
            
        Returns:
            True if signature is valid
        """
        if not self.validator:
            logger.warning("Twilio validator not initialized, skipping signature verification")
            return True  # Skip verification if credentials not configured
        
        return self.validator.validate(url, params, signature)
    
    def parse_webhook_payload(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Twilio WhatsApp webhook payload into internal format
        
        Args:
            form_data: Form data from Twilio webhook
            
        Returns:
            Parsed message data in internal format
        """
        return {
            "message_sid": form_data.get("MessageSid"),
            "account_sid": form_data.get("AccountSid"),
            "from_number": form_data.get("From"),  # Format: whatsapp:+1234567890
            "to_number": form_data.get("To"),  # Your Twilio WhatsApp number
            "body": form_data.get("Body", ""),
            "num_media": form_data.get("NumMedia", "0"),
            "profile_name": form_data.get("ProfileName", ""),
            "wa_id": form_data.get("WaId", ""),  # WhatsApp ID
            "timestamp": form_data.get("Timestamp"),
        }
    
    def create_twiml_response(self, message: str) -> str:
        """
        Create TwiML response for Twilio
        
        Args:
            message: Message text to send back
            
        Returns:
            TwiML XML string
        """
        try:
            from twilio.twiml.messaging_response import MessagingResponse
            response = MessagingResponse()
            response.message(message)
            return str(response)
        except ImportError:
            logger.error("Twilio SDK not installed, returning basic TwiML")
            return f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{message}</Message></Response>"
    
    def create_twiml_media_response(self, message: str, media_url: str) -> str:
        """
        Create TwiML response with media
        
        Args:
            message: Message text
            media_url: URL of media to send
            
        Returns:
            TwiML XML string
        """
        try:
            from twilio.twiml.messaging_response import MessagingResponse, Message
            response = MessagingResponse()
            msg = Message()
            msg.body(message)
            msg.media(media_url)
            response.append(msg)
            return str(response)
        except ImportError:
            logger.error("Twilio SDK not installed, returning basic TwiML")
            return f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{message}</Message></Response>"
    
    def send_typing_indicator(self, message_sid: str) -> Dict[str, Any]:
        """
        Send typing indicator to WhatsApp user
        
        This shows the "typing..." indicator to the user while processing their message.
        The indicator automatically disappears when a message is sent or after 25 seconds.
        
        Uses Twilio's Messaging API v2 Typing Indicators endpoint.
        
        Args:
            message_sid: The SID of the message being responded to (from webhook)
                        Format: SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        
        Returns:
            Result of sending typing indicator
        
        Raises:
            ValueError: If Twilio credentials are not configured
        """
        # Check credentials first and return gracefully if not configured
        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
            logger.warning("Twilio credentials not configured, skipping typing indicator")
            return {
                "success": False,
                "message_sid": message_sid,
                "reason": "Twilio credentials not configured",
            }
        
        try:
            # Twilio SDK includes requests library as a dependency
            # Use requests to call Twilio's Typing Indicators API
            import requests
            
            url = "https://messaging.twilio.com/v2/Indicators/Typing.json"
            auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            
            # Use data-urlencode format as per Twilio documentation
            # This ensures proper encoding of parameters
            data = {
                "messageId": message_sid,
                "channel": "whatsapp"
            }
            
            # Use requests with proper headers
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            response = requests.post(
                url,
                auth=auth,
                data=data,
                headers=headers,
                timeout=5
            )
            
            # Check response status
            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"✅ Typing indicator sent for message: {message_sid}")
                return {
                    "success": True,
                    "message_sid": message_sid,
                    "result": result,
                }
            else:
                # Log the error but don't fail - typing indicator is optional
                error_detail = response.text
                logger.warning(
                    f"⚠️  Typing indicator API returned {response.status_code}: {error_detail}. "
                    f"This may be expected for inbound messages or trial accounts."
                )
                return {
                    "success": False,
                    "message_sid": message_sid,
                    "reason": f"API returned {response.status_code}",
                    "error": error_detail,
                }
            
        except ImportError:
            logger.warning("requests library not available, skipping typing indicator")
            return {
                "success": False,
                "message_sid": message_sid,
                "reason": "requests library not available",
            }
        except requests.exceptions.RequestException as e:
            # Handle network/request errors gracefully
            logger.warning(f"⚠️  Network error sending typing indicator: {str(e)}")
            return {
                "success": False,
                "message_sid": message_sid,
                "reason": f"Network error: {str(e)}",
            }
        except Exception as e:
            # Handle any other errors gracefully
            logger.warning(f"⚠️  Error sending typing indicator: {str(e)}")
            return {
                "success": False,
                "message_sid": message_sid,
                "reason": f"Error: {str(e)}",
            }
    
    def send_message(
        self,
        to: str,
        message: str,
        media_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send WhatsApp message via Twilio API
        
        Args:
            to: Recipient WhatsApp number (format: whatsapp:+1234567890)
            message: Message text to send
            media_url: Optional media URL to send with message
            
        Returns:
            Message sending result
        """
        try:
            from twilio.rest import Client
            
            if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
                raise ValueError("Twilio credentials not configured")
            
            if not settings.TWILIO_WHATSAPP_NUMBER:
                raise ValueError("Twilio WhatsApp number not configured")
            
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            
            if media_url:
                message_obj = client.messages.create(
                    body=message,
                    media_url=[media_url],
                    from_=settings.TWILIO_WHATSAPP_NUMBER,
                    to=to,
                )
            else:
                message_obj = client.messages.create(
                    body=message,
                    from_=settings.TWILIO_WHATSAPP_NUMBER,
                    to=to,
                )
            
            return {
                "success": True,
                "message_sid": message_obj.sid,
                "status": message_obj.status,
                "to": to,
            }
        except ImportError:
            raise ValueError("Twilio SDK not installed")
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}", exc_info=True)
            raise
