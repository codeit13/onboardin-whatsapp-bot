"""
Helper utility functions
"""
import hashlib
import secrets
from typing import Any, Dict
from datetime import datetime


def generate_id() -> str:
    """Generate a unique ID"""
    return secrets.token_urlsafe(16)


def hash_string(value: str) -> str:
    """Hash a string using SHA256"""
    return hashlib.sha256(value.encode()).hexdigest()


def format_datetime(dt: datetime) -> str:
    """Format datetime to ISO string"""
    return dt.isoformat()


def safe_get(data: Dict[str, Any], *keys, default: Any = None) -> Any:
    """Safely get nested dictionary value"""
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        else:
            return default
        if result is None:
            return default
    return result if result is not None else default

