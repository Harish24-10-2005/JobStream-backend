"""
Interview Prep Agent - AI-powered interview preparation
Uses LangChain's DeepAgent for personalized interview coaching
"""

import json
from typing import Dict, List, Optional

from pydantic import BaseModel

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


# ============================================
# Pydantic Schemas for Strict Output Parsing
# ============================================
class STARFramework(BaseModel):
	situation: str
	task: str
	action: str
	result: str


class BehavioralQuestion(BaseModel):
	question: str
	why_asked: str
	key_points: List[str]
	star_framework: STARFramework


class BehavioralQuestionsModel(BaseModel):
	questions: List[BehavioralQuestion]


class TechnicalQuestion(BaseModel):
	question: str
	category: str
	technology: str
	difficulty: str
	key_concepts: List[str]
	sample_answer_points: List[str]
	follow_up_questions: List[str]
	requires_coding_environment: bool = False


class TechnicalQuestionsModel(BaseModel):
	technical_questions: List[TechnicalQuestion]


# ============================================
# Circuit Breakers & Guardrails
# ============================================
cb_groq = CircuitBreaker('groq', failure_threshold=5, retry_count=2)
input_guard = create_input_pipeline('medium')

# ============================================
# Tool Definitions for Interview DeepAgent
# ============================================


def analyze_job_requirements(role: str, company: str, tech_stack: List[str], job_description: str = '') -> Dict:
	"""
	Analyze job requirements to identify key interview focus areas.

	Args:
	    role: Job title
	    company: Company name
	    tech_stack: Required technologies
	    job_description: Full job description text

	Returns:
	    Analysis with focus areas, skills to highlight, and topic weights
	"""
	console.step(1, 5, 'Analyzing job requirements')

	# Categorize skills
	technical_skills = []
	soft_skills = []
	leadership_skills = []

	leadership_keywords = ['lead', 'manage', 'senior', 'principal', 'architect', 'head']
	soft_keywords = ['communication', 'team', 'collaborate', 'stakeholder']

	role_lower = role.lower()
	is_senior = any(kw in role_lower for kw in leadership_keywords)

	for skill in tech_stack:
		skill_lower = skill.lower()
		if any(kw in skill_lower for kw in soft_keywords):
			soft_skills.append(skill)
		else:
			technical_skills.append(skill)

	if is_senior:
		leadership_skills = ['Team Leadership', 'Mentoring', 'Technical Decision Making']

	analysis = {
		'role': role,
		'company': company,
		'is_senior_role': is_senior,
		'technical_focus': technical_skills[:5],
		'soft_skills_focus': soft_skills or ['Communication', 'Teamwork'],
		'leadership_focus': leadership_skills,
		'interview_rounds': [
			'Phone Screen',
			'Technical Round',
			'System Design' if is_senior else 'Coding Round',
			'Behavioral Round',
			'Hiring Manager',
		],
		'preparation_priority': {
			'technical': 40,
			'behavioral': 30,
			'system_design': 20 if is_senior else 10,
			'company_knowledge': 10,
		},
	}

	console.success(f'Identified {len(technical_skills)} technical focus areas')
	return analysis


def get_interview_resources(role: str, tech_stack: List[str], include_system_design: bool = False) -> Dict:
	"""
	Get curated interview preparation resources including DSA sheets,
	LeetCode problems, and discussion links.

	Args:
	    role: Target job role
	    tech_stack: Technologies for the role
	    include_system_design: Include system design resources for senior roles

	Returns:
	    Curated resources with links for interview preparation
	"""
	console.step(2, 6, 'Gathering interview resources')

	# Core DSA resources
	dsa_resources = {
		'dsa_sheets': [
			{
				'name': "Striver's SDE Sheet",
				'url': 'https://takeuforward.org/interviews/strivers-sde-sheet-top-coding-interview-problems/',
				'description': '180 problems covering all DSA topics',
				'difficulty': 'Medium-Hard',
			},
			{
				'name': 'NeetCode 150',
				'url': 'https://neetcode.io/practice',
				'description': 'Curated 150 LeetCode problems by topic',
				'difficulty': 'Easy-Hard',
			},
			{
				'name': 'Blind 75',
				'url': 'https://leetcode.com/discuss/general-discussion/460599/blind-75-leetcode-questions',
				'description': 'Top 75 LeetCode questions by frequency',
				'difficulty': 'Medium',
			},
			{
				'name': 'Grind 75',
				'url': 'https://www.techinterviewhandbook.org/grind75',
				'description': 'Curated list with customizable schedule',
				'difficulty': 'Easy-Hard',
			},
		],
		'leetcode_practice': [
			{
				'name': 'LeetCode Top Interview Questions',
				'url': 'https://leetcode.com/problem-list/top-interview-questions/',
				'description': 'Official LeetCode interview collection',
			},
			{
				'name': 'LeetCode Company Tags',
				'url': 'https://leetcode.com/company/',
				'description': 'Problems by company (FAANG, etc.)',
			},
		],
		'discussions': [
			{
				'name': 'LeetCode Discuss - Interview Experiences',
				'url': 'https://leetcode.com/discuss/interview-experience',
				'description': 'Real interview experiences from candidates',
			},
			{
				'name': 'r/cscareerquestions',
				'url': 'https://reddit.com/r/cscareerquestions',
				'description': 'Career advice and interview tips',
			},
			{
				'name': 'Glassdoor Interview Reviews',
				'url': 'https://glassdoor.com/Interview/',
				'description': 'Company-specific interview questions',
			},
		],
	}

	# Technology-specific resources
	tech_resources = {}

	tech_lower = [t.lower() for t in tech_stack]

	if any(t in tech_lower for t in ['python', 'django', 'flask', 'fastapi']):
		tech_resources['python'] = [
			{'name': 'Python Interview Questions', 'url': 'https://github.com/DopplerHQ/awesome-interview-questions#python'},
			{'name': 'Real Python Tutorials', 'url': 'https://realpython.com/tutorials/best-practices/'},
		]

	if any(t in tech_lower for t in ['javascript', 'react', 'node', 'typescript', 'vue', 'angular']):
		tech_resources['javascript'] = [
			{'name': 'JavaScript Interview Questions', 'url': 'https://github.com/sudheerj/javascript-interview-questions'},
			{'name': 'React Interview Questions', 'url': 'https://github.com/sudheerj/reactjs-interview-questions'},
		]

	if any(t in tech_lower for t in ['java', 'spring', 'kotlin']):
		tech_resources['java'] = [
			{'name': 'Java Interview Questions', 'url': 'https://github.com/DopplerHQ/awesome-interview-questions#java'},
			{'name': 'Spring Boot Guide', 'url': 'https://spring.io/guides'},
		]

	if any(t in tech_lower for t in ['sql', 'postgresql', 'mysql', 'database']):
		tech_resources['database'] = [
			{'name': 'SQL Practice - HackerRank', 'url': 'https://hackerrank.com/domains/sql'},
			{'name': 'SQL Zoo', 'url': 'https://sqlzoo.net/'},
		]

	if any(t in tech_lower for t in ['aws', 'azure', 'gcp', 'cloud']):
		tech_resources['cloud'] = [
			{'name': 'AWS Interview Questions', 'url': 'https://github.com/donnemartin/system-design-primer#aws'},
			{'name': 'Cloud Practitioner Guide', 'url': 'https://aws.amazon.com/certification/'},
		]

	if any(t in tech_lower for t in ['ml', 'ai', 'machine learning', 'deep learning', 'data science']):
		tech_resources['ml'] = [
			{'name': 'ML Interview Prep', 'url': 'https://github.com/khangich/machine-learning-interview'},
			{'name': 'Deep Learning Questions', 'url': 'https://github.com/andrewekhalel/MLQuestions'},
		]

	# System Design resources for senior roles
	system_design = {}
	if include_system_design:
		system_design = {
			'resources': [
				{
					'name': 'System Design Primer',
					'url': 'https://github.com/donnemartin/system-design-primer',
					'description': 'Comprehensive system design guide',
				},
				{
					'name': 'Grokking System Design',
					'url': 'https://www.designgurus.io/course/grokking-the-system-design-interview',
					'description': 'Popular paid course',
				},
				{
					'name': 'System Design YouTube - Gaurav Sen',
					'url': 'https://youtube.com/@gaborvadai',
					'description': 'Free video explanations',
				},
				{
					'name': 'High Scalability Blog',
					'url': 'http://highscalability.com/',
					'description': 'Real-world architecture case studies',
				},
			],
			'common_topics': [
				'URL Shortener',
				'Twitter/Instagram Feed',
				'Chat System',
				'Rate Limiter',
				'Distributed Cache',
				'Load Balancer',
				'Database Sharding',
				'Message Queue',
				'Search Engine',
			],
		}

	# Behavioral interview prep
	behavioral_resources = [
		{
			'name': 'STAR Method Guide',
			'url': 'https://www.themuse.com/advice/star-interview-method',
			'description': 'How to structure behavioral answers',
		},
		{
			'name': 'Amazon Leadership Principles',
			'url': 'https://www.amazon.jobs/en/principles',
			'description': 'Essential for Amazon interviews',
		},
		{
			'name': 'Behavioral Questions by Company',
			'url': 'https://leetcode.com/discuss/interview-question?currentPage=1&orderBy=hot&query=behavioral',
			'description': 'LeetCode behavioral discussions',
		},
	]

	resources = {
		'dsa_sheets': dsa_resources['dsa_sheets'],
		'leetcode_collections': dsa_resources['leetcode_practice'],
		'discussions_forums': dsa_resources['discussions'],
		'tech_specific': tech_resources,
		'behavioral_prep': behavioral_resources,
		'study_plan': {
			'week_1': 'Focus on Arrays, Strings, HashMaps',
			'week_2': 'Trees, Graphs, BFS/DFS',
			'week_3': 'Dynamic Programming basics',
			'week_4': 'System Design + Behavioral prep',
		},
	}

	if include_system_design:
		resources['system_design'] = system_design

	console.success(f'Found {len(dsa_resources["dsa_sheets"])} DSA sheets, {len(tech_resources)} tech-specific resources')
	return resources


def generate_behavioral_questions(
	role: str, company: str, is_senior: bool = False, focus_areas: List[str] = None, learnings_prompt: str = ''
) -> str:
	"""
	Generate behavioral interview questions with STAR format guidance.

	Args:
	    role: Target job role
	    company: Target company
	    is_senior: Whether it's a senior/leadership position
	    focus_areas: Specific areas to focus on

	Returns:
	    JSON string of behavioral questions with answer frameworks
	"""
	console.step(2, 5, 'Generating behavioral questions')
	slog.agent('interview_agent', 'generate_behavioral_questions', role=role, company=company, is_senior=is_senior)

	seniority = 'senior/leadership' if is_senior else 'individual contributor'
	focus = ', '.join(focus_areas) if focus_areas else 'general professional skills'

	prompt = f"""
    Generate 8 behavioral interview questions for a {role} position at {company}.
    
    Role Level: {seniority}
    Focus Areas: {focus}
    {learnings_prompt}
    
    For each question, provide:
    1. The question
    2. Why interviewers ask this
    3. Key points to cover in your answer
    4. A STAR framework outline
    
    Return ONLY valid JSON:
    {{
        "questions": [
            {{
                "question": "Tell me about a time...",
                "why_asked": "To assess...",
                "key_points": ["point1", "point2"],
                "star_framework": {{
                    "situation": "Describe the context",
                    "task": "What was your responsibility",
                    "action": "What specific steps did you take",
                    "result": "What was the outcome (quantify if possible)"
                }}
            }}
        ]
    }}
    """

	try:
		parsed = get_llm(temperature=0.7).generate_json(
			prompt=prompt, system_prompt='You are an expert interview coach.', agent_name='interview_agent'
		)
		if 'error' in parsed:
			raise Exception(parsed['error'])

		validated_data = BehavioralQuestionsModel.model_validate(parsed)

		slog.agent('interview_agent', 'behavioral_questions_generated', count=len(validated_data.questions))
		return validated_data.model_dump_json()

	except Exception as e:
		slog.agent_error('interview_agent', 'behavioral_questions_failed', error=str(e))
		return AgentResponse.create_error(str(e)).model_dump_json()


def generate_technical_questions(
	role: str, tech_stack: List[str], difficulty: str = 'medium', learnings_prompt: str = '', rag_context: str = ''
) -> str:
	"""
	Generate technical interview questions based on the role's tech stack.

	Args:
	    role: Target job role
	    tech_stack: Required technologies
	    difficulty: easy, medium, or hard
	    learnings_prompt: Personal learnings to consider

	Returns:
	    JSON string of technical questions with solution hints
	"""
	console.step(3, 5, 'Generating technical questions')
	slog.agent('interview_agent', 'generate_technical_questions', role=role, difficulty=difficulty)

	tech_list = ', '.join(tech_stack[:6])

	prompt = f"""
    Generate 10 technical interview questions for a {role} role.
    
    Technologies to cover: {tech_list}
    Difficulty: {difficulty}
    {learnings_prompt}
    {rag_context}
    
    Include a mix of:
    - Conceptual questions
    - Coding problems
    - System design (if applicable)
    - Debugging scenarios
    
    Return ONLY valid JSON:
    {{
        "technical_questions": [
            {{
                "question": "...",
                "category": "conceptual|coding|system_design|debugging",
                "technology": "specific tech being tested",
                "difficulty": "easy|medium|hard",
                "key_concepts": ["concept1", "concept2"],
                "sample_answer_points": ["point1", "point2"],
                "follow_up_questions": ["follow up 1"]
            }}
        ]
    }}
    """

	try:
		parsed = get_llm(temperature=0.5).generate_json(
			prompt=prompt, system_prompt='You are a senior technical interviewer.', agent_name='interview_agent'
		)
		if 'error' in parsed:
			raise Exception(parsed['error'])

		validated_data = TechnicalQuestionsModel.model_validate(parsed)

		slog.agent('interview_agent', 'technical_questions_generated', count=len(validated_data.technical_questions))
		return validated_data.model_dump_json()

	except Exception as e:
		slog.agent_error('interview_agent', 'technical_questions_failed', error=str(e))
		return AgentResponse.create_error(str(e)).model_dump_json()


def create_star_response(question: str, profile_json: str, context: str = '') -> str:
	"""
	Create a STAR-format answer using the candidate's actual experience.

	Args:
	    question: The interview question to answer
	    profile_json: JSON string of user profile
	    context: Additional context about the role

	Returns:
	    JSON string with structured STAR response
	"""
	console.step(4, 5, 'Creating personalized STAR response')
	slog.agent('interview_agent', 'create_star_response', question=question[:80])

	try:
		profile = json.loads(profile_json)
	except json.JSONDecodeError:
		return AgentResponse.create_error('Invalid profile JSON').model_dump_json()

	# Extract relevant experience
	experience = profile.get('experience', [])
	projects = profile.get('projects', [])

	prompt = f"""
    Create a STAR-format answer for this interview question using the candidate's REAL experience.
    
    QUESTION: {question}
    
    CANDIDATE'S EXPERIENCE:
    {json.dumps(experience, indent=2)[:2000]}
    
    CANDIDATE'S PROJECTS:
    {json.dumps(projects, indent=2)[:1000]}
    
    ADDITIONAL CONTEXT: {context}
    
    Write a compelling answer that:
    1. Uses a REAL example from their experience/projects
    2. Shows specific actions and results
    3. Quantifies impact where possible
    4. Is 1-2 minutes when spoken
    
    Return ONLY valid JSON:
    {{
        "question": "the question",
        "star_response": {{
            "situation": "Specific context from their experience",
            "task": "Their responsibility",
            "action": "Specific steps they took",
            "result": "Measurable outcome"
        }},
        "full_answer": "Complete spoken answer (2-3 paragraphs)",
        "key_points_to_emphasize": ["point1", "point2"],
        "potential_follow_ups": ["follow up 1", "follow up 2"],
        "tips": ["delivery tip 1"]
    }}
    """

	try:
		parsed = get_llm(temperature=0.6).generate_json(
			prompt=prompt,
			system_prompt='You are an expert interview coach. Create compelling, authentic answers.',
			agent_name='interview_agent',
		)
		if 'error' in parsed:
			raise Exception(parsed['error'])
		slog.agent('interview_agent', 'star_response_created', question=question[:80])
		return json.dumps(parsed)

	except Exception as e:
		slog.agent_error('interview_agent', 'star_response_failed', error=str(e))
		return AgentResponse.create_error(str(e)).model_dump_json()


def start_practice_mode(questions_json: str, practice_type: str = 'behavioral') -> Dict:
	"""
	Start interactive practice mode for interview preparation.
	Human-in-the-Loop: User practices answering questions.

	Args:
	    questions_json: JSON string of questions to practice
	    practice_type: behavioral or technical

	Returns:
	    Practice session results with feedback
	"""
	console.step(5, 5, 'Starting Practice Mode')
	console.divider()
	console.header('🎯 INTERVIEW PRACTICE MODE')

	try:
		questions_data = json.loads(questions_json)
	except json.JSONDecodeError:
		return AgentResponse.create_error('Invalid questions JSON', completed=False).model_dump()

	if practice_type == 'behavioral':
		questions = questions_data.get('questions', [])
	else:
		questions = questions_data.get('technical_questions', [])

	if not questions:
		console.warning('No questions available for practice')
		return AgentResponse.create_error('No questions available', completed=False).model_dump()

	console.info(f'You have {len(questions)} questions to practice.')
	console.info('Type your answer, then press Enter twice to submit.')
	console.info("Type 'skip' to skip, 'quit' to end practice.\n")

	results = []

	for i, q in enumerate(questions[:5], 1):  # Limit to 5 for practice
		question = q.get('question', str(q))

		console.box(f'Question {i}', question)

		# Get user's answer
		print('\n  Your answer (press Enter twice when done):')
		lines = []
		while True:
			line = input('  > ')
			if line.strip().lower() == 'quit':
				console.info('Practice session ended.')
				return {'completed': False, 'practiced': i - 1, 'results': results}
			if line.strip().lower() == 'skip':
				results.append({'question': question, 'skipped': True})
				break
			if line == '' and lines and lines[-1] == '':
				break
			lines.append(line)

		if lines and lines[-1] != 'skip':
			answer = '\n'.join(lines).strip()

			# Simple feedback
			word_count = len(answer.split())

			feedback = {'question': question, 'skipped': False, 'word_count': word_count, 'tips': []}

			if word_count < 50:
				feedback['tips'].append('Consider adding more detail to your answer')
			if word_count > 300:
				feedback['tips'].append('Try to be more concise')
			if 'I' not in answer:
				feedback['tips'].append("Use 'I' to show personal ownership of actions")

			results.append(feedback)
			console.success(f'Answer recorded. Word count: {word_count}')

	console.divider()
	console.success(f'Practice complete! You answered {len([r for r in results if not r.get("skipped")])} questions.')

	return {'completed': True, 'total_questions': len(questions), 'practiced': len(results), 'results': results}


# ============================================
# Interview Agent System Prompt
# ============================================

INTERVIEW_AGENT_SYSTEM_PROMPT = """You are an expert interview coach helping candidates prepare for job interviews.

## Your Capabilities

### `analyze_job_requirements`
Analyze the job to identify key interview focus areas and preparation priorities.

### `get_interview_resources`
Get curated preparation resources: DSA sheets (Striver, NeetCode, Blind 75), LeetCode problems, discussion forums, and tech-specific guides.

### `generate_behavioral_questions`
Generate behavioral interview questions with STAR framework guidance.

### `generate_technical_questions`
Generate technical interview questions based on the role's tech stack.

### `create_star_response`
Create personalized STAR-format answers using the candidate's REAL experience.

### `start_practice_mode`
Start interactive practice mode for hands-on preparation.

## Workflow

1. **Analyze** - Understand the job requirements
2. **Get Resources** - Provide DSA sheets, LeetCode links, and forums
3. **Generate Questions** - Create both behavioral and technical questions
4. **Prepare Answers** - Create STAR responses for key behavioral questions
5. **Practice** - Offer practice mode for the candidate

## Guidelines

- Always provide relevant DSA/LeetCode resources for the role
- Use the candidate's ACTUAL experience for answer suggestions
- Quantify results wherever possible (%, $, time saved)
- Focus on the top skills mentioned in the job description
- For senior roles, include leadership and system design resources
- Always encourage specificity over generality
"""


class InterviewAgent(BaseAgent):
	"""
	DeepAgent-based Interview Preparation Agent.

	Generates personalized interview questions and STAR-format answers
	based on job requirements and candidate experience.
	"""

	def __init__(self):
		super().__init__()

		self.llm = get_llm(temperature=0.5)

	async def run(self, *args, **kwargs) -> AgentResponse:
		"""Required abstract method - delegates to prepare_interview."""
		job_analysis = kwargs.get('job_analysis') or (args[0] if args else None)
		user_profile = kwargs.get('user_profile') or (args[1] if len(args) > 1 else None)
		user_id = kwargs.get('user_id', None)

		if not job_analysis or not user_profile:
			return AgentResponse.create_error('job_analysis and user_profile are required')

		return await self.prepare_interview(job_analysis, user_profile, user_id=user_id)

	async def chat_with_persona(self, history: List[Dict], current_input: str, persona_settings: Dict) -> str:
		"""Generation logic for persona chat."""
		try:
			system_prompt = f"""You are {persona_settings['name']}, acting as an interviewer for a {persona_settings.get('role', 'Developer')} role at {persona_settings.get('company', 'Tech Co')}.
            
STYLE: {persona_settings.get('style', 'Professional, neutral')}
GOAL: Assess the candidate's fit. Be realistic. Do not give the answer away.
Keep responses conversational (under 3 sentences) unless explaining a complex concept.
"""
			messages = [{'role': 'system', 'content': system_prompt}]

			# Add context window (last 6 turns)
			for msg in history[-6:]:
				messages.append({'role': msg.get('role', 'user'), 'content': msg.get('content', '')})

			messages.append({'role': 'user', 'content': current_input})

			content = await self.llm.ainvoke(messages, agent_name='interview_agent')

			slog.agent('interview_agent', 'persona_chat_response', persona=persona_settings.get('name', 'unknown'))

			return content

		except Exception as e:
			slog.agent_error('interview_agent', 'persona_chat_failed', error=str(e))
			return AgentResponse.create_error('I apologize, but I lost my train of thought. Could you repeat that?').message

	async def prepare_interview(
		self, job_analysis: JobAnalysis, user_profile: UserProfile, include_practice: bool = False, user_id: Optional[str] = None
	) -> AgentResponse:
		"""
		Prepare comprehensive interview materials.

		Args:
		    job_analysis: Analysis of the target job
		    user_profile: Candidate's profile
		    include_practice: Whether to include practice mode
		    user_id: The ID of the user requesting the interview

		Returns:
		    Dict with questions, suggested answers, and prep materials
		"""
		console.subheader('🎯 Interview Prep Agent')
		console.info('Generating personalized interview preparation...')

		job_data = job_analysis.model_dump() if hasattr(job_analysis, 'model_dump') else dict(job_analysis)
		profile_data = user_profile.model_dump() if hasattr(user_profile, 'model_dump') else dict(user_profile)

		# Sanitize critical string fields
		for data_dict, dict_name in [(job_data, 'job_data'), (profile_data, 'profile_data')]:
			for key, val in list(data_dict.items()):
				if isinstance(val, str) and val:
					check = input_guard.check_sync(val)
					if check.is_blocked:
						slog.agent_error(
							'interview_agent', f'guardrail_blocked_{dict_name}_{key}', {'reason': check.blocked_reason}
						)
						return AgentResponse.create_error(
							f'Input validation failed for {dict_name}.{key}: {check.blocked_reason}'
						)
					data_dict[key] = check.processed_text
				elif isinstance(val, list):  # Handle lists of strings, e.g., tech_stack
					sanitized_list = []
					for item in val:
						if isinstance(item, str):
							check = input_guard.check_sync(item)
							if check.is_blocked:
								slog.agent_error(
									'interview_agent',
									f'guardrail_blocked_{dict_name}_{key}_item',
									{'reason': check.blocked_reason},
								)
								return AgentResponse.create_error(
									f'Input validation failed for {dict_name}.{key} item: {check.blocked_reason}'
								)
							sanitized_list.append(check.processed_text)
						else:
							sanitized_list.append(item)  # Keep non-string items as is
					data_dict[key] = sanitized_list

		practice_instruction = (
			'Offer practice mode at the end.' if include_practice else 'Do not start practice mode unless asked.'
		)

		task_message = f"""
        Prepare comprehensive interview materials for this candidate and job.
        
        ## Job Details
        - Role: {job_data.get('role', 'Unknown')}
        - Company: {job_data.get('company', 'Unknown')}
        - Tech Stack: {', '.join(job_data.get('tech_stack', []))}
        
        ## Candidate Profile (JSON)
        ```json
        {json.dumps(profile_data, indent=2)[:3000]}
        ```
        
        ## Instructions
        1. Analyze the job requirements
        2. Generate 8 behavioral questions with STAR frameworks
        3. Generate 10 technical questions
        4. Create STAR responses for the top 3 behavioral questions using the candidate's experience
        5. {practice_instruction}
        
        Provide comprehensive preparation materials.
        """

		try:
			# Use direct function calls instead of agent.invoke
			# Step 1: Analyze job requirements
			analysis = analyze_job_requirements(
				role=job_data.get('role', 'Unknown'),
				company=job_data.get('company', 'Unknown'),
				tech_stack=job_data.get('tech_stack', []),
				job_description='',
			)

			# Step 2: Get interview resources
			resources = get_interview_resources(
				role=job_data.get('role', 'Unknown'),
				tech_stack=job_data.get('tech_stack', []),
				include_system_design=analysis.get('is_senior_role', False),
			)

			# Fetch learnings
			learnings_prompt = ''
			if user_id:
				learnings = await agent_memory.get_learnings('interview_agent', user_id)
				if learnings:
					bullets = '\n'.join(f'- {learning}' for learning in learnings)
					learnings_prompt = (
						f'\n\n## Candidate Weaknesses / Focus Areas:\nEnsure some questions cover these areas:\n{bullets}\n'
					)
					console.info(f'Injected {len(learnings)} personal learnings into full interview prep')

			# Step 3: Generate behavioral questions
			behavioral_questions = generate_behavioral_questions(
				role=job_data.get('role', 'Unknown'),
				company=job_data.get('company', 'Unknown'),
				is_senior=analysis.get('is_senior_role', False),
				focus_areas=analysis.get('soft_skills_focus', []),
				learnings_prompt=learnings_prompt,
			)

			# Step 4: Generate technical questions
			rag_context = ''
			if user_profile and user_profile.id:
				try:
					tech_query = f'Technical depth and specific projects using {", ".join(job_data.get("tech_stack", [])[:3])}'
					rag_results = await rag_service.query(user_profile.id, tech_query, limit=2)
					if rag_results:
						rag_context = (
							"\n\n## Candidate's Past Technical Content (RAG):\nFormulate some questions that touch lightly on these topics so they feel personalized:\n"
							+ '\n'.join([f'- {r["content"]}' for r in rag_results])
						)
				except Exception as e:
					console.warning(f'RAG query failed in interview prep: {e}')

			technical_questions = generate_technical_questions(
				role=job_data.get('role', 'Unknown'),
				tech_stack=job_data.get('tech_stack', []),
				difficulty='medium',  # Default difficulty
				learnings_prompt=learnings_prompt,
				rag_context=rag_context,
			)

			behavioral_json = json.loads(behavioral_questions)
			technical_json = json.loads(technical_questions)
			behavioral_list = behavioral_json.get('questions', behavioral_json if isinstance(behavioral_json, list) else [])
			technical_list = technical_json.get(
				'technical_questions', technical_json if isinstance(technical_json, list) else []
			)

			# Backward-compatibility fields for older consumers/tests.
			for item in behavioral_list:
				if isinstance(item, dict) and 'framework' not in item:
					item['framework'] = 'STAR'

			console.success('Interview preparation complete!')

			return AgentResponse.create_success(
				data={
					'job_analysis': analysis,
					'resources': resources,
					'behavioral_questions': behavioral_list,
					'technical_questions': technical_list,
					'job_title': job_data.get('role', ''),
					'company_name': job_data.get('company', ''),
				}
			)

		except Exception as e:
			console.error(f'Interview preparation failed: {e}')
			return AgentResponse.create_error(f'Interview preparation failed: {e}')

	async def quick_prep(self, role: str, company: str, tech_stack: List[str], user_id: Optional[str] = None) -> AgentResponse:
		"""Quick preparation without full profile - generates generic questions and resources."""
		# Sanitize scalar inputs
		for val, name in [(role, 'role'), (company, 'company')]:
			if val:
				check = input_guard.check_sync(val)
				if check.is_blocked:
					slog.agent_error('interview_agent', f'guardrail_blocked_{name}', {'reason': check.blocked_reason})
					return AgentResponse.create_error(f'Input validation failed: {check.blocked_reason}')
				if name == 'role':
					role = check.processed_text
				elif name == 'company':
					company = check.processed_text

		# Handle tech stack sanitization
		sanitized_tech_stack = []
		for tech in tech_stack:
			check = input_guard.check_sync(tech)
			if check.is_blocked:
				slog.agent_error('interview_agent', 'guardrail_blocked_tech_stack', reason=check.blocked_reason)
				return AgentResponse.create_error(f'Input validation failed on tech stack: {check.blocked_reason}')
			sanitized_tech_stack.append(check.processed_text)
		tech_stack = sanitized_tech_stack

		console.subheader('🎯 Quick Interview Prep')

		# Analyze requirements
		analysis = analyze_job_requirements(role, company, tech_stack)

		# Get interview resources
		resources = get_interview_resources(role, tech_stack, include_system_design=analysis.get('is_senior_role', False))

		# Fetch learnings
		learnings_prompt = ''
		if user_id:
			learnings = await agent_memory.get_learnings('interview_agent', user_id)
			if learnings:
				bullets = '\n'.join(f'- {learning}' for learning in learnings)
				learnings_prompt = (
					f'\n\n## Candidate Weaknesses / Focus Areas:\nEnsure some questions cover these areas:\n{bullets}\n'
				)
				console.info(f'Injected {len(learnings)} personal learnings into interview prep')

		# Generate questions
		behavioral = generate_behavioral_questions(
			role, company, analysis.get('is_senior_role', False), analysis.get('soft_skills_focus', []), learnings_prompt
		)

		technical = generate_technical_questions(role, tech_stack, 'medium', learnings_prompt)

		return AgentResponse.create_success(
			data={
				'analysis': analysis,
				'resources': resources,
				'behavioral_questions': json.loads(behavioral),
				'technical_questions': json.loads(technical),
			}
		)


# Lazy singleton instance
_interview_agent = None


def get_interview_agent() -> InterviewAgent:
	"""Get or create the InterviewAgent singleton."""
	global _interview_agent
	if _interview_agent is None:
		_interview_agent = InterviewAgent()
	return _interview_agent


# For backwards compatibility
interview_agent = None  # Use get_interview_agent() instead
