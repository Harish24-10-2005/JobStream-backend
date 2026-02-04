"""
LLM provider configuration and fallback logic for the LiveApplier agent.

Provides a unified interface for LLM selection with automatic fallback:
1. Mistral (primary - best for form-filling tasks)
2. OpenRouter (fallback)
3. Raises LLMUnavailableError if none available
"""

import logging
from typing import Any, Tuple

from src.core.config import settings
from .exceptions import LLMUnavailableError
from .models import AgentConfig

logger = logging.getLogger(__name__)


def get_llm_client() -> Tuple[Any, str]:
    """
    Get configured LLM client with automatic fallback.
    
    Returns:
        Tuple of (llm_client, provider_name)
    
    Raises:
        LLMUnavailableError: If no LLM provider is available
    """
    attempted = []
    
    # Priority 1: Mistral (primary for applier tasks)
    llm, name = _try_mistral()
    if llm:
        return llm, name
    attempted.append("Mistral")
    
    # Priority 2: OpenRouter (flexible fallback)
    llm, name = _try_openrouter()
    if llm:
        return llm, name
    attempted.append("OpenRouter")
    
    # Priority 3: Gemini (secondary fallback)
    llm, name = _try_gemini()
    if llm:
        return llm, name
    attempted.append("Gemini")
    
    # No LLM available
    raise LLMUnavailableError(attempted_providers=attempted)


def _try_mistral() -> Tuple[Any, str]:
    """Try to initialize Mistral LLM."""
    if not settings.mistral_api_key:
        logger.debug("Mistral API key not configured")
        return None, ""
    
    try:
        # Lazy import to avoid loading browser_use on module import
        try:
            from browser_use.llm.mistral import ChatMistral
        except ImportError:
            from langchain_mistralai import ChatMistralAI as ChatMistral
        
        llm = ChatMistral(
            model=settings.mistral_model,
            temperature=AgentConfig.TEMPERATURE,
            api_key=settings.mistral_api_key.get_secret_value()
        )
        name = f"Mistral ({settings.mistral_model})"
        logger.info(f"Initialized LLM: {name}")
        return llm, name
        
    except Exception as e:
        logger.warning(f"Failed to initialize Mistral: {e}")
        return None, ""


def _try_openrouter() -> Tuple[Any, str]:
    """Try to initialize OpenRouter LLM."""
    if not settings.openrouter_api_key:
        logger.debug("OpenRouter API key not configured")
        return None, ""
    
    try:
        from browser_use import ChatOpenAI
        
        llm = ChatOpenAI(
            model=settings.openrouter_model,
            base_url='https://openrouter.ai/api/v1',
            api_key=settings.get_openrouter_key(),
            temperature=AgentConfig.TEMPERATURE,
        )
        name = f"OpenRouter ({settings.openrouter_model})"
        logger.info(f"Initialized LLM: {name}")
        return llm, name
        
    except Exception as e:
        logger.warning(f"Failed to initialize OpenRouter: {e}")
        return None, ""


def _try_gemini() -> Tuple[Any, str]:
    """Try to initialize Gemini LLM."""
    if not settings.gemini_api_key:
        logger.debug("Gemini API key not configured")
        return None, ""
    
    try:
        from browser_use import ChatGoogle
        
        llm = ChatGoogle(
            model=settings.gemini_model,
            api_key=settings.gemini_api_key.get_secret_value(),
            temperature=AgentConfig.TEMPERATURE,
        )
        name = f"Gemini ({settings.gemini_model})"
        logger.info(f"Initialized LLM: {name}")
        return llm, name
        
    except Exception as e:
        logger.warning(f"Failed to initialize Gemini: {e}")
        return None, ""
