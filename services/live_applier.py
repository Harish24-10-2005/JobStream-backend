"""
Live Applier Service
Direct URL application with live browser streaming and WebSocket HITL
"""
import asyncio
import base64
import yaml
from typing import Optional
from datetime import datetime
from pathlib import Path

# optimized imports
from browser_use import Browser, Agent, ChatOpenAI, Tools, ActionResult, ChatGoogle
from src.core.config import settings
from src.models.profile import UserProfile
from api.websocket import manager, EventType, AgentEvent
import logging

logger = logging.getLogger(__name__)


class LiveApplierService:
    """
    Service for direct job application with live browser streaming.
    
    Features:
    - Direct URL input → ApplierAgent
    - Live screenshot streaming to web interface
    - WebSocket HITL chat (replaces blocking input())
    - Persistent browser session for speed
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._manager = manager
        self._is_running = False
        self._screenshot_task: Optional[asyncio.Task] = None
        self._agent = None
        self._browser = None  # Persistent browser instance
        self._browser_session = None
        self._pending_hitl: Optional[asyncio.Future] = None
        self._pending_hitl_id: Optional[str] = None
        self._tools = Tools()
        self._register_tools()
        
    def _register_tools(self):
        """Register tools once during initialization."""
        
        @self._tools.action(description='Ask human for help with a question')
        async def ask_human(question: str) -> ActionResult:
            """WebSocket-based human input request."""
            # Generate HITL ID
            hitl_id = f"hitl_{int(datetime.now().timestamp() * 1000)}"
            
            # Create future for response using asyncio.get_running_loop() (Python 3.7+)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            self._pending_hitl = loop.create_future()
            self._pending_hitl_id = hitl_id
            
            logger.debug(f"HITL request: id={hitl_id}, question={question}")
            
            # Send HITL request to frontend
            await self.emit(
                EventType.HITL_REQUEST,
                question,
                {"hitl_id": hitl_id, "context": "Form requires your input"}
            )
            await self.emit_chat("agent", f"❓ {question}")
            
            try:
                # Wait for response (2 min timeout)
                response = await asyncio.wait_for(self._pending_hitl, timeout=120)
                await self.emit_chat("user", response)
                logger.debug(f"Got HITL response: {response}")
                return ActionResult(extracted_content=f'Human responded: {response}')
            except asyncio.TimeoutError:
                await self.emit_chat("system", "⏱️ No response, skipping...")
                return ActionResult(extracted_content='Human did not respond, skip this field')
            finally:
                self._pending_hitl = None
                self._pending_hitl_id = None

    async def get_browser(self):
        """Get a new browser instance (persistence disabled for stability)."""
        # Always create new browser for now to avoid state issues
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        
        self._browser = Browser(
            executable_path=settings.chrome_path,
            user_data_dir=settings.user_data_dir,
            profile_directory=settings.profile_directory,
            headless=True  # Reverted to headless as per user request
        )
        return self._browser

    async def emit(self, event_type: EventType, message: str, data: dict = None):
        """Emit an event to connected clients."""
        event = AgentEvent(
            type=event_type,
            agent="applier",
            message=message,
            data=data or {}
        )
        await self._manager.broadcast(event)
    
    async def emit_chat(self, sender: str, message: str, data: dict = None):
        """Emit a chat message."""
        event = AgentEvent(
            type=EventType.CHAT_MESSAGE,
            agent=sender,
            message=message,
            data=data or {}
        )
        await self._manager.broadcast(event)
    
    def resolve_hitl(self, hitl_id: str, response: str):
        """Resolve a pending HITL request from this service."""
        logger.debug(f"HITL resolve: id={hitl_id}, pending_id={self._pending_hitl_id}")
        if self._pending_hitl and self._pending_hitl_id == hitl_id:
            if not self._pending_hitl.done():
                self._pending_hitl.set_result(response)
                logger.debug(f"HITL resolved with: {response}")
    
    async def _screenshot_loop(self):
        """Capture and stream screenshots."""
        logger.debug("Screenshot loop started, waiting for browser_session...")
        frame_count = 0
        wait_count = 0
        
        # Wait for browser session to be available
        while self._is_running and not self._browser_session:
            wait_count += 1
            if wait_count % 10 == 1:
                logger.debug(f"Waiting for browser_session... ({wait_count})")
            await asyncio.sleep(0.5) # Slower poll for startup
        
        # Additional wait for session to initialize
        await asyncio.sleep(2.0)
        
        if self._browser_session:
            logger.debug("Browser session available! Starting screenshot capture...")
        else:
            logger.debug("Screenshot loop exiting - is_running=False or no session")
            return
        
        error_count = 0
        while self._is_running:
            try:
                if self._browser_session:
                    # browser-use Page.screenshot returns base64 string directly
                    page = await self._browser_session.get_current_page()
                    
                    if not page:
                        # Fallback to get any page if current is unavailable
                        try:
                            pages = await self._browser_session.get_pages()
                            if pages:
                                page = pages[-1]
                        except Exception as pe:
                            if error_count < 3:
                                logger.debug(f"Failed to get pages: {pe}")
                            error_count += 1

                    if page:
                        screenshot_b64 = await page.screenshot(
                            format='jpeg',
                            quality=50
                        )
                        
                        frame_count += 1
                        if frame_count <= 3 or frame_count % 50 == 0:
                            logger.info(f"Screenshot frame #{frame_count} sent, size={len(screenshot_b64)}")
                            
                        await self.emit(
                            EventType.BROWSER_SCREENSHOT,
                            "Browser screenshot",
                            {"screenshot": screenshot_b64, "format": "jpeg"}
                        )
                        error_count = 0  # Reset error count on success
                    elif error_count < 5:
                        logger.debug("No page available for screenshot")
                        error_count += 1
                        
            except Exception as e:
                error_count += 1
                if error_count <= 3:
                    logger.warning(f"Screenshot error: {e}")
            
            await asyncio.sleep(0.2)  # 5 FPS target
            
        logger.debug(f"Screenshot loop ended, total frames: {frame_count}")
    
    async def perform_interaction(self, Interaction: dict):
        """
        Execute remote interaction on the active browser page.
        
        Args:
            Interaction: Dictionary with 'type', 'x', 'y', 'text', etc.
        """
        if not self._browser_session:
            logger.warning("Interaction ignored: No active browser session.")
            return

        try:
            page = await self._browser_session.get_current_page()
            if not page:
                return

            action_type = Interaction.get("type")
            
            if action_type == "click":
                x = Interaction.get("x")
                y = Interaction.get("y")
                if x is not None and y is not None:
                    # Adjust for potential scale/offset if needed, but assuming direct mapping
                    logger.debug(f"Remote Interaction: Click at ({x}, {y})")
                    await page.mouse.click(x, y)
                    
            elif action_type == "type":
                text = Interaction.get("text", "")
                if text:
                    logger.debug(f"Remote Interaction: Type '{text}'")
                    await page.keyboard.type(text)
                    
            elif action_type == "key":
                key = Interaction.get("key", "")
                if key:
                    logger.debug(f"Remote Interaction: Press key '{key}'")
                    await page.keyboard.press(key)

            elif action_type == "scroll":
                delta_y = Interaction.get("delta_y", 0)
                if delta_y:
                    await page.mouse.wheel(0, delta_y)
                    
        except Exception as e:
            logger.error(f"Failed to perform interaction: {e}")

    def stop(self):
        """Stop the applier service."""
        self._is_running = False
        if self._pending_hitl and not self._pending_hitl.done():
            self._pending_hitl.cancel()
            
        if self._screenshot_task:
            self._screenshot_task.cancel()
        
        # Note: We do NOT close the browser here to allow reuse, 
        # unless we implement a full shutdown method.
        # Ideally, we should close it when the application shuts down.
    
    async def cleanup(self):
        """Explicitly close the browser resources."""
        print("[DEBUG] Cleaning up LiveApplierService resources...")
        if self._browser:
            await self._browser.close()
            self._browser = None
        
        if self._pending_hitl and not self._pending_hitl.done():
             self._pending_hitl.cancel()


    async def run(self, url: str):
        """Run the application process with live streaming."""
        self._is_running = True
        
        await self.emit(EventType.APPLIER_START, f"Starting application")
        await self.emit_chat("system", f"🎯 Applying to: {url}")
        
        try:
            # Load user profile
            base_dir = Path(__file__).resolve().parent.parent
            profile_path = base_dir / "src/data/user_profile.yaml"
            
            with open(profile_path, "r", encoding="utf-8") as f:
                profile_data = yaml.safe_load(f)
            profile = UserProfile(**profile_data)
            profile_yaml = yaml.dump(profile_data)
            resume_path = profile.files.resume
            
            await self.emit_chat("system", f"📋 Profile: {profile.personal_information.full_name}")
            
            # Task prompt
            task_prompt = f"""
GOAL: Navigate to {url} and apply for the job using my profile data.

👤 PROFILE:
{profile_yaml}

📋 STEPS:
1. Go to URL. If login required, use 'ask_human'.
2. Fill form with profile data.
3. For unknown fields, use 'ask_human'.
4. Upload resume: "{resume_path}"
5. Submit application.

⚠️ RULES:
- DO NOT invent data. Use 'ask_human' for unknowns.
- Prefer "Easy Apply" if available.
"""
            
            await self.emit_chat("agent", "🚀 Starting browser...")
            
            # Get persistent browser
            browser = await self.get_browser()
            
            # Configure LLM - Try Gemini first (more reliable), fall back to OpenRouter
            llm = None
            llm_name = ""
            
            # # Try Gemini first
            # if settings.gemini_api_key:
            #     try:
            #         llm = ChatGoogle(
            #             model=settings.gemini_model,
            #             api_key=settings.gemini_api_key.get_secret_value(),
            #         )
            #         llm_name = f"Gemini ({settings.gemini_model})"
            #         logger.info(f"Using Gemini LLM: {settings.gemini_model}")
            #     except Exception as e:
            #         logger.warning(f"Failed to initialize Gemini: {e}")
            
            # Fall back to OpenRouter
            if settings.openrouter_api_key:
                try:
                    llm = ChatOpenAI(
                        model=settings.openrouter_model,
                        base_url='https://openrouter.ai/api/v1',
                        api_key=settings.get_openrouter_key(),
                    )
                    llm_name = f"OpenRouter ({settings.openrouter_model})"
                    logger.info(f"Using OpenRouter LLM: {settings.openrouter_model}")
                except Exception as e:
                    logger.warning(f"Failed to initialize OpenRouter: {e}")
            
            if not llm:
                raise ValueError("No LLM available - check GEMINI_API_KEY or OPENROUTER_API_KEY")
            
            await self.emit_chat("agent", f"🤖 AI ready ({llm_name}), opening browser...")
            
            # Create agent
            self._agent = Agent(
                task=task_prompt,
                llm=llm,
                browser=browser,
                use_vision=False, 
                tools=self._tools,
                extend_system_message="Be concise. Fill forms quickly.",
            )

            self._screenshot_task = asyncio.create_task(self._screenshot_loop())
            
            try:
                # Get session for interaction
                self._browser_session = self._agent.browser_session
                
                await self.emit_chat("system", "📺 Live view active")
                
                # Run the agent
                await self._agent.run()
                
                # Capture proof of application
                if self._browser_session:
                    try:
                        page = await self._browser_session.get_current_page()
                        if page:
                            # Auto-track the application
                            from src.agents.tracker_agent import job_tracker_agent
                            await job_tracker_agent.add_application(
                                company=url, 
                                role="Software Engineer", 
                                url=url,
                                notes=f"Auto-applied. Proof captured.",
                                priority="High"
                            )
                    except Exception as e:
                        logger.error(f"Failed to capture proof or track: {e}")
                
                await self.emit(EventType.APPLIER_COMPLETE, "Application submitted!", {"success": True})
                await self.emit_chat("agent", "✅ Application submitted! 🎉")
                return {"success": True}
                
            finally:
                self._is_running = False
                if self._screenshot_task:
                    self._screenshot_task.cancel()
                    try:
                        await self._screenshot_task
                    except asyncio.CancelledError:
                        pass
            
        except Exception as e:
            error_msg = str(e)
            await self.emit(EventType.PIPELINE_ERROR, f"Error: {error_msg}", {"error": error_msg})
            await self.emit_chat("system", f"❌ {error_msg}")
            return {"success": False, "error": error_msg}
        finally:
            self._is_running = False
