"""
LLM Service - Groq provider for RAG and text enhancement
"""
import logging
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMService(ABC):
    """Abstract base class for LLM services"""
    
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None,
                 temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None,
                 **kwargs) -> str:
        """Generate text from prompt"""
        pass
    
    @abstractmethod
    def generate_with_context(self, messages: List[Dict[str, str]],
                             temperature: Optional[float] = None,
                             max_tokens: Optional[int] = None,
                             **kwargs) -> str:
        """Generate text with conversation context"""
        pass


class GroqLLMService(LLMService):
    """Groq LLM service implementation"""
    
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'GROQ_API_KEY', None)
        self.model_name = model_name or getattr(settings, 'GROQ_MODEL_NAME', 'llama-3.1-70b-versatile')
        
        if not self.api_key:
            raise ValueError("Groq API key is required. Set GROQ_API_KEY in environment.")
        
        try:
            from groq import Groq
            self.client = Groq(api_key=self.api_key)
            logger.info(f"✅ Initialized Groq LLM with model: {self.model_name}")
        except ImportError:
            raise ImportError("groq package is required. Install with: pip install groq")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Groq LLM: {str(e)}")
            raise
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None,
                 temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None,
                 **kwargs) -> str:
        """Generate text from prompt"""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature or settings.LLM_TEMPERATURE,
                max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating text with Groq: {str(e)}")
            raise
    
    def generate_with_context(self, messages: List[Dict[str, str]],
                             temperature: Optional[float] = None,
                             max_tokens: Optional[int] = None,
                             **kwargs) -> str:
        """Generate text with conversation context"""
        try:
            # Convert messages format if needed
            formatted_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ["system", "user", "assistant"]:
                    formatted_messages.append({"role": role, "content": content})
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=formatted_messages,
                temperature=temperature or settings.LLM_TEMPERATURE,
                max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
            )
            
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating text with context: {str(e)}")
            raise


def get_llm_service(provider: Optional[str] = None,
                   api_key: Optional[str] = None,
                   model_name: Optional[str] = None) -> LLMService:
    """
    Factory function to get Groq LLM service.
    """
    return GroqLLMService(api_key=api_key, model_name=model_name)
