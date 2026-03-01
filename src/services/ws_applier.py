"""
WebSocket-Enabled ApplierAgent
Wraps the ApplierAgent with event streaming and WebSocket HITL
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import yaml

from src.api.websocket import AgentEvent, EventType, manager

logger = logging.getLogger(__name__)


class WebSocketApplierAgent:
	"""
	ApplierAgent wrapper that streams browser actions to WebSocket clients.
	Replaces blocking input() with WebSocket-based HITL.
	"""

	def __init__(self, session_id: str = 'default'):
		self.session_id = session_id
		self._manager = manager
		self._screenshot_interval = 1.0  # seconds between screenshots

	async def emit(self, event_type: EventType, message: str, data: dict = None):
		"""Emit an event to connected clients."""
		event = AgentEvent(type=event_type, agent='applier', message=message, data=data or {})
		await self._manager.send_event(self.session_id, event)

	async def ask_human_ws(self, question: str, context: str = '') -> str:
		"""
		Request human input via WebSocket instead of stdin.
		This is the WebSocket replacement for the blocking input() call.
		"""
		return await self._manager.request_hitl(self.session_id, question, context)

	async def run(self, url: str, profile_data: dict, resume_path: Optional[str] = None) -> dict:
		"""
		Run the application process with real-time event streaming.

		Args:
		    url: Job application URL
		    profile_data: User profile dictionary
		    resume_path: Optional path to a specific (tailored) resume file

		Returns:
		    Result dictionary with success status
		"""
		await self.emit(EventType.APPLIER_START, 'Starting application for job')
		await self.emit(EventType.APPLIER_NAVIGATE, f'Navigating to {url[:60]}...')

		try:
			# Import browser-use components (includes LLM wrappers)
			from browser_use import Agent, Browser, ChatGroq, ChatOpenAI, Controller
			from browser_use.agent.views import ActionResult

			from src.core.config import settings
			from src.models.profile import UserProfile

			profile = UserProfile(**profile_data)
			profile_yaml = yaml.dump(profile_data)

			# Use provided resume path or fall back to profile default
			final_resume_path = resume_path if resume_path else profile.files.resume

			# Create custom controller with WebSocket HITL
			controller = Controller()

			# Store reference to self for the closure
			ws_agent = self

			@controller.action(description='Ask human for help with a question')
			async def ask_human(question: str) -> ActionResult:
				"""WebSocket-based human input request."""
				await ws_agent.emit(
					EventType.HITL_REQUEST,
					question,
					{'hitl_id': f'hitl_{datetime.now().timestamp()}', 'context': 'Form requires additional input'},
				)

				try:
					# Wait for response via WebSocket
					response = await ws_agent.ask_human_ws(question)
					return ActionResult(extracted_content=f'The human responded with: {response}')
				except asyncio.TimeoutError:
					return ActionResult(extracted_content='Human did not respond in time, skipping this field')

			# Task prompt
			task_prompt = f"""
GOAL: Navigate to {url} and apply for the job using my profile data.

--- 
👤 CANDIDATE PROFILE (Use this data STRICTLY):
{profile_yaml}
---

📋 EXECUTION STEPS:
1. **Navigation:** Go to the URL. If redirected to a login page, use the 'ask_human' tool immediately.
2. **Form Filling:** 
   - Scan the page for input fields.
   - Map 'First Name', 'Last Name', 'Email', 'Phone' from the PROFILE above.
   - If asked for "LinkedIn" or "GitHub", use the URLs in the profile.
   - If asked for "Experience", calculate based on the 'experience' section.
   - If asked for "Sponsorship" or "Visa", select "No" / "Authorized to work".
3. **Smart Answers:** 
   - If there is an open-ended question like "Why do you want this job?", generate a 2-sentence answer.
4. **File Upload:** 
   - If a Resume upload button appears, upload: "{final_resume_path}"
   - DO NOT try to drag-and-drop. Click the input element and send the file path.
5. **Final Review:**
   - Check if all required fields are filled.
   - Click 'Submit' or 'Apply'.

⚠️ CRITICAL RULES:
- DO NOT invent information. If a field requires data not in the profile (like "SSN"), use 'ask_human'.
- If the page allows "Easy Apply" via LinkedIn, try that first if possible, otherwise use the manual form.
"""

			await self.emit(EventType.APPLIER_NAVIGATE, 'Initializing browser...')

			# Docker/cloud-compatible Chrome args
			chrome_args = [
				'--disable-dev-shm-usage',
				'--disable-gpu',
				'--single-process',
			]

			# Initialize Browser
			browser = Browser(
				executable_path=settings.chrome_path,
				user_data_dir=settings.user_data_dir,
				profile_directory=settings.profile_directory,
				headless=settings.headless,
				chromium_sandbox=False,
				args=chrome_args,
				disable_security=True,  # Allow all URLs
			)

			# Configure LLMs
			llm = ChatOpenAI(
				model=settings.openrouter_model, base_url='https://openrouter.ai/api/v1', api_key=settings.get_openrouter_key()
			)
			fallback_llm = ChatGroq(model='llama-3.3-70b-versatile')

			# Create agent with action hooks for event streaming
			agent = Agent(
				task=task_prompt,
				llm=llm,
				browser=browser,
				use_vision=False,
				controller=controller,
				fallback_llm=fallback_llm,
				extend_system_message='Be extremely concise. Get to the goal quickly.',
			)

			# Add hooks to stream actions
			original_execute = agent.execute_action if hasattr(agent, 'execute_action') else None

			async def execute_with_streaming(action):
				"""Wrapper that emits events for each action."""
				action_type = getattr(action, 'type', 'unknown')
				action_data = getattr(action, 'data', {})

				# Emit action event
				if 'click' in str(action_type).lower():
					await self.emit(EventType.APPLIER_CLICK, 'Clicking element')
				elif 'type' in str(action_type).lower() or 'input' in str(action_type).lower():
					await self.emit(EventType.APPLIER_TYPE, 'Typing text')
				elif 'navigate' in str(action_type).lower() or 'goto' in str(action_type).lower():
					await self.emit(EventType.APPLIER_NAVIGATE, 'Navigating')
				elif 'upload' in str(action_type).lower():
					await self.emit(EventType.APPLIER_UPLOAD, 'Uploading file')

				# Take screenshot and send to frontend
				try:
					if hasattr(browser, 'page') and browser.page:
						# browser-use page.screenshot returns base64 string directly
						screenshot_b64 = await browser.page.screenshot(format='jpeg', quality=50)
						await self.emit(
							EventType.BROWSER_SCREENSHOT,
							'Browser screenshot',
							{'screenshot': screenshot_b64, 'image': screenshot_b64, 'format': 'jpeg'},
						)
				except Exception as e:
					logger.debug(f'Screenshot failed: {e}')  # Log for debugging

				# Execute the original action
				if original_execute:
					return await original_execute(action)

			# Run the agent
			await self.emit(EventType.APPLIER_NAVIGATE, 'Running browser automation...')

			try:
				await agent.run()
				await self.emit(EventType.APPLIER_COMPLETE, 'Application submitted successfully!', {'success': True})
				return {'success': True, 'message': 'Application submitted'}
			finally:
				# Cleanup browser
				try:
					await browser.close()
				except Exception:
					pass

		except Exception as e:
			error_msg = str(e)
			await self.emit(EventType.PIPELINE_ERROR, f'Application failed: {error_msg}', {'error': error_msg})
			return {'success': False, 'error': error_msg}
