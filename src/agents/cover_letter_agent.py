"""
Cover Letter Agent - Deep Agent with LangGraph for personalized cover letters
Uses planning, multi-step generation, and Human-in-the-Loop verification
"""

from typing import Any, Callable, Dict, Literal, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.automators.base import BaseAgent
from src.core.agent_memory import agent_memory
from src.core.circuit_breaker import CircuitBreaker
from src.core.console import console
from src.core.guardrails import create_input_pipeline
from src.core.llm_provider import get_llm
from src.core.structured_logger import slog
from src.core.types import AgentResponse
from src.models.job import JobAnalysis
from src.models.profile import UserProfile
from src.services.rag_service import rag_service
from src.services.resume_storage_service import resume_storage_service

# ============================================
# Circuit Breakers & Guardrails
# ============================================
cb_groq = CircuitBreaker('groq', failure_threshold=5, retry_count=2)
input_guard = create_input_pipeline('medium')


# ============================================
# State Definition for LangGraph
# ============================================
class CoverLetterState(TypedDict):
	"""State for the Cover Letter Deep Agent workflow."""

	# Input
	job_analysis: Dict
	user_profile: Dict
	tone: str
	hitl_handler: Optional[Callable[[str, str], Any]]  # Added HITL Handler
	user_id: Optional[str]

	# Planning
	plan: list
	current_step: int

	# Processing
	company_research: Dict
	content: Dict
	full_text: str

	# Human-in-the-loop
	needs_human_review: bool
	human_approved: bool
	human_feedback: str

	# Output
	result: Dict
	error: str


class CoverLetterAgent(BaseAgent):
	"""
	LangGraph Deep Agent for personalized cover letter generation.

	Features:
	- Multi-step planning
	- Company culture matching
	- Tone customization
	- Human-in-the-Loop verification
	- Groq LLM (free tier)
	"""

	TONES = {
		'professional': 'Write in a professional, confident tone. Be direct and focused.',
		'enthusiastic': 'Write with enthusiasm and energy. Show genuine excitement.',
		'formal': 'Write in a formal, traditional business letter style.',
		'casual': 'Write in a friendly, approachable tone while remaining professional.',
	}

	def __init__(self):
		super().__init__()
		self.llm = get_llm(temperature=0.6)
		self.memory = MemorySaver()
		self.graph = self._build_graph()

	def _build_graph(self) -> StateGraph:
		"""Build the LangGraph workflow."""

		workflow = StateGraph(CoverLetterState)

		# Add nodes
		workflow.add_node('plan', self._plan_node)
		workflow.add_node('research_company', self._research_company_node)
		workflow.add_node('generate_content', self._generate_content_node)
		workflow.add_node('format_letter', self._format_letter_node)
		workflow.add_node('human_review', self._human_review_node)
		workflow.add_node('finalize', self._finalize_node)

		# Define edges
		workflow.set_entry_point('plan')
		workflow.add_edge('plan', 'research_company')
		workflow.add_edge('research_company', 'generate_content')
		workflow.add_edge('generate_content', 'format_letter')
		workflow.add_edge('format_letter', 'human_review')

		# Conditional edge after human review
		workflow.add_conditional_edges(
			'human_review', self._should_continue, {'approved': 'finalize', 'revise': 'generate_content', 'end': END}
		)
		workflow.add_edge('finalize', END)

		return workflow.compile(checkpointer=self.memory)

	# ============================================
	# Graph Nodes
	# ============================================

	async def _plan_node(self, state: CoverLetterState) -> CoverLetterState:
		"""Planning node."""
		console.subheader('✉️ Cover Letter Deep Agent')
		console.step(1, 5, 'Planning cover letter generation')
		slog.agent('cover_letter_agent', 'plan_node', tone=state.get('tone', 'professional'))

		tone = state.get('tone', 'professional')

		plan = [
			'1. Research company culture',
			f'2. Generate {tone} content',
			'3. Format letter structure',
			'4. Human verification',
			'5. Finalize document',
		]

		console.info(f'Generating {tone} cover letter...')

		return {**state, 'plan': plan, 'current_step': 0}

	async def _research_company_node(self, state: CoverLetterState) -> CoverLetterState:
		"""Research company to personalize letter."""
		console.step(2, 5, 'Analyzing company context')
		slog.agent('cover_letter_agent', 'research_company_node', company=state['job_analysis'].get('company', 'unknown'))

		job = state['job_analysis']
		company = job.get('company', 'the company')

		# Use LLM to infer company characteristics
		prompt = f"""
        Based on this job posting, infer the company culture:
        
        Company: {company}
        Role: {job.get('role', '')}
        Tech Stack: {', '.join(job.get('tech_stack', []))}
        
        Return JSON:
        {{
            "culture_type": "startup/corporate/tech-forward/traditional",
            "values": ["likely company values"],
            "communication_style": "formal/casual/technical",
            "unique_aspects": ["what makes them stand out"]
        }}
        
        Output ONLY valid JSON.
        """

		try:
			research = await self.llm.agenerate_json(
				prompt=prompt, system_prompt='You analyze company culture from job postings.', agent_name='cover_letter_agent'
			)

			if 'error' in research:
				raise Exception(research['error'])

			slog.agent('cover_letter_agent', 'research_complete', culture_type=research.get('culture_type', 'unknown'))

			return {**state, 'company_research': research, 'current_step': 1}

		except Exception as e:
			slog.agent_error('cover_letter_agent', 'research_failed', error=str(e))
			return {**state, 'company_research': {}, 'current_step': 1}

	async def _generate_content_node(self, state: CoverLetterState) -> CoverLetterState:
		"""Generate cover letter paragraphs."""
		console.step(3, 5, 'Generating personalized content')
		slog.agent('cover_letter_agent', 'generate_content_node', tone=state.get('tone', 'professional'))

		job = state['job_analysis']
		profile = state['user_profile']
		research = state.get('company_research', {})
		tone = state.get('tone', 'professional')
		feedback = state.get('human_feedback', '')

		personal = profile.get('personal_information') or {}
		experience = profile.get('experience', [])
		skills = profile.get('skills', {})

		recent_exp = experience[0] if experience else {}
		tone_instruction = self.TONES.get(tone, self.TONES['professional'])

		feedback_instruction = ''
		if feedback:
			feedback_instruction = f'\n\nADDRESS THIS FEEDBACK:\n{feedback}\n'

		# RAG Lookups for relevant stories
		rag_context = ''
		if profile.get('id'):
			try:
				query = f'Stories/achievements related to {", ".join(job.get("tech_stack", [])[:3])}'
				rag_results = await rag_service.query(profile['id'], query, limit=2)
				if rag_results:
					rag_context = '\nRELEVANT STORIES:\n' + '\n'.join([f'- {r["content"]}' for r in rag_results])
			except Exception:
				pass

		# Agent Memory Learnings
		learnings_prompt = ''
		user_id = state.get('user_id')
		if user_id:
			learnings = await agent_memory.get_learnings('cover_letter_agent', user_id)
			if learnings:
				bullets = '\n'.join(f'- {learning}' for learning in learnings)
				learnings_prompt = f'\n\n## Personal Learnings & Preferences\nKeep these in mind:\n{bullets}\n'
				console.info(f'Injected {len(learnings)} personal learnings into context')

		# Stylistic Mimicry / Writing Samples
		writing_samples_prompt = ''
		writing_samples = profile.get('writing_samples', [])
		if writing_samples:
			samples_text = '\n'.join(f'- {s}' for s in writing_samples)
			writing_samples_prompt = f'\n\n## Stylistic Mimicry\nMatch the tone, sentence structure, and vocabulary of these writing samples from the user:\n{samples_text}\n'

		prompt = f"""
        Write a compelling cover letter for this job.
        
        JOB:
        - Position: {job.get('role', '')}
        - Company: {job.get('company', '')}
        - Tech Stack: {', '.join(job.get('tech_stack', []))}
        
        COMPANY CULTURE:
        - Type: {research.get('culture_type', 'professional')}
        - Values: {', '.join(research.get('values', []))}
        
        CANDIDATE:
        - Name: {personal.get('full_name', '')}
        - Current Role: {recent_exp.get('title', '')}
        - Key Skills: {', '.join(list(skills.get('technical', skills.get('primary', [])))[:5])}
        
        {rag_context}
        {learnings_prompt}
        
        MATCHING SKILLS: {', '.join(job.get('matching_skills', []))}
        
        TONE: {tone_instruction}
        {feedback_instruction}
        {writing_samples_prompt}
        
        BANNED WORDS / CLICHES: Do NOT use any of these overused words: "delve", "testament", "tapestry", "fast-paced", "dynamic landscape", "look no further", "navigating", "realm".
        
        Generate a cover letter with:
        1. Opening: Hook + genuine interest in THIS specific company/role
        2. Body: 2-3 specific achievements that match job requirements
        3. Closing: Enthusiasm + clear call to action
        
        Return JSON:
        {{
            "greeting": "Dear Hiring Manager," or personalized,
            "opening": "Opening paragraph (2-3 compelling sentences)...",
            "body": "Body paragraph (3-4 sentences with specific examples)...",
            "closing": "Closing paragraph (2 sentences with call to action)...",
            "signature": "Sincerely,\\n\\n[Name]"
        }}
        
        Output ONLY valid JSON.
        """

		try:
			parsed = await self.llm.agenerate_json(
				prompt=prompt,
				system_prompt='You write personalized cover letters. Be authentic and compelling.',
				agent_name='cover_letter_agent',
			)

			if 'error' in parsed:
				raise Exception(parsed['error'])

			# Ensure name in signature
			name = personal.get('full_name', '')
			if name and '[Name]' in parsed.get('signature', ''):
				parsed['signature'] = parsed['signature'].replace('[Name]', name)

			slog.agent('cover_letter_agent', 'content_generated', word_count=len(str(parsed).split()))

			return {**state, 'content': parsed, 'current_step': 2}

		except Exception as e:
			slog.agent_error('cover_letter_agent', 'content_generation_failed', error=str(e))
			name = personal.get('full_name', 'Candidate')
			return {
				**state,
				'content': {
					'greeting': 'Dear Hiring Manager,',
					'opening': f'I am writing to express my interest in the {job.get("role", "position")} at {job.get("company", "your company")}.',
					'body': 'With my relevant experience and skills, I am confident I can contribute to your team.',
					'closing': 'I would welcome the opportunity to discuss how my background aligns with your needs.',
					'signature': f'Sincerely,\n\n{name}',
				},
				'error': str(e),
				'current_step': 2,
			}

	async def _format_letter_node(self, state: CoverLetterState) -> CoverLetterState:
		"""Format content into full letter."""
		console.step(4, 5, 'Formatting document')

		content = state.get('content', {})
		profile = state.get('user_profile', {})
		personal = profile.get('personal_information') or {}

		# Build header
		header_parts = []
		if personal.get('full_name'):
			header_parts.append(personal['full_name'])
		if personal.get('email'):
			header_parts.append(personal['email'])
		if personal.get('phone'):
			header_parts.append(personal['phone'])

		header = ' | '.join(header_parts)

		# Build full letter
		letter_parts = [
			header,
			'',
			content.get('greeting', 'Dear Hiring Manager,'),
			'',
			content.get('opening', ''),
			'',
			content.get('body', ''),
			'',
			content.get('closing', ''),
			'',
			content.get('signature', 'Sincerely,'),
		]

		full_text = '\n'.join(letter_parts)

		return {**state, 'full_text': full_text, 'current_step': 3, 'needs_human_review': True}

	async def _human_review_node(self, state: CoverLetterState) -> CoverLetterState:
		"""Human-in-the-Loop verification."""
		console.step(5, 5, 'Human Review Required')

		full_text = state.get('full_text', '')
		job = state.get('job_analysis', {})
		hitl_handler = state.get('hitl_handler')

		console.divider()
		console.header('📋 COVER LETTER REVIEW')

		context = f"""
Target: {job.get('role', 'Position')} at {job.get('company', 'Company')}

{full_text}
        """

		console.box('Review Context', context)

		word_count = len(full_text.split())
		console.info(f'Word count: {word_count}')

		question = 'Do you approve this cover letter? (y/n/e)'

		if hitl_handler:
			console.info('Waiting for remote human approval via WebSocket...')
			response = await hitl_handler(question, context)
			choice = response.strip().lower()

			if choice in ['y', 'yes', 'approve']:
				console.success('Cover letter approved via WebSocket!')
				return {**state, 'human_approved': True, 'human_feedback': ''}
			elif choice.startswith('e') or choice.startswith('edit'):
				parts = choice.split(':', 1)
				feedback = parts[1].strip() if len(parts) > 1 else 'Please revise.'
				console.info(f'Feedback received: {feedback}')
				return {**state, 'human_approved': False, 'human_feedback': feedback}
			else:
				return {**state, 'human_approved': False, 'human_feedback': 'Please revise the content'}

		# CLI Fallback
		console.applier_human_input(question)
		print('\n  Options:')
		print('    [y] Approve and continue')
		print('    [n] Reject and revise')
		print('    [e] Edit with feedback')
		print('    [q] Quit/Cancel')

		choice = input('\n  Your choice > ').strip().lower()

		if choice == 'y':
			console.success('Cover letter approved!')
			return {**state, 'human_approved': True, 'human_feedback': ''}
		elif choice == 'e':
			feedback = input('  Enter your feedback > ').strip()
			console.info(f'Feedback received: {feedback}')
			return {**state, 'human_approved': False, 'human_feedback': feedback}
		elif choice == 'n':
			return {**state, 'human_approved': False, 'human_feedback': 'Please revise the content'}
		else:
			console.warning('Cover letter generation cancelled')
			return {**state, 'human_approved': False, 'error': 'Cancelled by user'}

	def _should_continue(self, state: CoverLetterState) -> Literal['approved', 'revise', 'end']:
		"""Determine next step after human review."""
		if state.get('error'):
			return 'end'
		if state.get('human_approved'):
			return 'approved'
		if state.get('human_feedback'):
			return 'revise'
		return 'end'

	async def _finalize_node(self, state: CoverLetterState) -> CoverLetterState:
		"""Finalize cover letter."""
		console.success('Finalizing cover letter...')

		job = state.get('job_analysis', {})

		result = {
			'content': state.get('content', {}),
			'full_text': state.get('full_text', ''),
			'job_title': job.get('role', ''),
			'company_name': job.get('company', ''),
			'tone': state.get('tone', 'professional'),
			'word_count': len(state.get('full_text', '').split()),
			'human_approved': True,
		}

		console.success('Cover letter complete!')

		# Save to persistence
		# Note: Ideally we generate a PDF here first.
		# For simplicity, we'll assume PDF generation happens in API or separate service
		# But wait, resume_storage_service expects PDF bytes.
		# We should generate PDF here if we want to save it.
		# Let's generate a simple PDF using reportlab or resume_service (which handles PDF compilation)

		# Integrating basic PDF generation for persistence
		try:
			# Create a simple PDF from text
			# Using temporary file
			import os
			import tempfile

			with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
				# PDF generation logic - simplistic for now, ideally use a template
				from reportlab.lib.pagesizes import letter
				from reportlab.lib.utils import simpleSplit
				from reportlab.pdfgen import canvas

				c = canvas.Canvas(tmp.name, pagesize=letter)
				width, height = letter

				text_object = c.beginText(50, height - 50)
				text_object.setFont('Helvetica', 12)

				# Split text into lines
				lines = state.get('full_text', '').split('\n')
				for line in lines:
					wrapped_lines = simpleSplit(line, 'Helvetica', 12, width - 100)
					for wrapped in wrapped_lines:
						text_object.textLine(wrapped)
					if not wrapped_lines:  # Empty line
						text_object.textLine('')

				c.drawText(text_object)
				c.save()
				tmp_path = tmp.name

			# Read bytes
			import asyncio
			def _read_pdf():
				with open(tmp_path, 'rb') as f:
					return f.read()
			pdf_bytes = await asyncio.to_thread(_read_pdf)

			os.unlink(tmp_path)

			# Save to storage
			if state.get('user_profile', {}).get('id'):
				await resume_storage_service.save_cover_letter(
					user_id=state['user_profile']['id'],
					pdf_content=pdf_bytes,
					job_url=job.get('job_url'),
					job_title=job.get('role'),
					company_name=job.get('company'),
					content=state.get('content', {}),
					tone=state.get('tone', 'professional'),
				)
				console.success('Cover letter saved to storage')

		except Exception as save_err:
			console.error(f'Failed to save cover letter: {save_err}')

		return {**state, 'result': result}

	# ============================================
	# Public API
	# ============================================

	async def run(self, *args, **kwargs) -> AgentResponse:
		"""Required abstract method - delegates to generate."""
		job_analysis = kwargs.get('job_analysis') or (args[0] if args else None)
		user_profile = kwargs.get('user_profile') or (args[1] if len(args) > 1 else None)
		tone = kwargs.get('tone', 'professional')
		hitl_handler = kwargs.get('hitl_handler', None)
		user_id = kwargs.get('user_id', None)

		if not job_analysis or not user_profile:
			return AgentResponse.create_error('job_analysis and user_profile are required')

		return await self.generate(job_analysis, user_profile, tone, hitl_handler, user_id)

	async def generate(
		self,
		job_analysis: JobAnalysis,
		user_profile: UserProfile,
		tone: str = 'professional',
		hitl_handler: Optional[Callable[[str, str], Any]] = None,
		user_id: Optional[str] = None,
	) -> AgentResponse:
		"""
		Generate a personalized cover letter with human verification.

		Args:
		    job_analysis: Analysis of the target job
		    user_profile: User's profile
		    tone: Writing tone ('professional', 'enthusiastic', 'formal', 'casual')
		    hitl_handler: Optional callback for HITL
		    user_id: The ID of the user requesting the cover letter

		Returns:
		    Dict containing cover letter content and metadata
		"""
		job_dict = job_analysis.model_dump() if hasattr(job_analysis, 'model_dump') else dict(job_analysis)
		profile_dict = user_profile.model_dump() if hasattr(user_profile, 'model_dump') else dict(user_profile)

		# Sanitize critical string fields
		for d in [job_dict, profile_dict]:
			for key, val in list(d.items()):
				if isinstance(val, str) and val:
					check = input_guard.check_sync(val)
					if check.is_blocked:
						slog.agent_error('cover_letter_agent', f'guardrail_blocked_{key}', {'reason': check.blocked_reason})
						return AgentResponse.create_error(f'Input validation failed for {key}: {check.blocked_reason}')
					d[key] = check.processed_text

		# Prepare initial state
		initial_state: CoverLetterState = {
			'job_analysis': job_dict,
			'user_profile': profile_dict,
			'tone': tone,
			'user_id': user_id,
			'hitl_handler': hitl_handler,
			'plan': [],
			'current_step': 0,
			'company_research': {},
			'content': {},
			'full_text': '',
			'needs_human_review': False,
			'human_approved': False,
			'human_feedback': '',
			'result': {},
			'error': '',
		}

		config = {'configurable': {'thread_id': 'cover_letter_session'}}

		try:
			# Rebuild graph per run so monkeypatched node methods (tests) are respected.
			graph = self._build_graph()
			final_state = await graph.ainvoke(initial_state, config)

			if final_state.get('error'):
				console.error(f'Error: {final_state["error"]}')
				return AgentResponse.create_error(final_state['error'])

			return AgentResponse.create_success(data=final_state.get('result', {}))

		except Exception as e:
			console.error(f'Cover letter generation failed: {e}')
			return AgentResponse.create_error(str(e))


# Singleton instance
cover_letter_agent = CoverLetterAgent()
