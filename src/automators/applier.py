import yaml

from src.automators.base import BaseAgent
from src.core.console import console
from src.models.profile import UserProfile

# Lazy imports - browser_use and langchain are heavy, only import when needed
_controller = None


def _get_controller():
	"""Lazy initialization of Controller with ask_human action."""
	global _controller
	if _controller is None:
		from browser_use import Controller

		_controller = Controller()

		@_controller.action(description='Ask human for help with a question')
		def ask_human(question: str) -> str:
			console.applier_human_input(question)
			# Future enhancement: route through WebSocket for web UI
			# await websocket_manager.send_personal_message(question, client_id)
			answer = input('\n  ❓ Your answer > ')
			console.applier_status('Received human input', 'Response recorded')
			return f'The human responded with: {answer}'

		@_controller.action(
			description='Pause execution to allow human to solve CAPTCHA, Cloudflare, or similar anti-bot challenge'
		)
		def solve_captcha(challenge_type: str = 'CAPTCHA') -> str:
			console.applier_human_input(f'ACTION REQUIRED: Please solve the {challenge_type} in the browser window.')
			# Production environment hook for WebSocket UI:
			# await websocket_manager.broadcast({"type": "CAPTCHA_REQUIRED", "challenge": challenge_type})
			# await wait_for_human_signal()
			input(f'\n  🚨 Press ENTER when you have solved the {challenge_type} > ')
			console.applier_status('Resuming', 'Human indicated challenge is solved')
			return 'Challenge has been solved by human. Please proceed with the task.'

	return _controller


class ApplierAgent(BaseAgent):
	"""
	Agent responsible for applying to jobs using Browser automation.
	"""

	def __init__(self):
		super().__init__()
		self.browser = None

	def check_profile_completeness(self, profile: UserProfile) -> list:
		missing = []
		if not profile.personal_information or not profile.personal_information.first_name:
			missing.append('First Name')
		if not profile.personal_information or not profile.personal_information.last_name:
			missing.append('Last Name')
		if not profile.personal_information or not profile.personal_information.email:
			missing.append('Email')
		if not profile.files or not profile.files.resume:
			missing.append('Resume File')
		if not profile.experience:
			missing.append('Experience History')
		return missing

	async def run(self, url: str, profile: UserProfile) -> str:
		"""
		Executes the application process.
		"""
		# Rich console output
		console.applier_header(url)
		self.logger.info(f'🚀 ApplierAgent: Starting application for {url}')

		# 0. Pre-flight check
		missing_fields = self.check_profile_completeness(profile)
		if missing_fields:
			msg = f'Profile incomplete! Missing required fields: {", ".join(missing_fields)}'
			console.error(msg)
			self.logger.error(f'Applier Pre-flight failed: {msg}')
			return f'Error: {msg}'

		# 1. Prepare Data
		profile_dict = profile.model_dump()
		profile_yaml = yaml.dump(profile_dict)
		resume_path = profile.files.resume

		console.applier_status('Preparing application', 'Loading profile and resume')

		# 2. Optimized Prompt
		task_prompt = f"""
GOAL: Navigate to {url} and apply for the job using my profile data.

--- 
👤 CANDIDATE PROFILE (Strictly use this):
{profile_yaml}
---

📋 EXECUTION STEPS:
1. **Navigation:** Go to the URL. If redirected to login, use 'ask_human' immediately.
2. **Anti-Bot Check:** If you encounter a CAPTCHA, Cloudflare check, or 'Verify you are human' page, IMMEDIATELY use the 'solve_captcha' action and wait.
3. **Form Filling:** - Scan page for inputs. Map 'First Name', 'Last Name', 'Email', 'Phone' from PROFILE.
   - LinkedIn/GitHub: Use URLs from profile.
   - Experience: Calculate based on 'experience' section dates.
   - Sponsorship: Select "No" / "Authorized to work".
3. **Smart Answers:** - For open questions like "Why this job?", generate a concise 2-sentence answer.
4. **File Upload:** - Upload resume from: "{resume_path}"
   - Click input element directly (do not drag-and-drop).
5. **Final Review:** Click 'Submit' or 'Apply'.

⚠️ CRITICAL RULES:
- If a field requires missing data (e.g., "SSN"), use 'ask_human'.
- Prioritize "Easy Apply" if available.
"""

		console.applier_status('Initializing browser', 'Chrome automation starting...')

		# Lazy import heavy browser_use modules (includes LLM wrappers)
		from browser_use import Agent, Browser, ChatGoogle, ChatOpenAI

		# Initialize Browser
		browser = Browser(
			executable_path=self.settings.chrome_path,
			user_data_dir=self.settings.user_data_dir,
			profile_directory=self.settings.profile_directory,
			headless=self.settings.headless,
		)

		console.applier_status('Configuring AI models', 'Primary: Gemini 2.0 | Fallback: Qwen')

		# --- LLM CONFIGURATION START ---

		# 1. Primary Model: Google Gemini 2.0 Flash (Fast + Vision)
		# We access the secret string using .get_secret_value()
		gemini_key = self.settings.gemini_api_key.get_secret_value() if self.settings.gemini_api_key else ''

		fallback_llm = ChatGoogle(
			model='gemini-2.0-flash-exp',  # or 'gemini-2.0-flash'
			api_key=gemini_key,
		)

		# 2. Fallback Model: OpenRouter Qwen (Free) or Groq
		# This only runs if Gemini fails.
		llm = ChatOpenAI(
			model=self.settings.openrouter_model,
			base_url='https://openrouter.ai/api/v1',
			api_key=self.settings.get_openrouter_key(),
		)

		# Alternative Fallback (if you prefer Groq for speed):
		# fallback_llm = ChatGroq(
		#     model='llama-3.3-70b-versatile',
		#     api_key=self.settings.groq_api_key.get_secret_value()
		# )

		# --- LLM CONFIGURATION END ---

		SPEED_OPTIMIZATION_PROMPT = """
Speed optimization instructions:
- Be extremely concise.
- Use multi-action sequences (e.g., fill multiple fields in one go).
- Do not scroll unless necessary.
"""

		try:
			agent = Agent(
				task=task_prompt,
				llm=llm,
				browser=browser,
				use_vision=True,  # ENABLED: Crucial for accurate form detection
				controller=_get_controller(),
				fallback_llm=fallback_llm,
				extend_system_message=SPEED_OPTIMIZATION_PROMPT,
			)

			console.applier_status('Running browser agent', 'Navigating and filling forms...')
			await agent.run()

			console.applier_complete(True)
			return 'Application process finished.'

		except Exception as e:
			self.logger.error(f'Application error: {e}')
			console.applier_complete(False, str(e))
			raise
