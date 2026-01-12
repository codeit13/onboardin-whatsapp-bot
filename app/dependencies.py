"""
FastAPI dependencies
"""
from typing import Optional
from fastapi import Header, HTTPException, status
from app.core.config import get_settings

settings = get_settings()


async def verify_webhook_secret(
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret")
) -> bool:
    """Verify webhook secret from header"""
    if not settings.WEBHOOK_SECRET:
        return True  # Skip verification if secret not configured
    
    if not x_webhook_secret or x_webhook_secret != settings.WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret",
        )
    return True


async def get_api_key(
    api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> Optional[str]:
    """Get and validate API key from header"""
    # Implement your API key validation logic here
    return api_key

