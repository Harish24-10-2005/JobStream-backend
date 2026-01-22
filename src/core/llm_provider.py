"""
Unified LLM Provider with Multi-Provider Fallback
Supports: Groq → OpenRouter → Gemini with retry logic
"""
import os
import time
import logging
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
from dataclasses import dataclass

from src.core.config import settings
from src.core.console import console

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""
    GROQ = "groq"
    OPENROUTER = "openrouter"
    GEMINI = "gemini"


@dataclass
class LLMConfig:
    """Configuration for an LLM provider."""
    provider: LLMProvider
    api_key: str
    model: str
    temperature: float = 0.3
    max_tokens: int = 4096


class LLMError(Exception):
    """Base exception for LLM errors."""
    pass


class RateLimitError(LLMError):
    """Rate limit exceeded."""
    pass


class APIError(LLMError):
    """General API error."""
    pass


def exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
    """Calculate delay with exponential backoff."""
    delay = min(base_delay * (2 ** attempt), max_delay)
    return delay


class UnifiedLLM:
    """
    Unified LLM interface with multi-provider fallback.
    
    Fallback order:
    1. Groq (primary) - fastest
    2. Groq (fallback key)
    3. OpenRouter (primary)
    4. OpenRouter (fallback key)
    5. Gemini
    """
    
    def __init__(
        self,
        temperature: float = 0.3,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        self.temperature = temperature
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Build provider chain
        self.providers = self._build_provider_chain()
        self.current_provider_index = 0
        
        console.info(f"LLM initialized with {len(self.providers)} provider(s)")
    
    def _build_provider_chain(self) -> List[LLMConfig]:
        """Build ordered list of LLM providers to try."""
        providers = []
        
        # 1. Groq Primary
        if settings.groq_api_key:
            providers.append(LLMConfig(
                provider=LLMProvider.GROQ,
                api_key=settings.groq_api_key.get_secret_value(),
                model="llama-3.1-8b-instant",
                temperature=self.temperature
            ))
        
        # 2. Groq Fallback
        if settings.groq_api_key_fallback:
            providers.append(LLMConfig(
                provider=LLMProvider.GROQ,
                api_key=settings.groq_api_key_fallback.get_secret_value(),
                model="llama-3.1-8b-instant",
                temperature=self.temperature
            ))
        
        # 3. OpenRouter Primary
        if settings.openrouter_api_key:
            providers.append(LLMConfig(
                provider=LLMProvider.OPENROUTER,
                api_key=settings.openrouter_api_key.get_secret_value(),
                model=settings.openrouter_model or "qwen/qwen-2.5-coder-32b-instruct:free",
                temperature=self.temperature
            ))
        
        # 4. OpenRouter Fallback
        if settings.openrouter_api_key_fallback:
            providers.append(LLMConfig(
                provider=LLMProvider.OPENROUTER,
                api_key=settings.openrouter_api_key_fallback.get_secret_value(),
                model=settings.openrouter_model or "qwen/qwen-2.5-coder-32b-instruct:free",
                temperature=self.temperature
            ))
        
        # 5. Gemini
        if settings.gemini_api_key:
            providers.append(LLMConfig(
                provider=LLMProvider.GEMINI,
                api_key=settings.gemini_api_key.get_secret_value(),
                model=settings.gemini_model or "gemini-2.0-flash-exp",
                temperature=self.temperature
            ))
        
        if not providers:
            raise LLMError("No LLM API keys configured!")
        
        return providers
    
    def _create_llm(self, config: LLMConfig):
        """Create LLM instance based on provider."""
        if config.provider == LLMProvider.GROQ:
            from langchain_groq import ChatGroq
            return ChatGroq(
                model=config.model,
                temperature=config.temperature,
                api_key=config.api_key
            )
        
        elif config.provider == LLMProvider.OPENROUTER:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=config.model,
                temperature=config.temperature,
                api_key=config.api_key,
                base_url="https://openrouter.ai/api/v1"
            )
        
        elif config.provider == LLMProvider.GEMINI:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=config.model,
                temperature=config.temperature,
                google_api_key=config.api_key
            )
        
        else:
            raise LLMError(f"Unknown provider: {config.provider}")
    
    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if error is a rate limit error."""
        error_str = str(error).lower()
        rate_limit_indicators = [
            "rate_limit", "rate limit", "ratelimit",
            "429", "too many requests", "quota exceeded",
            "tokens per minute", "requests per minute"
        ]
        return any(indicator in error_str for indicator in rate_limit_indicators)
    
    def invoke(self, messages: List[Dict[str, str]]) -> str:
        """
        Invoke LLM with automatic fallback.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            
        Returns:
            LLM response text
        """
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
        
        # Convert to LangChain messages
        lc_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))
        
        last_error = None
        
        for provider_idx, config in enumerate(self.providers):
            for attempt in range(self.max_retries):
                try:
                    llm = self._create_llm(config)
                    result = llm.invoke(lc_messages)
                    
                    # Success!
                    if provider_idx > 0:
                        console.info(f"Using fallback: {config.provider.value}")
                    
                    return result.content
                
                except Exception as e:
                    last_error = e
                    
                    if self._is_rate_limit_error(e):
                        logger.warning(f"Rate limit on {config.provider.value}, attempt {attempt + 1}")
                        
                        if attempt < self.max_retries - 1:
                            delay = exponential_backoff(attempt, self.retry_delay)
                            console.warning(f"Rate limited, retrying in {delay:.1f}s...")
                            time.sleep(delay)
                        else:
                            # Move to next provider
                            console.warning(f"Rate limit exhausted on {config.provider.value}, trying next...")
                            break
                    else:
                        logger.error(f"LLM error on {config.provider.value}: {e}")
                        break  # Non-rate-limit error, try next provider
        
        # All providers failed
        raise LLMError(f"All LLM providers failed. Last error: {last_error}")
    
    async def ainvoke(self, messages: List[Dict[str, str]]) -> str:
        """Async version of invoke."""
        # For now, use sync invoke
        # TODO: Implement proper async support
        return self.invoke(messages)
    
    def generate_json(self, prompt: str, system_prompt: str = "") -> Dict:
        """Generate and parse JSON response."""
        import json
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt + "\nOutput only valid JSON."})
        messages.append({"role": "user", "content": prompt})
        
        response = self.invoke(messages)
        
        # Clean response
        content = response.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return {"error": str(e), "raw_response": response[:500]}


# Singleton instance
_llm_instance = None


def get_llm(temperature: float = 0.3) -> UnifiedLLM:
    """Get or create unified LLM instance."""
    global _llm_instance
    
    if _llm_instance is None:
        _llm_instance = UnifiedLLM(temperature=temperature)
    
    return _llm_instance


def reset_llm():
    """Reset LLM instance (useful for testing)."""
    global _llm_instance
    _llm_instance = None
