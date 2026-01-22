import yaml
from src.automators.base import BaseAgent
from src.models.profile import UserProfile
from src.core.console import console

# Import browser_use at module level like the working example
from browser_use import Tools, Agent, ChatOpenAI, ActionResult, Browser, ChatGroq ,ChatGoogle

# Initialize Tools at module level (like working example)
tools = Tools()

@tools.action(description='Ask human for help with a question')
def ask_human(question: str) -> ActionResult:
    console.applier_human_input(question)
    answer = input(f'\n  ❓ Your answer > ')
    console.applier_status("Received human input", "Response recorded")
    return f'The human responded with: {answer}'


class ApplierAgent(BaseAgent):
    """
    Agent responsible for applying to jobs using Browser automation.
    """
    def __init__(self):
        super().__init__()
        self.browser = None

    async def run(self, url: str, profile: UserProfile) -> str:
        """
        Executes the application process.
        """
        # Rich console output
        console.applier_header(url)
        self.logger.info(f"🚀 ApplierAgent: Starting application for {url}")
        
        # 1. Prepare Data
        profile_dict = profile.model_dump()
        profile_yaml = yaml.dump(profile_dict)
        resume_path = profile.files.resume
        
        console.applier_status("Preparing application", "Loading profile and resume")
        
        # 2. Optimized Prompt
        task_prompt = f"""
GOAL: Navigate to {url} and apply for the job using my profile data.

--- 
👤 CANDIDATE PROFILE (Strictly use this):
{profile_yaml}
---

📋 EXECUTION STEPS:
1. **Navigation:** Go to the URL. If redirected to login, use 'ask_human' immediately.
2. **Form Filling:** - Scan page for inputs. Map 'First Name', 'Last Name', 'Email', 'Phone' from PROFILE.
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

        console.applier_status("Initializing browser", "Chrome automation starting...")
        
        # Initialize Browser
        browser = Browser(
            executable_path=self.settings.chrome_path,
            user_data_dir=self.settings.user_data_dir,
            profile_directory=self.settings.profile_directory,
            headless=self.settings.headless
        )
        
        console.applier_status("Configuring AI models", "Primary: Gemini 2.0 | Fallback: Qwen")
        
        # --- LLM CONFIGURATION START ---
        
        # 1. Primary Model: Google Gemini 2.0 Flash (Fast + Vision)
        # We access the secret string using .get_secret_value()
        gemini_key = self.settings.gemini_api_key.get_secret_value() if self.settings.gemini_api_key else ""
        
        fallback_llm = ChatGoogle(
            model='gemini-2.0-flash-exp', # or 'gemini-2.0-flash'
            api_key=gemini_key
        )

        # 2. Fallback Model: OpenRouter Qwen (Free) or Groq
        # This only runs if Gemini fails.
        llm = ChatOpenAI(
            model='qwen/qwen3-next-80b-a3b-instruct:free',
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
                tools=tools,
                fallback_llm=fallback_llm,
                extend_system_message=SPEED_OPTIMIZATION_PROMPT,
            )
            
            console.applier_status("Running browser agent", "Navigating and filling forms...")
            await agent.run()
            
            console.applier_complete(True)
            return "Application process finished."
            
        except Exception as e:
            self.logger.error(f"Application error: {e}")
            console.applier_complete(False, str(e))
            raise