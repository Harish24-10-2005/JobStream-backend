import asyncio
from typing import List, Optional, Set
from urllib.parse import urlparse

import requests
from langchain_community.utilities import SerpAPIWrapper
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from src.automators.base import BaseAgent
from src.core.console import console


# ============================================
# Pydantic Schemas for Strict Output Parsing
# ============================================
class ScrapedJob(BaseModel):
	url: str
	source_domain: str
	title: Optional[str] = None
	company: Optional[str] = None
	status: str = Field(default='discovered', description='Current status: discovered, applied, failed, skipped')
	query_matched: str = Field(default='', description='The query that found this job')


class ScoutAgent(BaseAgent):
	"""
	Agent responsible for finding job listings.
	"""

	def __init__(self):
		super().__init__()
		# Initialize SerpAPI with key from secure settings
		key = self.settings.serpapi_api_key.get_secret_value()
		if not key:
			self.logger.error('ScoutAgent: SERPAPI_API_KEY is missing or empty!')
			raise ValueError('SERPAPI_API_KEY is required for ScoutAgent')

		self.logger.debug(f'ScoutAgent: Initializing SerpAPI with key length {len(key)}')

		self.search = SerpAPIWrapper(
			serpapi_api_key=key, params={'engine': 'google', 'google_domain': 'google.com', 'gl': 'us', 'hl': 'en', 'num': 20}
		)
		# Initialize LLM for Reflection/Self-Correction
		self.llm = ChatGroq(
			model='llama-3.3-70b-versatile', temperature=0.2, api_key=self.settings.groq_api_key.get_secret_value()
		)

		self.ats_domains = ['site:greenhouse.io', 'site:lever.co', 'site:ashbyhq.com']
		self.valid_domains = ['greenhouse.io', 'lever.co', 'ashbyhq.com']

	async def run(
		self, query: str, location: str = '', freshness: str = 'month', attempt: int = 1, webhook_url: Optional[str] = None
	) -> List[ScrapedJob]:
		"""
		Searches for jobs targeting ATS domains.
		freshness: 'day' | 'week' | 'month' | None
		attempt: current retry attempt (max 2)
		webhook_url: optional URL to POST results to instantly
		"""
		# Map freshness to Google Time-Based Search (tbs) params
		tbs_map = {'day': 'qdr:d', 'week': 'qdr:w', 'month': 'qdr:m', 'year': 'qdr:y'}
		tbs_param = tbs_map.get(freshness, 'qdr:m')  # Default to past month if invalid

		full_query = f'{query} {location}'.strip()
		target_query = f'{full_query} ({" OR ".join(self.ats_domains)})'

		# update params for this run
		self.search.params['tbs'] = tbs_param

		# Rich console output
		console.scout_header()
		self.logger.info(f"🔎 ScoutAgent: Searching for '{full_query}' ({freshness} fresh) [Attempt {attempt}]...")

		try:
			# Synchronous call to SerpAPI (wrapped if needed, but simple enough here)
			raw_results = self.search.results(target_query)
			organic_results = raw_results.get('organic_results', [])

			if not organic_results:
				self.logger.warning('Search returned no results.')
				if attempt < 2:
					return await self._reflect_and_retry(query, location, freshness, attempt, webhook_url)

				console.scout_results(query, location, [])
				return []

			valid_jobs_data = self._filter_results(organic_results)

			if not valid_jobs_data and attempt < 2:
				self.logger.warning('No VALID ATS links found. Retrying...')
				return await self._reflect_and_retry(query, location, freshness, attempt, webhook_url)

			# Convert valid jobs data to ScrapedJob objects
			jobs = [
				ScrapedJob(
					url=data['link'],
					title=data.get('title'),
					company=data.get('company'),
					source_domain=next((domain for domain in self.valid_domains if domain in data['link']), 'unknown'),
					query_matched=full_query,
				)
				for data in valid_jobs_data
			]

			# Display rich formatted results
			console.scout_results(query, location, [j.url for j in jobs])

			# Webhook Integration
			if webhook_url and jobs:
				try:
					payload = {'query': full_query, 'jobs': [j.model_dump() for j in jobs]}

					def send_webhook():
						response = requests.post(webhook_url, json=payload, timeout=5)
						response.raise_for_status()

					await asyncio.to_thread(send_webhook)
					self.logger.info(f'✅ Webhook sent successfully to {webhook_url}')
				except Exception as e:
					self.logger.error(f'Failed to send webhook: {e}')

			return jobs

		except Exception as e:
			self.logger.error(f'ScoutAgent Error: {str(e)}')
			console.error(f'Search failed: {str(e)}')
			return []

	async def _reflect_and_retry(
		self, query: str, location: str, freshness: str, attempt: int, webhook_url: Optional[str] = None
	) -> List[ScrapedJob]:
		"""
		Self-Correction: Analyze why the search failed and generate a better query.
		"""
		console.warning('🤔 ScoutAgent: 0 results found. Reflecting on strategy...')

		prompt = f"""
        You are a Google Search Expert for Recruitment.
        The user searched for: '{query} {location}' (Time filter: {freshness})
        
        Result: 0 valid job listings found on ATS (Greenhouse/Lever/Ashby).
        
        Reasoning: The query might be too specific (long tail keywords), have typos, or conflict with location filters.
        
        Task: Generate a BROADER, more likely to succeed search query.
        - Remove specific seniority levels if they are niche (e.g. "Senior Staff Principal" -> "Senior")
        - Remove conflicting terms.
        - Keep the essential skill/role.
        
        OUTPUT ONLY THE RAW QUERY STRING. NO EXPLANATION.
        """

		try:
			messages = [
				SystemMessage(content='You are a search query optimizer. Output ONLY the query string.'),
				HumanMessage(content=prompt),
			]
			response = self.llm.invoke(messages)
			new_query = response.content.strip().replace('"', '')

			console.info(f"💡 ScoutAgent Idea: Retrying with '{new_query}'")

			# Recursive retry with new query
			return await self.run(new_query, '', freshness, attempt + 1, webhook_url)

		except Exception as e:
			self.logger.error(f'Reflection Failed: {e}')
			return []

	def _filter_results(self, results: List[dict]) -> List[dict]:
		valid_jobs = []
		seen: Set[str] = set()
		non_job_paths = {'', '/', '/pricing', '/about', '/blog', '/docs', '/security'}

		for r in results:
			link = r.get('link', '').strip()
			if not link or link in seen:
				continue

			if any(domain in link for domain in self.valid_domains):
				parsed = urlparse(link)
				host = (parsed.netloc or '').lower()
				path = (parsed.path or '').lower()
				if host.startswith('status.'):
					continue
				if path in non_job_paths:
					continue
				# Accept canonical ATS job URLs on host-specific patterns.
				is_greenhouse_job = ('greenhouse' in host and '/jobs' in path) or (
					'boards.greenhouse.io' in host and path not in {'', '/'}
				)
				is_lever_job = ('lever.co' in host and '/jobs' in path) or ('jobs.lever.co' in host and path not in {'', '/'})
				is_ashby_job = ('ashbyhq.com' in host and '/jobs' in path) or (
					'jobs.ashbyhq.com' in host and path not in {'', '/'}
				)
				if not (is_greenhouse_job or is_lever_job or is_ashby_job):
					continue
				
				# Try to extract company from path
				company = 'Unknown'
				path_parts = [p for p in path.split('/') if p]
				if 'greenhouse.io' in host and len(path_parts) > 0:
					company = path_parts[0]
				elif 'lever.co' in host and len(path_parts) > 0:
					company = path_parts[0]
				elif 'ashbyhq.com' in host and len(path_parts) > 0:
					company = path_parts[0]
				
				# Format company name
				if company != 'Unknown':
					company = company.replace('-', ' ').title()

				# Parse title
				raw_title = r.get('title', 'Untitled')
				title = raw_title.split(' - ')[0].split(' at ')[0].split('|')[0].strip()

				valid_jobs.append({
					'link': link,
					'title': title,
					'company': company
				})
				seen.add(link)

		self.logger.info(f'✅ ScoutAgent: Found {len(valid_jobs)} valid jobs.')
		return valid_jobs
