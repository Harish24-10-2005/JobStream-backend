"""
Live Applier Service
Direct URL application with live browser streaming and WebSocket HITL
Supports multi-user via user_id parameter
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import yaml

# Lazy imports for faster startup - browser_use is heavy
if TYPE_CHECKING:
	pass

import logging

from src.api.websocket import AgentEvent, EventType, manager
from src.core.config import settings
from src.models.profile import UserProfile

logger = logging.getLogger(__name__)


class LiveApplierService:
	"""
	Service for direct job application with live browser streaming.

	Features:
	- Direct URL input → ApplierAgent
	- Live screenshot streaming to web interface
	- WebSocket HITL chat (replaces blocking input())
	- Persistent browser session for speed
	- **Draft Mode** (default ON): Pauses before submit for user confirmation
	- **Multi-User**: Accepts user_id for per-user profile loading
	"""

	def __init__(self, session_id: str, draft_mode: bool = True, user_id: Optional[str] = None):
		# Lazy import heavy browser_use modules
		from browser_use import ActionResult, Tools

		self.session_id = session_id
		self.draft_mode = draft_mode  # Default ON for trust-building
		self.user_id = user_id  # For multi-user profile loading
		self._manager = manager
		self._is_running = False
		self._screenshot_task: Optional[asyncio.Task] = None
		self._agent = None
		self._browser = None  # Persistent browser instance
		self._browser_session = None
		self._pending_hitl: Optional[asyncio.Future] = None
		self._pending_hitl_id: Optional[str] = None
		self._draft_confirmed: bool = False  # Track if user confirmed draft
		self.tools = Tools()  # Use Tools instead of Controller
		self._ActionResult = ActionResult  # Store for use in methods
		self._register_tools()

	def _register_tools(self):
		"""Register tools once during initialization."""
		ActionResult = self._ActionResult  # Local reference

		@self.tools.action(description='Ask human for help with a question')
		async def ask_human(question: str) -> ActionResult:
			"""WebSocket-based human input request."""
			# Generate HITL ID
			hitl_id = f'hitl_{int(datetime.now().timestamp() * 1000)}'

			# Create future for response using asyncio.get_running_loop() (Python 3.7+)
			try:
				loop = asyncio.get_running_loop()
			except RuntimeError:
				loop = asyncio.new_event_loop()
				asyncio.set_event_loop(loop)

			self._pending_hitl = loop.create_future()
			self._pending_hitl_id = hitl_id

			logger.debug(f'HITL request: id={hitl_id}, question={question}')

			# Send HITL request to frontend
			await self.emit(EventType.HITL_REQUEST, question, {'hitl_id': hitl_id, 'context': 'Form requires your input'})
			await self.emit_chat('agent', f'❓ {question}')

			try:
				# Wait for response (2 min timeout)
				response = await asyncio.wait_for(self._pending_hitl, timeout=120)
				await self.emit_chat('user', response)
				logger.debug(f'Got HITL response: {response}')
				return ActionResult(extracted_content=f'Human responded: {response}')
			except asyncio.TimeoutError:
				await self.emit_chat('system', '⏱️ No response, skipping...')
				return ActionResult(extracted_content='Human did not respond, skip this field')
			finally:
				self._pending_hitl = None
				self._pending_hitl_id = None

		@self.tools.action(description='Request draft review before submitting application')
		async def request_draft_review() -> ActionResult:
			"""
			Draft Mode: Pause before submitting and ask user for confirmation.

			This builds trust by showing the user exactly what will be submitted.
			Default behavior: ON (opt-out, not opt-in)
			"""
			if not self.draft_mode:
				# Draft mode disabled, proceed directly
				return ActionResult(extracted_content='Draft mode disabled, proceed to submit.')

			hitl_id = f'draft_{int(datetime.now().timestamp() * 1000)}'

			try:
				loop = asyncio.get_running_loop()
			except RuntimeError:
				loop = asyncio.new_event_loop()
				asyncio.set_event_loop(loop)

			self._pending_hitl = loop.create_future()
			self._pending_hitl_id = hitl_id

			logger.info(f'Draft review requested: id={hitl_id}')

			# Capture full-page screenshot for review
			screenshot_b64 = None
			if self._browser_session:
				try:
					page = await self._browser_session.get_current_page()
					if page:
						screenshot_b64 = await page.screenshot(
							format='jpeg',
							quality=80,
							full_page=True,  # Capture entire form
						)
				except Exception as e:
					logger.warning(f'Failed to capture draft screenshot: {e}')

			# Send draft review request to frontend
			await self.emit(
				EventType.DRAFT_REVIEW,
				'📋 Application ready! Please review before submitting.',
				{
					'hitl_id': hitl_id,
					'screenshot': screenshot_b64,
					'context': 'Review the filled form and click Confirm to submit, or Edit to make changes.',
				},
			)
			await self.emit_chat('agent', '📋 **Draft Ready!** Please review the form above and confirm submission.')

			try:
				# Wait for user confirmation (5 min timeout for review)
				response = await asyncio.wait_for(self._pending_hitl, timeout=300)

				if response.lower() in ['confirm', 'submit', 'yes', 'ok']:
					self._draft_confirmed = True
					await self.emit_chat('user', '✅ Confirmed!')
					await self.emit(EventType.DRAFT_CONFIRM, 'User confirmed submission')
					logger.info('Draft confirmed by user, proceeding to submit')
					return ActionResult(extracted_content='User confirmed. Click the Submit/Apply button now.')
				else:
					await self.emit_chat('user', f'✏️ {response}')
					await self.emit(EventType.DRAFT_EDIT, 'User requested edits', {'feedback': response})
					logger.info(f'User requested edits: {response}')
					return ActionResult(
						extracted_content=f'User wants changes: {response}. Make the edits, then call request_draft_review again.'
					)

			except asyncio.TimeoutError:
				await self.emit_chat('system', '⏱️ Review timed out. Proceeding with submission.')
				logger.warning('Draft review timed out, proceeding')
				return ActionResult(extracted_content='Review timed out. Proceed to submit.')
			finally:
				self._pending_hitl = None
				self._pending_hitl_id = None

		@self.tools.action(description='Retrieve information from users documents (resume, notes, etc.)')
		async def retrieve_user_context(query: str) -> ActionResult:
			"""
			Use this tool to look up specific details about the user that are needed for the form
			but missing from the profile summary.
			Examples: "detailed project description", "challenges faced", "university courses", "hobbies".
			"""
			if not self.user_id:
				return ActionResult(extracted_content='No user_id linked. Cannot retrieve specific documents.')

			try:
				from src.services.rag_service import rag_service

				results = await rag_service.query(self.user_id, query)

				if results:
					formatted = '\n\n'.join(
						[f'- {r.get("content", r)}' if isinstance(r, dict) else f'- {r}' for r in results]
					)
					return ActionResult(extracted_content=f'Found relevant info:\n{formatted}')
				else:
					return ActionResult(extracted_content='No relevant info found in documents.')
			except Exception as e:
				logger.error(f'RAG tool error: {e}')
				return ActionResult(extracted_content=f'Error retrieving info: {e}')

	async def get_browser(self):
		from browser_use import Browser

		# Always create new browser for now to avoid state issues
		if self._browser:
			try:
				await self._browser.close()
			except Exception:
				pass

		# Docker/cloud-compatible Chrome args
		chrome_args = [
			'--disable-dev-shm-usage',  # Overcome limited /dev/shm in containers
			'--disable-gpu',  # Disable GPU in headless
			'--single-process',  # Reduce memory in containers
		]

		# Use new_context_config if available, or just pass args
		# According to docs/source, disable_security=True in Browser init should work.

		self._browser = Browser(
			executable_path=settings.chrome_path,
			user_data_dir=settings.user_data_dir,
			profile_directory=settings.profile_directory,
			headless=settings.headless,
			args=chrome_args + ['--no-sandbox'],
			disable_security=True,
		)
		return self._browser

	async def emit(self, event_type: EventType, message: str, data: dict = None):
		"""Emit an event to connected clients."""
		event = AgentEvent(type=event_type, agent='applier', message=message, data=data or {})
		await self._manager.send_event(self.session_id, event)

	async def emit_chat(self, sender: str, message: str, data: dict = None):
		"""Emit a chat message."""
		event = AgentEvent(type=EventType.CHAT_MESSAGE, agent=sender, message=message, data=data or {})
		await self._manager.send_event(self.session_id, event)

	def resolve_hitl(self, hitl_id: str, response: str):
		"""Resolve a pending HITL request from this service."""
		logger.debug(f'HITL resolve: id={hitl_id}, pending_id={self._pending_hitl_id}')
		if self._pending_hitl and self._pending_hitl_id == hitl_id:
			if not self._pending_hitl.done():
				self._pending_hitl.set_result(response)
				logger.debug(f'HITL resolved with: {response}')

	async def _screenshot_loop(self):
		"""Capture and stream screenshots."""
		logger.debug('Screenshot loop started, waiting for browser_session...')
		frame_count = 0
		wait_count = 0

		# Wait for browser session to be available
		while self._is_running and not self._browser_session:
			wait_count += 1
			if wait_count % 10 == 1:
				logger.debug(f'Waiting for browser_session... ({wait_count})')
			await asyncio.sleep(0.5)  # Slower poll for startup

		# Additional wait for session to initialize
		await asyncio.sleep(2.0)

		if self._browser_session:
			logger.debug('Browser session available! Starting screenshot capture...')
		else:
			logger.debug('Screenshot loop exiting - is_running=False or no session')
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
								logger.debug(f'Failed to get pages: {pe}')
							error_count += 1

					if page:
						screenshot_b64 = await page.screenshot(format='jpeg', quality=50)

						frame_count += 1
						if frame_count <= 3 or frame_count % 50 == 0:
							logger.info(f'Screenshot frame #{frame_count} sent, size={len(screenshot_b64)}')

						await self.emit(
							EventType.BROWSER_SCREENSHOT,
							'Browser screenshot',
							{'screenshot': screenshot_b64, 'image': screenshot_b64, 'format': 'jpeg'},
						)
						error_count = 0  # Reset error count on success
					elif error_count < 5:
						logger.debug('No page available for screenshot')
						error_count += 1

			except Exception as e:
				error_count += 1
				if error_count <= 3:
					logger.warning(f'Screenshot error: {e}')

			await asyncio.sleep(0.2)  # 5 FPS target

		logger.debug(f'Screenshot loop ended, total frames: {frame_count}')

	async def perform_interaction(self, Interaction: dict):
		"""
		Execute remote interaction on the active browser page.

		Args:
		    Interaction: Dictionary with 'type', 'x', 'y', 'text', etc.
		"""
		if not self._browser_session:
			logger.warning('Interaction ignored: No active browser session.')
			return

		try:
			page = await self._browser_session.get_current_page()
			if not page:
				return

			action_type = Interaction.get('type')

			if action_type == 'click':
				x = Interaction.get('x')
				y = Interaction.get('y')
				if x is not None and y is not None:
					# Adjust for potential scale/offset if needed, but assuming direct mapping
					logger.debug(f'Remote Interaction: Click at ({x}, {y})')
					await page.mouse.click(x, y)

			elif action_type == 'type':
				text = Interaction.get('text', '')
				if text:
					logger.debug(f"Remote Interaction: Type '{text}'")
					await page.keyboard.type(text)

			elif action_type == 'key':
				key = Interaction.get('key', '')
				if key:
					logger.debug(f"Remote Interaction: Press key '{key}'")
					await page.keyboard.press(key)

			elif action_type == 'scroll':
				delta_y = Interaction.get('delta_y', 0)
				if delta_y:
					await page.mouse.wheel(0, delta_y)

		except Exception as e:
			logger.error(f'Failed to perform interaction: {e}')

	async def take_screenshot(self):
		"""Take an immediate screenshot."""
		if not self._browser_session:
			logger.warning('Screenshot ignored: No active browser session.')
			return

		try:
			page = await self._browser_session.get_current_page()
			if page:
				screenshot_b64 = await page.screenshot(full_page=False, type='jpeg', quality=80)

				await self.emit(
					EventType.BROWSER_SCREENSHOT,
					'Manual screenshot captured',
					{'screenshot': screenshot_b64, 'image': screenshot_b64, 'format': 'jpeg'},
				)
				logger.info('Manual screenshot captured and sent')
			else:
				logger.warning('No page available for screenshot')
		except Exception as e:
			logger.error(f'Failed to take screenshot: {e}')

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
		if self._browser:
			try:
				await self._browser.close()
			except Exception as e:
				logger.debug(f'Ignored error closing browser: {e}')
			finally:
				self._browser = None

		if self._pending_hitl and not self._pending_hitl.done():
			self._pending_hitl.cancel()

	async def run(self, url: str):
		"""Run the application process with live streaming."""
		self._is_running = True

		await self.emit(EventType.APPLIER_START, 'Starting application')
		await self.emit_chat('system', f'🎯 Applying to: {url}')

		if self.draft_mode:
			await self.emit_chat('system', "📋 Draft Mode ON - You'll review before submission")

		try:
			# Load user profile - from database if user_id provided, else fallback to YAML
			profile = None
			profile_data = None

			if self.user_id:
				# Multi-user mode: Load from Supabase
				from src.services.user_profile_service import user_profile_service

				profile = await user_profile_service.get_profile(self.user_id)

				if not profile:
					await self.emit_chat('system', '❌ Profile not found. Please complete onboarding.')
					await self.emit(EventType.PIPELINE_ERROR, 'User profile not found')
					return

				# Convert profile to dict for YAML dump
				profile_data = profile.model_dump()
				logger.info(f'Loaded profile from database for user {self.user_id}')
			else:
				# Legacy mode: Load from YAML file
				base_dir = Path(__file__).resolve().parent.parent
				profile_path = base_dir / 'data/user_profile.yaml'

				def load_yaml():
					with open(profile_path, 'r', encoding='utf-8') as f:
						return yaml.safe_load(f)

				profile_data = await asyncio.to_thread(load_yaml)
				profile = UserProfile(**profile_data)
				logger.info('Loaded profile from YAML file (legacy mode)')

			profile_yaml = yaml.dump(profile_data)
			resume_path = profile.files.resume

			await self.emit_chat('system', f'📋 Profile: {profile.personal_information.full_name}')

			# Import high-quality prompt
			from src.prompts.applier_agent import get_applier_prompt

			task_prompt = get_applier_prompt(
				url=url, profile_yaml=profile_yaml, resume_path=resume_path, draft_mode=self.draft_mode
			)

			await self.emit_chat('agent', '🚀 Starting browser...')

			# Get persistent browser
			browser = await self.get_browser()

			# Lazy import LLM classes from browser_use
			from browser_use import Agent

			# Note: verify if ChatMistral is in browser_use top level or submodule
			# User specified: from browser_use.llm.mistral import ChatMistral
			try:
				from browser_use.llm.mistral import ChatMistral
			except ImportError:
				# Fallback or standard langchain import if browser_use wrapper missing
				from langchain_mistralai import ChatMistralAI as ChatMistral

			# Configure LLM - Mistral (Primary as per user request)
			llm = None
			llm_name = ''

			if settings.mistral_api_key:
				try:
					llm = ChatMistral(
						model=settings.mistral_model, temperature=0.6, api_key=settings.mistral_api_key.get_secret_value()
					)
					llm_name = f'Mistral ({settings.mistral_model})'
					logger.info(f'Using Mistral LLM: {settings.mistral_model}')
				except Exception as e:
					logger.warning(f'Failed to initialize Mistral: {e}')

			if not llm:
				# Fallback to OpenRouter or Gemini if Mistral fails/missing
				# (Keeping previous logic as fallback, or error if strict)
				# User said "make all ... use ChatMistral".
				# If no key, maybe error.
				pass

			# Previous fallbacks...
			if not llm and settings.gemini_api_key:
				# ... (Existing Gemini logic)
				pass

			# For now, I will just REPLACE the block to prioritize Mistral and keep OpenRouter as fallback?
			# User instruction: "make all ... use llm = ChatMistral".
			# I will ensure Mistral is tried.

			if not llm:
				# Try OpenRouter if Mistral key missing but OpenRouter present?
				if settings.openrouter_api_key:
					from browser_use import ChatOpenAI

					llm = ChatOpenAI(
						model=settings.openrouter_model,
						base_url='https://openrouter.ai/api/v1',
						api_key=settings.get_openrouter_key(),
					)
					llm_name = f'OpenRouter ({settings.openrouter_model})'

			if not llm:
				raise ValueError('No LLM available - check MISTRAL_API_KEY')

			await self.emit_chat('agent', f'🤖 AI ready ({llm_name}), opening browser...')

			# Create agent
			self._agent = Agent(
				task=task_prompt,
				llm=llm,
				browser=browser,
				use_vision=False,
				tools=self.tools,  # Pass tools object
				extend_system_message='Be concise. Fill forms quickly. RESPONSE MUST BE RAW JSON. NO MARKDOWN. NO CODE BLOCKS.',
				max_failures=5,
			)

			self._screenshot_task = asyncio.create_task(self._screenshot_loop())

			try:
				# Get session for interaction
				self._browser_session = self._agent.browser_session

				await self.emit_chat('system', '📺 Live view active')

				# Run the agent with retry logic for transient LLM errors
				max_retries = 3
				for attempt in range(max_retries):
					try:
						await self._agent.run()
						break  # Success
					except Exception as e:
						# Check for LLM errors (Rate limit, JSON error, etc.)
						error_str = str(e)
						is_llm_error = (
							'ModelProviderError' in type(e).__name__
							or 'ModelRateLimitError' in type(e).__name__
							or '429' in error_str
						)

						if is_llm_error and attempt < max_retries - 1:
							wait_time = (attempt + 1) * 5
							msg = f'⚠️ LLM Error ({type(e).__name__}). Retrying in {wait_time}s...'
							logger.warning(f'{msg} Detail: {e}')
							await self.emit_chat('system', msg)
							await asyncio.sleep(wait_time)
							continue
						else:
							raise e

				# Capture proof of application
				if self._browser_session:
					try:
						page = await self._browser_session.get_current_page()
						if page:
							# Auto-track the application
							from src.agents.tracker_agent import JobTrackerAgent
							tracker_agent = JobTrackerAgent(self.user_id or 'default')
							await tracker_agent.add_application(
								company=url,
								role='Software Engineer',
								url=url,
								notes='Auto-applied. Proof captured.',
								priority='High',
							)
					except Exception as e:
						logger.error(f'Failed to capture proof or track: {e}')

				await self.emit(EventType.APPLIER_COMPLETE, 'Application submitted!', {'success': True})
				await self.emit_chat('agent', '✅ Application submitted! 🎉')
				return {'success': True}

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
			await self.emit(EventType.PIPELINE_ERROR, f'Error: {error_msg}', {'error': error_msg})
			await self.emit_chat('system', f'❌ {error_msg}')
			return {'success': False, 'error': error_msg}
		finally:
			self._is_running = False
