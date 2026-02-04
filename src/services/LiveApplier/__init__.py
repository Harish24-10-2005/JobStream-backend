"""
LiveApplier Service - Production-Ready Job Application Automation

This module provides browser-based job application automation with:
- Live video streaming (5 FPS JPEG)
- Human-in-the-Loop (HITL) intervention via WebSocket
- Draft Mode for pre-submission review
- Multi-user profile isolation
- RAG-powered document retrieval

Usage:
    from src.services.LiveApplier import LiveApplierService
    
    applier = LiveApplierService(session_id="abc", user_id="uuid")
    result = await applier.run("https://example.com/job/12345")
"""

from .service import LiveApplierService
from .models import ApplierStatus, ApplierResult, Timeouts, ScreenshotConfig, AgentConfig
from .browser import BrowserManager
from .tools import HITLManager, create_applier_tools
from .llm_config import get_llm_client
from .exceptions import (
    LiveApplierError,
    ProfileNotFoundError,
    BrowserConnectionError,
    LLMUnavailableError,
    HITLTimeoutError,
)

__all__ = [
    # Main service
    "LiveApplierService",
    # Models
    "ApplierStatus",
    "ApplierResult",
    "Timeouts",
    "ScreenshotConfig",
    "AgentConfig",
    # Managers (for testing/advanced usage)
    "BrowserManager",
    "HITLManager",
    "create_applier_tools",
    "get_llm_client",
    # Exceptions
    "LiveApplierError",
    "ProfileNotFoundError",
    "BrowserConnectionError",
    "LLMUnavailableError",
    "HITLTimeoutError",
]
