"""
API v1 router - aggregates all v1 endpoints
"""
from fastapi import APIRouter
from app.api.v1.endpoints import webhooks, whatsapp
# from app.api.v1.endpoints import users, onboarding

api_router = APIRouter()

# Include webhook router
api_router.include_router(
    webhooks.webhook_router,
    prefix="/webhooks",
    # Tags are defined at the endpoint level, no need to add here
)

# Include WhatsApp API endpoints
api_router.include_router(
    whatsapp.router,
    prefix="/whatsapp",
    tags=["whatsapp"],
)

# Add other endpoint routers as needed
# api_router.include_router(users.router, prefix="/users", tags=["users"])
# api_router.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])

@api_router.get("/", tags=["api"])
async def api_root():
    """API root endpoint"""
    return {"message": "API v1", "status": "active"}

