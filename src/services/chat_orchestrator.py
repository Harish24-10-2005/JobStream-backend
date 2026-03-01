"""
Chat Orchestrator
Parses natural language user input and directs the "Canvas" interface.
"""

import json
from typing import Any, Dict

from pydantic import BaseModel, Field

from src.core.llm_provider import get_llm


class Intent(BaseModel):
	action: str = Field(..., description="The action to take: 'SEARCH', 'APPLY', 'RESEARCH', 'TRACK', 'CHAT'")
	parameters: Dict[str, Any] = Field(default_factory=dict, description='Parameters extracted from the prompt')
	response_text: str = Field(..., description='A short response to show the user in the chat bubble')


class ChatOrchestrator:
	"""
	The 'Brain' that decides which tool/canvas to open based on user input.
	"""

	def __init__(self):
		# We use a smart model for intent classification
		self.llm = get_llm(temperature=0)

	async def determine_intent(self, user_message: str, user_id: str = None) -> Intent:
		"""
		Analyze user message and return structured intent.
		"""
		system_prompt = """
        You are the Orchestrator for 'JobAI', a career automation platform.
        Your goal is to classify the user's intent and extract parameters to control the UI 'Canvas'.
        
        AVAILABLE ACTIONS:
        1. SEARCH: User wants to find jobs. 
           - Params: query (str), location (str)
           - Trigger words: "find jobs", "search for", "looking for roles"
        
        2. APPLY: User wants to apply to a specific URL.
           - Params: url (str)
           - Trigger words: "apply to this", "apply here", "http..."
        
        3. RESEARCH: User wants to analyze a company.
           - Params: company (str)
           - Trigger words: "research [Company]", "tell me about [Company]", "check [Company]"
        
        4. TRACK: User wants to see their application status/tracker.
           - Params: status (optional str filter)
           - Trigger words: "show my applications", "check tracker", "status of my jobs"
        
        5. CHAT: General conversation or questions not fitting above.
           - Params: none
        
        OUTPUT FORMAT:
        Return a JSON object matching the Intent schema.
        {
            "action": "SEARCH",
            "parameters": {"query": "React Developer", "location": "Remote"},
            "response_text": "I'll start searching for React Developer roles (Remote)..."
        }
        """

		try:
			# We construct a structured prompt for the LLM
			# Since we can't use .with_structured_output on all providers easily in this mixed env,
			# we'll use JSON mode or prompt engineering.

			messages = [
				{'role': 'system', 'content': system_prompt},
				{'role': 'user', 'content': user_message},
			]

			response_text = await self.llm.ainvoke(messages, agent_name='chat_orchestrator')
			content = response_text.strip()

			# Clean up potential markdown code blocks
			if '```json' in content:
				content = content.split('```json')[1].split('```')[0].strip()
			elif '```' in content:
				content = content.split('```')[1].split('```')[0].strip()

			data = json.loads(content)
			return Intent(**data)

		except Exception as e:
			# Fallback to simple CHAT
			return Intent(
				action='CHAT',
				parameters={},
				response_text="I'm not sure how to handle that command visually, but I can answer questions! What do you need help with?",
			)


# Singleton
chat_orchestrator = ChatOrchestrator()
