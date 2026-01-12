"""
Pydantic schemas for request/response models
"""
from typing import Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WebhookRequest(BaseModel):
    """Webhook request model"""
    event: str = Field(..., description="Event type")
    data: Dict[str, Any] = Field(..., description="Event data")
    timestamp: Optional[datetime] = None


class WebhookResponse(BaseModel):
    """Webhook response model"""
    success: bool
    message: str
    event: str
    task_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Error response model"""
    error: bool = True
    message: str
    details: Optional[Dict[str, Any]] = None

