"""
LLM Service - Abstracted LLM provider interface
Supports multiple providers (Gemini, OpenAI, Anthropic, etc.)
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


class GeminiLLMService(LLMService):
    """Google Gemini LLM service implementation"""
    
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or settings.LLM_API_KEY
        self.model_name = model_name or settings.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("Gemini API key is required. Set LLM_API_KEY in environment.")
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"✅ Initialized Gemini LLM with model: {self.model_name}")
        except ImportError:
            raise ImportError("google-generativeai package is required. Install with: pip install google-generativeai")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini LLM: {str(e)}")
            raise
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None,
                 temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None,
                 **kwargs) -> str:
        """Generate text from prompt"""
        try:
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            generation_config = {
                "temperature": temperature or settings.LLM_TEMPERATURE,
            }
            if max_tokens:
                generation_config["max_output_tokens"] = max_tokens
            
            response = self.model.generate_content(
                full_prompt,
                generation_config=generation_config,
            )
            
            return response.text
        except Exception as e:
            logger.error(f"Error generating text with Gemini: {str(e)}")
            raise
    
    def generate_with_context(self, messages: List[Dict[str, str]],
                             temperature: Optional[float] = None,
                             max_tokens: Optional[int] = None,
                             **kwargs) -> str:
        """Generate text with conversation context"""
        try:
            # Convert messages to Gemini format
            chat = self.model.start_chat(history=[])
            
            # Send all messages except the last one as history
            for msg in messages[:-1]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    chat.send_message(content)
                elif role == "assistant":
                    # Gemini doesn't support assistant messages in history the same way
                    # We'll include it in the prompt instead
                    pass
            
            # Send the last message
            last_message = messages[-1].get("content", "")
            
            generation_config = {
                "temperature": temperature or settings.LLM_TEMPERATURE,
            }
            if max_tokens:
                generation_config["max_output_tokens"] = max_tokens
            
            response = chat.send_message(last_message, generation_config=generation_config)
            return response.text
        except Exception as e:
            logger.error(f"Error generating text with context: {str(e)}")
            raise


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
    Factory function to get LLM service based on provider
    
    Args:
        provider: LLM provider name (gemini, groq, openai, etc.)
        api_key: API key for the provider
        model_name: Model name to use
        
    Returns:
        LLMService instance
    """
    provider = provider or settings.LLM_PROVIDER
    
    if provider.lower() == "gemini":
        return GeminiLLMService(api_key=api_key, model_name=model_name)
    elif provider.lower() == "groq":
        return GroqLLMService(api_key=api_key, model_name=model_name)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}. Supported: gemini, groq")
