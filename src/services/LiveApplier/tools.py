"""
Custom browser-use tools for the LiveApplier agent.

Provides three key tools:
1. ask_human - WebSocket-based human input request
2. request_draft_review - Draft mode confirmation before submit
3. retrieve_user_context - RAG-based document retrieval
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Any, Callable, Awaitable, TYPE_CHECKING

from .models import Timeouts, ScreenshotConfig
from .exceptions import HITLTimeoutError

if TYPE_CHECKING:
    from browser_use import Tools
    from browser_use.agent.views import ActionResult

logger = logging.getLogger(__name__)


class HITLManager:
    """Manages Human-in-the-Loop pending requests."""
    
    def __init__(self):
        self._pending_hitl: Optional[asyncio.Future] = None
        self._pending_hitl_id: Optional[str] = None
    
    @property
    def pending_id(self) -> Optional[str]:
        return self._pending_hitl_id
    
    def create_request(self, prefix: str = "hitl") -> str:
        """Create a new HITL request and return its ID."""
        hitl_id = f"{prefix}_{int(datetime.now().timestamp() * 1000)}"
        
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        self._pending_hitl = loop.create_future()
        self._pending_hitl_id = hitl_id
        return hitl_id
    
    async def wait_for_response(self, timeout: float) -> str:
        """Wait for HITL response with timeout."""
        if not self._pending_hitl:
            raise ValueError("No pending HITL request")
        
        try:
            return await asyncio.wait_for(self._pending_hitl, timeout=timeout)
        finally:
            self._pending_hitl = None
            self._pending_hitl_id = None
    
    def resolve(self, hitl_id: str, response: str) -> bool:
        """Resolve a pending HITL request. Returns True if resolved."""
        if self._pending_hitl and self._pending_hitl_id == hitl_id:
            if not self._pending_hitl.done():
                self._pending_hitl.set_result(response)
                logger.debug(f"HITL resolved: {hitl_id} -> {response}")
                return True
        return False
    
    def cancel(self):
        """Cancel any pending HITL request."""
        if self._pending_hitl and not self._pending_hitl.done():
            self._pending_hitl.cancel()


def create_applier_tools(
    hitl_manager: HITLManager,
    emit: Callable[..., Awaitable[None]],
    emit_chat: Callable[..., Awaitable[None]],
    browser_manager: Any,
    user_id: Optional[str],
    draft_mode: bool,
) -> "Tools":
    """
    Create browser-use Tools with applier-specific actions.
    
    Args:
        hitl_manager: HITL request manager
        emit: Async function to emit events
        emit_chat: Async function to emit chat messages
        browser_manager: BrowserManager for screenshots
        user_id: User ID for RAG queries
        draft_mode: Whether draft review is enabled
    
    Returns:
        Configured Tools instance
    """
    from browser_use import Tools
    from browser_use.agent.views import ActionResult
    from src.api.websocket import EventType
    
    tools = Tools()
    draft_confirmed = False  # Track confirmation state
    
    @tools.action(description='Ask human for help with a question')
    async def ask_human(question: str) -> ActionResult:
        """
        WebSocket-based human input request.
        
        Use when:
        - CAPTCHA detected
        - Login required
        - Stuck on a field
        - Ambiguous form question
        """
        hitl_id = hitl_manager.create_request("hitl")
        logger.debug(f"HITL request: id={hitl_id}, question={question}")
        
        # Send request to frontend
        await emit(
            EventType.HITL_REQUEST,
            question,
            {"hitl_id": hitl_id, "context": "Form requires your input"}
        )
        await emit_chat("agent", f"❓ {question}")
        
        try:
            response = await hitl_manager.wait_for_response(Timeouts.HITL_RESPONSE)
            await emit_chat("user", response)
            logger.debug(f"HITL response received: {response}")
            return ActionResult(extracted_content=f'Human responded: {response}')
        except asyncio.TimeoutError:
            await emit_chat("system", "⏱️ No response, skipping...")
            return ActionResult(extracted_content='Human did not respond, skip this field')
    
    @tools.action(description='Request draft review before submitting application')
    async def request_draft_review() -> ActionResult:
        """
        Draft Mode: Pause before submitting and ask user for confirmation.
        
        Captures full-page screenshot for review.
        Default: ON (opt-out, not opt-in)
        """
        nonlocal draft_confirmed
        
        if not draft_mode:
            return ActionResult(extracted_content='Draft mode disabled, proceed to submit.')
        
        hitl_id = hitl_manager.create_request("draft")
        logger.info(f"Draft review requested: id={hitl_id}")
        
        # Capture full-page screenshot for review
        screenshot_b64 = await browser_manager.capture_full_page_screenshot()
        
        # Send draft review request to frontend
        await emit(
            EventType.DRAFT_REVIEW,
            "📋 Application ready! Please review before submitting.",
            {
                "hitl_id": hitl_id,
                "screenshot": screenshot_b64,
                "context": "Review the filled form and click Confirm to submit, or Edit to make changes."
            }
        )
        await emit_chat("agent", "📋 **Draft Ready!** Please review the form above and confirm submission.")
        
        try:
            response = await hitl_manager.wait_for_response(Timeouts.DRAFT_REVIEW)
            
            if response.lower() in ["confirm", "submit", "yes", "ok"]:
                draft_confirmed = True
                await emit_chat("user", "✅ Confirmed!")
                await emit(EventType.DRAFT_CONFIRM, "User confirmed submission")
                logger.info("Draft confirmed by user, proceeding to submit")
                return ActionResult(extracted_content='User confirmed. Click the Submit/Apply button now.')
            else:
                await emit_chat("user", f"✏️ {response}")
                await emit(EventType.DRAFT_EDIT, "User requested edits", {"feedback": response})
                logger.info(f"User requested edits: {response}")
                return ActionResult(
                    extracted_content=f'User wants changes: {response}. Make the edits, then call request_draft_review again.'
                )
                
        except asyncio.TimeoutError:
            await emit_chat("system", "⏱️ Review timed out. Proceeding with submission.")
            logger.warning("Draft review timed out, proceeding")
            return ActionResult(extracted_content='Review timed out. Proceed to submit.')
    
    @tools.action(description='Retrieve information from users documents (resume, notes, etc.)')
    async def retrieve_user_context(query: str) -> ActionResult:
        """
        RAG-based document retrieval for form filling.
        
        Use when profile summary doesn't have needed details:
        - "detailed project description"
        - "university courses taken"
        - "leadership experience"
        - "career goals"
        """
        if not user_id:
            return ActionResult(extracted_content="No user_id linked. Cannot retrieve specific documents.")
        
        try:
            from src.services.rag_service import rag_service
            results = await rag_service.query(user_id, query)
            
            if results:
                formatted = "\n\n".join([f"- {r}" for r in results])
                return ActionResult(extracted_content=f"Found relevant info:\n{formatted}")
            else:
                return ActionResult(extracted_content="No relevant info found in documents.")
        except Exception as e:
            logger.error(f"RAG tool error: {e}")
            return ActionResult(extracted_content=f"Error retrieving info: {e}")
    
    return tools
