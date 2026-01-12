"""
Main webhook router - aggregates all webhook routes
"""
from fastapi import APIRouter
from app.api.v1.endpoints.webhooks.routes import twilio

webhook_router = APIRouter()

# Include provider-specific webhook routes
webhook_router.include_router(
    twilio.router,
    prefix="/twilio",
    # Tags are defined at the endpoint level, no need to add here
)

# Add more providers as needed:
# webhook_router.include_router(stripe.router, prefix="/stripe", tags=["webhooks", "stripe"])
