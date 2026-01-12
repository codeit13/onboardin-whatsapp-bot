"""
Base service class
"""
from abc import ABC
from typing import Any, Dict, Optional


class BaseService(ABC):
    """Base service class for business logic"""
    
    def __init__(self):
        pass
    
    def validate(self, data: Dict[str, Any]) -> bool:
        """Validate service input data"""
        return True
    
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process service logic"""
        raise NotImplementedError("Subclasses must implement process method")

