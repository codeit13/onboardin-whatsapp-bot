"""
Custom exception classes
"""
from fastapi import HTTPException, status


class AppException(Exception):
    """Base application exception"""
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(AppException):
    """Resource not found exception"""
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=status.HTTP_404_NOT_FOUND)


class ValidationError(AppException):
    """Validation error exception"""
    def __init__(self, message: str = "Validation error"):
        super().__init__(message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class UnauthorizedError(AppException):
    """Unauthorized access exception"""
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(AppException):
    """Forbidden access exception"""
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


class WebhookError(AppException):
    """Webhook processing error"""
    def __init__(self, message: str = "Webhook processing failed"):
        super().__init__(message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

