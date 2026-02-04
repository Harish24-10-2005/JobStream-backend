"""
LiveApplierService - Main orchestrator for job application automation.

This is the primary entry point for the Live Applier feature.
Coordinates browser, LLM, tools, and WebSocket communication.
"""

import asyncio
import logging
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from src.core.config import settings
from src.models.profile import UserProfile
from src.api.websocket import manager, EventType, AgentEvent
from src.prompts.applier_agent import get_applier_prompt

from .models import ApplierStatus, ApplierResult, AgentConfig, Timeouts
from .exceptions import ProfileNotFoundError, LLMUnavailableError, LiveApplierError
from .browser import BrowserManager
from .tools import HITLManager, create_applier_tools
from .llm_config import get_llm_client

logger = logging.getLogger(__name__)


class LiveApplierService:
    """
    Production-ready service for automated job applications.
    
    Features:
    - Direct URL input → browser-use Agent
    - Live screenshot streaming (5 FPS)
    - WebSocket HITL (Human-in-the-Loop)
    - Draft Mode for pre-submission review
    - Multi-user profile isolation
    - RAG integration for document context
    
    Example:
        applier = LiveApplierService(
            session_id="abc123",
            user_id="uuid-xxxx",
            draft_mode=True
        )
        result = await applier.run("https://company.com/jobs/12345")
    """
    
    def __init__(
        self,
        session_id: str,
        draft_mode: bool = True,
        user_id: Optional[str] = None
    ):
        """
        Initialize the Live Applier service.
        
        Args:
            session_id: Unique session identifier for WebSocket
            draft_mode: If True, pause before submit for user confirmation
            user_id: User ID for multi-user profile loading (from JWT)
        """
        self.session_id = session_id
        self.draft_mode = draft_mode
        self.user_id = user_id
        
        # Internal state
        self._status = ApplierStatus.IDLE
        self._is_running = False
        self._agent = None
        self._start_time: Optional[datetime] = None
        
        # Managers
        self._manager = manager  # WebSocket manager
        self._hitl_manager = HITLManager()
        self._browser_manager = BrowserManager(session_id, self.emit)
        
        # Tools will be created when run() is called
        self._tools = None
        
        logger.info(f"LiveApplierService initialized: session={session_id}, user={user_id}, draft={draft_mode}")
    
    # =========================================================================
    # Public API
    # =========================================================================
    
    async def run(self, url: str) -> ApplierResult:
        """
        Run the complete job application process.
        
        Args:
            url: Job application URL
        
        Returns:
            ApplierResult with success status, message, and metadata
        """
        self._start_time = datetime.now()
        self._is_running = True
        self._status = ApplierStatus.INITIALIZING
        
        await self.emit(EventType.APPLIER_START, f"Starting application")
        await self.emit_chat("system", f"🎯 Applying to: {url}")
        
        if self.draft_mode:
            await self.emit_chat("system", "📋 Draft Mode ON - You'll review before submission")
        
        try:
            # 1. Load user profile
            profile, profile_yaml, resume_path = await self._load_profile()
            await self.emit_chat("system", f"📋 Profile: {profile.personal_information.full_name}")
            
            # 2. Get LLM client
            llm, llm_name = get_llm_client()
            await self.emit_chat("agent", f"🤖 AI ready ({llm_name})")
            
            # 3. Initialize browser
            await self.emit_chat("agent", "🚀 Starting browser...")
            browser = await self._browser_manager.get_browser()
            
            # 4. Create tools
            self._tools = create_applier_tools(
                hitl_manager=self._hitl_manager,
                emit=self.emit,
                emit_chat=self.emit_chat,
                browser_manager=self._browser_manager,
                user_id=self.user_id,
                draft_mode=self.draft_mode
            )
            
            # 5. Generate task prompt
            task_prompt = get_applier_prompt(
                url=url,
                profile_yaml=profile_yaml,
                resume_path=resume_path,
                draft_mode=self.draft_mode
            )
            
            # 6. Create and run agent
            result = await self._run_agent(browser, llm, task_prompt, url)
            return result
            
        except ProfileNotFoundError as e:
            await self.emit_chat("system", "❌ Profile not found. Please complete onboarding.")
            await self.emit(EventType.PIPELINE_ERROR, "User profile not found")
            return self._create_result(False, url, error=str(e))
            
        except LLMUnavailableError as e:
            await self.emit_chat("system", f"❌ AI unavailable: {e.message}")
            await self.emit(EventType.PIPELINE_ERROR, e.message)
            return self._create_result(False, url, error=str(e))
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Applier error: {e}", exc_info=True)
            await self.emit(EventType.PIPELINE_ERROR, f"Error: {error_msg}", {"error": error_msg})
            await self.emit_chat("system", f"❌ {error_msg}")
            return self._create_result(False, url, error=error_msg)
            
        finally:
            self._is_running = False
            self._status = ApplierStatus.IDLE
    
    def resolve_hitl(self, hitl_id: str, response: str):
        """
        Resolve a pending HITL request.
        
        Called by WebSocket handler when user responds.
        """
        logger.debug(f"Resolving HITL: id={hitl_id}")
        self._hitl_manager.resolve(hitl_id, response)
    
    async def perform_interaction(self, interaction: dict):
        """
        Execute a remote browser interaction.
        
        Args:
            interaction: Dict with 'type' (click/type/key/scroll) and params
        """
        await self._browser_manager.perform_interaction(interaction)
    
    def stop(self):
        """Stop the applier service gracefully."""
        self._is_running = False
        self._status = ApplierStatus.CANCELLED
        self._hitl_manager.cancel()
        self._browser_manager.stop_screenshot_loop()
    
    async def cleanup(self):
        """Cleanup all resources."""
        self.stop()
        await self._browser_manager.cleanup()
    
    async def take_screenshot(self):
        """Take and emit a screenshot on demand."""
        screenshot = await self._browser_manager.capture_full_page_screenshot()
        if screenshot:
            await self.emit(
                EventType.BROWSER_SCREENSHOT,
                "Manual screenshot",
                {"screenshot": screenshot, "format": "jpeg"}
            )
    
    # =========================================================================
    # Event Emission
    # =========================================================================
    
    async def emit(self, event_type: EventType, message: str, data: dict = None):
        """Emit an event to the connected WebSocket client for this session."""
        event = AgentEvent(
            type=event_type,
            agent="applier",
            message=message,
            data=data or {}
        )
        # Send to specific session, not broadcast to all
        await self._manager.send_event(self.session_id, event)
    
    async def emit_chat(self, sender: str, message: str, data: dict = None):
        """Emit a chat message to this session."""
        event = AgentEvent(
            type=EventType.CHAT_MESSAGE,
            agent=sender,
            message=message,
            data=data or {}
        )
        # Send to specific session, not broadcast to all
        await self._manager.send_event(self.session_id, event)
    
    # =========================================================================
    # Internal Methods
    # =========================================================================
    
    async def _load_profile(self) -> tuple:
        """
        Load user profile from database or YAML.
        
        Returns:
            Tuple of (UserProfile, profile_yaml, resume_path)
        """
        profile = None
        profile_data = None
        
        if self.user_id:
            # Multi-user mode: Load from Supabase
            from src.services.user_profile_service import user_profile_service
            profile = await user_profile_service.get_profile(self.user_id)
            
            if not profile:
                raise ProfileNotFoundError(self.user_id)
            
            profile_data = profile.model_dump()
            logger.info(f"Loaded profile from database for user {self.user_id}")
        else:
            # Legacy mode: Load from YAML file
            base_dir = Path(__file__).resolve().parent.parent.parent
            profile_path = base_dir / "data/user_profile.yaml"
            
            with open(profile_path, "r", encoding="utf-8") as f:
                profile_data = yaml.safe_load(f)
            profile = UserProfile(**profile_data)
            logger.info("Loaded profile from YAML file (legacy mode)")
        
        profile_yaml = yaml.dump(profile_data)
        resume_path = profile.files.resume
        
        return profile, profile_yaml, resume_path
    
    async def _run_agent(self, browser, llm, task_prompt: str, url: str) -> ApplierResult:
        """
        Create and run the browser-use agent with retry logic.
        """
        from browser_use import Agent
        
        self._status = ApplierStatus.RUNNING
        
        # Track if we've set the browser session
        session_set = False
        
        def on_step_callback(*args, **kwargs):
            """Set browser session after agent connects (accepts any arguments for compatibility)."""
            nonlocal session_set
            if not session_set and self._agent:
                # Try to get browser_session from agent
                browser_session = getattr(self._agent, 'browser_session', None)
                if browser_session:
                    logger.info("Setting browser session from step callback")
                    self._browser_manager.set_browser_session(browser_session)
                    session_set = True
        
        # Create agent
        self._agent = Agent(
            task=task_prompt,
            llm=llm,
            browser=browser,
            use_vision=AgentConfig.USE_VISION,
            tools=self._tools,
            extend_system_message="Be concise. Fill forms quickly. RESPONSE MUST BE RAW JSON. NO MARKDOWN. NO CODE BLOCKS.",
            max_failures=AgentConfig.MAX_FAILURES,
            register_new_step_callback=on_step_callback,
        )
        
        # Try to set browser session immediately if available
        if hasattr(self._agent, 'browser_session') and self._agent.browser_session:
            logger.info("Setting browser session immediately after agent creation")
            self._browser_manager.set_browser_session(self._agent.browser_session)
            session_set = True
        
        # Start screenshot streaming (will wait for session if not yet set)
        self._browser_manager.start_screenshot_loop()
        
        try:
            await self.emit_chat("system", "📺 Live view starting...")
            
            # Run with retry logic for transient LLM errors
            for attempt in range(AgentConfig.MAX_LLM_RETRIES):
                try:
                    await self._agent.run()
                    break  # Success
                except Exception as e:
                    if self._is_llm_error(e) and attempt < AgentConfig.MAX_LLM_RETRIES - 1:
                        wait_time = (attempt + 1) * Timeouts.LLM_RETRY_BASE
                        msg = f"⚠️ LLM Error ({type(e).__name__}). Retrying in {wait_time}s..."
                        logger.warning(f"{msg} Detail: {e}")
                        await self.emit_chat("system", msg)
                        await asyncio.sleep(wait_time)
                        continue
                    raise
            
            # Success - track the application
            await self._track_application(url)
            
            self._status = ApplierStatus.COMPLETED
            await self.emit(EventType.APPLIER_COMPLETE, "Application submitted!", {"success": True})
            await self.emit_chat("agent", "✅ Application submitted! 🎉")
            
            return self._create_result(True, url, message="Application submitted successfully")
            
        finally:
            self._browser_manager.stop_screenshot_loop()
    
    def _is_llm_error(self, e: Exception) -> bool:
        """Check if exception is a retryable LLM error."""
        error_str = str(e)
        error_type = type(e).__name__
        return (
            "ModelProviderError" in error_type or
            "ModelRateLimitError" in error_type or
            "429" in error_str
        )
    
    async def _track_application(self, url: str):
        """Track the application in the job tracker."""
        try:
            if self._browser_manager._browser_session:
                from src.agents.tracker_agent import job_tracker_agent
                await job_tracker_agent.add_application(
                    company=url,
                    role="Software Engineer",
                    url=url,
                    notes="Auto-applied via Live Applier.",
                    priority="High"
                )
        except Exception as e:
            logger.error(f"Failed to track application: {e}")
    
    def _create_result(
        self,
        success: bool,
        url: str,
        message: str = "",
        error: str = None
    ) -> ApplierResult:
        """Create an ApplierResult with timing info."""
        duration = 0.0
        if self._start_time:
            duration = (datetime.now() - self._start_time).total_seconds()
        
        return ApplierResult(
            success=success,
            status=self._status,
            url=url,
            message=message,
            error=error,
            duration_seconds=duration
        )
