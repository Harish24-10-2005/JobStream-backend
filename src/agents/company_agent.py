"""
Company Research Agent - AI-powered company analysis
Uses LangChain's DeepAgent for pre-interview company research
"""

from datetime import date
from typing import Dict

from langchain_community.utilities import SerpAPIWrapper

from src.automators.base import BaseAgent
from src.core.circuit_breaker import CircuitBreaker
from src.core.config import settings
from src.core.console import console
from src.core.guardrails import create_input_pipeline
from src.core.llm_provider import get_llm
from src.core.structured_logger import slog
from src.core.types import AgentResponse

# ============================================
# Circuit Breakers & Guardrails
# ============================================
cb_serpapi = CircuitBreaker('serpapi', failure_threshold=3, retry_count=1)
cb_groq = CircuitBreaker('groq', failure_threshold=5, retry_count=2)
input_guard = create_input_pipeline('medium')

# ============================================
# Tool Definitions for Company DeepAgent
# ============================================


def search_company_info(company: str, role: str = '') -> Dict:
	"""
	Search for basic company information.

	Args:
	    company: Company name
	    role: Target role (optional, for context)

	Returns:
	    Company overview with key facts
	"""
	console.step(1, 4, f'Researching {company}')

	# Run input guardrails
	for val, name in [(company, 'company'), (role, 'role')]:
		if val:
			check = input_guard.check_sync(val)
			if check.is_blocked:
				slog.agent_error('company_agent', f'guardrail_blocked_{name}', error=check.blocked_reason or "Blocked")
				return AgentResponse.create_error(check.blocked_reason or "Blocked", company_name=company).model_dump()
			if name == 'company':
				company = check.processed_text
			elif name == 'role':
				role = check.processed_text

	slog.agent('company_agent', 'search_company_info', company=company, role=role)

	# Search Company Info
	search = SerpAPIWrapper(serpapi_api_key=settings.serpapi_api_key.get_secret_value())
	search_query = f'{company} company profile industry products competitors latest news'
	try:
		search_results = cb_serpapi.call_sync(search.run, search_query)
	except Exception as e:
		slog.agent_error('company_agent', 'serpapi_search_failed', query=search_query, error=str(e))
		search_results = 'Search unavailable.'

	prompt = f"""
    Provide a company research summary for {company}.
    Context: Candidate interviewing for {role or 'a position'} there.
    
    SEARCH RESULTS:
    {search_results}
    
    Return ONLY valid JSON with realistic, helpful information based on the search results where possible:
    {{
        "company_name": "{company}",
        "industry": "Tech/Finance/etc",
        "size": "Startup/Mid-size/Enterprise",
        "employee_count": "approximate",
        "founded": "year",
        "headquarters": "location",
        "mission": "company mission statement",
        "values": ["value1", "value2"],
        "tech_stack": ["known technologies"],
        "products": ["main products/services"],
        "competitors": ["competitor1", "competitor2"],
        "recent_news": ["recent headline 1", "recent headline 2"],
        "interview_tips": [
            "Mention their mission about...",
            "Show interest in their product..."
        ],
        "questions_to_ask": [
            "Good question for the interviewer",
            "Another insightful question"
        ],
        "sources": [
            "Source 1 (URL)",
            "Source 2 (URL)"
        ]
    }}
    """

	try:
		parsed = get_llm(temperature=0.3).generate_json(
			prompt=prompt,
			system_prompt='You are a company research expert. Use the provided search results to verify facts.',
			agent_name='company_agent',
		)

		if 'error' in parsed:
			raise Exception(parsed['error'])

		console.success(f'Found info for {company}')
		slog.agent('company_agent', 'search_company_info_complete', company=company)
		return parsed
	except Exception as e:
		console.error(f'Failed to research company: {e}')
		slog.agent_error('company_agent', 'search_company_info_failed', company=company, error=str(e))
		return AgentResponse.create_error(str(e), company_name=company).model_dump()


def analyze_company_culture(company: str, role: str = '') -> Dict:
	"""
	Analyze company culture based on available data.

	Args:
	    company: Company name
	    role: Target role for context

	Returns:
	    Culture analysis with work-life balance, values, etc.
	"""
	console.step(2, 4, 'Analyzing company culture')

	# Run input guardrails
	for val, name in [(company, 'company'), (role, 'role')]:
		if val:
			check = input_guard.check_sync(val)
			if check.is_blocked:
				slog.agent_error('company_agent', f'guardrail_blocked_{name}', error=check.blocked_reason or "Blocked")
				return AgentResponse.create_error(check.blocked_reason or "Blocked").model_dump()
			if name == 'company':
				company = check.processed_text
			elif name == 'role':
				role = check.processed_text

	slog.agent('company_agent', 'analyze_company_culture', company=company, role=role)

	# Analyze Culture Search
	search = SerpAPIWrapper(serpapi_api_key=settings.serpapi_api_key.get_secret_value())
	search_query = f'{company} work culture employee reviews glassdoor {role}'
	try:
		search_results = cb_serpapi.call_sync(search.run, search_query)
	except Exception as e:
		slog.agent_error('company_agent', 'serpapi_search_failed', query=search_query, error=str(e))
		search_results = 'Search unavailable.'
	prompt = f"""
    Analyze the work culture at {company} for someone interviewing for {role or 'a tech role'}.
    
    SEARCH RESULTS:
    {search_results}
    
    Provide realistic insights based on search results.
    
    Return ONLY valid JSON:
    {{
        "culture_type": "Startup/Corporate/Remote-first/etc",
        "work_life_balance": {{
            "rating": "Good/Average/Demanding",
            "notes": "explanation"
        }},
        "growth_opportunities": {{
            "rating": "Excellent/Good/Limited",
            "notes": "explanation"
        }},
        "management_style": "Flat/Hierarchical/Mixed",
        "remote_policy": "Full remote/Hybrid/In-office",
        "diversity_inclusion": "Strong/Growing/Unknown",
        "engineering_culture": {{
            "code_review": true,
            "testing": "Strong/Moderate/Weak",
            "documentation": "Good/Average/Lacking",
            "innovation_time": "20% time/Hackathons/None"
        }},
        "pros": [
            "Pro 1",
            "Pro 2"
        ],
        "cons": [
            "Con 1",
            "Con 2"
        ],
        "best_for": "Type of person who thrives here",
        "glassdoor_style_rating": 3.8,
        "sources": [
            "Source 1",
            "Source 2"
        ]
    }}
    """

	try:
		parsed = get_llm(temperature=0.4).generate_json(
			prompt=prompt,
			system_prompt='You are an HR and culture analyst. Be balanced and realistic.',
			agent_name='company_agent',
		)

		if 'error' in parsed:
			raise Exception(parsed['error'])

		console.success('Culture analysis complete')
		slog.agent('company_agent', 'culture_analysis_complete', company=company)
		return parsed
	except Exception as e:
		console.error(f'Failed to analyze culture: {e}')
		slog.agent_error('company_agent', 'culture_analysis_failed', company=company, error=str(e))
		return AgentResponse.create_error(str(e)).model_dump()


def identify_red_flags(company: str, job_description: str = '') -> Dict:
	"""
	Identify potential red flags about the company or job posting.

	Args:
	    company: Company name
	    job_description: Job posting text (optional)

	Returns:
	    Red flags and concerns to investigate
	"""
	console.step(3, 4, 'Identifying red flags')

	# Run input guardrails
	for val, name in [(company, 'company'), (job_description, 'job_description')]:
		if val:
			check = input_guard.check_sync(val)
			if check.is_blocked:
				slog.agent_error('company_agent', f'guardrail_blocked_{name}', error=check.blocked_reason or "Blocked")
				return AgentResponse.create_error(check.blocked_reason or "Blocked").model_dump()
			if name == 'company':
				company = check.processed_text
			elif name == 'job_description':
				job_description = check.processed_text

	slog.agent('company_agent', 'identify_red_flags', company=company, has_jd=bool(job_description))

	# Red Flags Search
	search = SerpAPIWrapper(serpapi_api_key=settings.serpapi_api_key.get_secret_value())
	search_query = f'{company} controversial news lawsuits layoffs reviews red flags'
	try:
		search_results = cb_serpapi.call_sync(search.run, search_query)
	except Exception as e:
		slog.agent_error('company_agent', 'serpapi_search_failed', query=search_query, error=str(e))
		search_results = 'Search unavailable.'
	jd_context = f'\n\nJob Description:\n{job_description[:1500]}' if job_description else ''

	prompt = f"""
    Analyze potential red flags for {company}.{jd_context}
    
    SEARCH RESULTS:
    {search_results}
    
    Check for common warning signs candidates should investigate based on the search results.
    
    Return ONLY valid JSON:
    {{
        "company_red_flags": [
            {{
                "flag": "Description of concern",
                "severity": "high|medium|low",
                "how_to_verify": "How to investigate this"
            }}
        ],
        "job_posting_red_flags": [
            {{
                "flag": "Vague salary/Unrealistic expectations/etc",
                "severity": "high|medium|low",
                "what_to_ask": "Question to clarify"
            }}
        ],
        "questions_to_ask_in_interview": [
            "Why is this position open?",
            "What happened to the previous person?",
            "What does success look like in 6 months?"
        ],
        "things_to_research": [
            "Check Glassdoor reviews",
            "LinkedIn employee tenure",
            "Recent funding/layoffs news"
        ],
        "overall_risk_level": "low|medium|high",
        "recommendation": "Proceed with caution / Looks good / Major concerns",
        "sources": ["Source 1", "Source 2"]
    }}
    """

	try:
		parsed = get_llm(temperature=0.3).generate_json(
			prompt=prompt,
			system_prompt='You are a career counselor helping candidates avoid bad job situations. Be thorough but fair.',
			agent_name='company_agent',
		)

		if 'error' in parsed:
			raise Exception(parsed['error'])

		risk = parsed.get('overall_risk_level', 'unknown')
		slog.agent('company_agent', 'red_flags_complete', company=company, risk_level=risk)
		if risk == 'low':
			console.success('Low risk - looks good!')
		elif risk == 'medium':
			console.warning('Medium risk - investigate further')
		else:
			console.error('High risk - proceed with caution')

		return parsed

	except Exception as e:
		slog.agent_error('company_agent', 'red_flags_failed', company=company, error=str(e))
		return AgentResponse.create_error(str(e)).model_dump()


def get_interview_insights(company: str, role: str) -> Dict:
	"""
	Get interview insights and tips for the specific company.

	Args:
	    company: Company name
	    role: Target role

	Returns:
	    Interview process insights and preparation tips
	"""
	console.step(4, 4, 'Gathering interview insights')

	# Run input guardrails
	for val, name in [(company, 'company'), (role, 'role')]:
		if val:
			check = input_guard.check_sync(val)
			if check.is_blocked:
				slog.agent_error('company_agent', f'guardrail_blocked_{name}', error=check.blocked_reason or "Blocked")
				return AgentResponse.create_error(check.blocked_reason or "Blocked").model_dump()
			if name == 'company':
				company = check.processed_text
			elif name == 'role':
				role = check.processed_text

	slog.agent('company_agent', 'get_interview_insights', company=company, role=role)

	# Interview Insights Search
	search = SerpAPIWrapper(serpapi_api_key=settings.serpapi_api_key.get_secret_value())
	search_query = f'{company} interview process questions {role} technical behavioral rounds'
	try:
		search_results = cb_serpapi.call_sync(search.run, search_query)
	except Exception as e:
		slog.agent_error('company_agent', 'serpapi_search_failed', query=search_query, error=str(e))
		search_results = 'Search unavailable.'
	prompt = f"""
    Provide interview insights for {role} at {company}.
    
    SEARCH RESULTS:
    {search_results}
    
    Provide insights based on search results.
    
    Return ONLY valid JSON:
    {{
        "interview_process": {{
            "typical_rounds": ["Phone Screen", "Technical", "Onsite"],
            "duration": "2-4 weeks typical",
            "difficulty": "Medium/Hard"
        }},
        "common_question_topics": [
            "Topic 1 they often ask about",
            "Topic 2",
            "Topic 3"
        ],
        "technical_focus": [
            "Coding patterns they prefer",
            "System design if senior"
        ],
        "behavioral_themes": [
            "Leadership principles they value",
            "Cultural fit aspects"
        ],
        "tips_from_candidates": [
            "Tip 1 from people who interviewed",
            "Tip 2"
        ],
        "what_they_look_for": [
            "Problem-solving approach",
            "Communication during coding"
        ],
        "resources": [
            {{
                "name": "Glassdoor Interview Reviews",
                "url": "https://glassdoor.com/Interview/{company.replace(' ', '-')}-Interview-Questions"
            }},
            {{
                "name": "LeetCode Company Tag",
                "url": "https://leetcode.com/company/{company.lower().replace(' ', '-')}/"
            }}
        ],
        "sources": ["Source 1", "Source 2"]
    }}
    """

	try:
		parsed = get_llm(temperature=0.5).generate_json(
			prompt=prompt,
			system_prompt='You are an interview coach with knowledge of tech company hiring.',
			agent_name='company_agent',
		)

		if 'error' in parsed:
			raise Exception(parsed['error'])

		console.success('Interview insights ready')
		slog.agent('company_agent', 'interview_insights_complete', company=company)
		return parsed

	except Exception as e:
		console.error(f'Failed to get insights: {e}')
		slog.agent_error('company_agent', 'interview_insights_failed', company=company, error=str(e))
		return AgentResponse.create_error(str(e)).model_dump()


# ============================================
# Company Agent System Prompt
# ============================================

COMPANY_AGENT_SYSTEM_PROMPT = """You are an expert company research analyst helping job candidates prepare for interviews.

## Your Capabilities

### `search_company_info`
Get company overview: industry, size, mission, tech stack, products, competitors.

### `analyze_company_culture`
Analyze work culture: work-life balance, growth, management style, pros/cons.

### `identify_red_flags`
Check for warning signs in the company or job posting.

### `get_interview_insights`
Get specific interview tips, common questions, and what they look for.

## Workflow

1. **Research** - Get basic company information
2. **Culture** - Analyze work culture and fit
3. **Red Flags** - Identify concerns to investigate
4. **Interview Tips** - Provide specific interview insights

## Guidelines

- Be balanced and fair - mention both pros and cons
- Provide actionable insights, not just generic advice
- Always include questions the candidate should ask
- Flag serious concerns clearly but don't be alarmist
"""


class CompanyAgent(BaseAgent):
	"""
	DeepAgent-based Company Research Agent.

	Researches companies, analyzes culture, identifies red flags,
	and provides interview-specific insights.
	"""

	def __init__(self):
		super().__init__()
		self.llm = get_llm(temperature=0.4)

	async def run(self, *args, **kwargs) -> AgentResponse:
		"""Required abstract method."""
		company = kwargs.get('company', '')
		role = kwargs.get('role', '')

		if not company:
			return AgentResponse.create_error('company name is required')

		try:
			data = await self.research_company(company, role)
			return AgentResponse.create_success(data=data, company_name=company)
		except Exception as e:
			return AgentResponse.create_error(str(e), company_name=company)

	async def research_company(self, company: str, role: str = '', job_description: str = '') -> Dict:
		"""
		Comprehensive company research.

		Args:
		    company: Company name
		    role: Target role
		    job_description: Optional job posting text

		Returns:
		    Complete research report
		"""
		console.subheader(f'🏢 Researching {company}')
		console.info('Gathering company intelligence...')

		# Get all information
		info = search_company_info(company, role)
		culture = analyze_company_culture(company, role)
		red_flags = identify_red_flags(company, job_description)
		insights = get_interview_insights(company, role)

		return {
			'success': True,
			'company': company,
			'role': role,
			'company_info': info,
			'culture_analysis': culture,
			'red_flags': red_flags,
			'interview_insights': insights,
		}

	async def quick_check(self, company: str) -> Dict:
		"""Quick company overview without full analysis."""
		console.subheader(f'🏢 Quick Check: {company}')

		info = search_company_info(company)
		red_flags = identify_red_flags(company)

		return {
			'success': True,
			'company': company,
			'overview': info,
			'risk_level': red_flags.get('overall_risk_level', 'unknown'),
			'key_concerns': red_flags.get('company_red_flags', [])[:3],
		}

	def generate_report(self, data: Dict) -> str:
		"""Generate comprehensive Markdown research report."""
		company = data.get('company', 'Unknown Company')
		info = data.get('company_info', {})
		culture = data.get('culture_analysis', {})
		flags = data.get('red_flags', {})
		insights = data.get('interview_insights', {})

		report = [
			f'# 🏢 Company Research Report: {company}',
			f'**Date:** {date.today().isoformat()}',
			'',
			'## 1. Executive Summary',
			f'- **Industry:** {info.get("industry", "N/A")}',
			f'- **Size:** {info.get("size", "N/A")} ({info.get("employee_count", "N/A")} employees)',
			f'- **Headquarters:** {info.get("headquarters", "N/A")}',
			f'- **Risk Level:** {flags.get("overall_risk_level", "Unknown").upper()}',
			'',
			'## 2. Company Overview',
			f'**Mission:** {info.get("mission", "N/A")}',
			'',
			'### Products & Services',
			*[f'- {p}' for p in info.get('products', [])],
			'',
			'### Tech Stack',
			*[f'- {t}' for t in info.get('tech_stack', [])],
			'',
			'### Recent News',
			*[f'- {n}' for n in info.get('recent_news', [])],
			'',
			f'**Sources:** {", ".join(info.get("sources", []))}',
			'',
			'## 3. Culture & Values',
			f'**Type:** {culture.get("culture_type", "N/A")}',
			f'**Work-Life Balance:** {culture.get("work_life_balance", {}).get("rating", "N/A")} - {culture.get("work_life_balance", {}).get("notes", "")}',
			'',
			'### Pros',
			*[f'- {p}' for p in culture.get('pros', [])],
			'',
			'### Cons',
			*[f'- {c}' for c in culture.get('cons', [])],
			'',
			f'**Sources:** {", ".join(culture.get("sources", []))}',
			'',
			'## 4. Risk Assessment (Red Flags)',
			f'**Recommendation:** {flags.get("recommendation", "N/A")}',
			'',
			'### Key Concerns',
			*[
				f'- **{f.get("flag")}** ({f.get("severity")}): {f.get("how_to_verify")}'
				for f in flags.get('company_red_flags', [])
			],
			'',
			f'**Sources:** {", ".join(flags.get("sources", []))}',
			'',
			'## 5. Interview Intelligence',
			f'**Process:** {insights.get("interview_process", {}).get("duration", "N/A")} - {insights.get("interview_process", {}).get("difficulty", "N/A")}',
			'',
			'### Tips',
			*[f'- {t}' for t in insights.get('tips_from_candidates', [])],
			'',
			'### Questions to Ask',
			*[f'- {q}' for q in info.get('questions_to_ask', [])],
			'',
			f'**Sources:** {", ".join(insights.get("sources", []))}',
		]

		return '\n'.join(report)


# Lazy singleton instance
_company_agent = None


def get_company_agent() -> CompanyAgent:
	"""Get or create the CompanyAgent singleton."""
	global _company_agent
	if _company_agent is None:
		_company_agent = CompanyAgent()
	return _company_agent


# For backwards compatibility
company_agent = None  # Use get_company_agent() instead
