"""
Supabase Client - Singleton connection to Supabase
"""

import logging

from supabase import Client, create_client

from src.core.config import settings

logger = logging.getLogger(__name__)

from src.core import db_tables



class SupabaseClient:
	"""Singleton Supabase client for database operations."""

	_instance: Client = None

	@classmethod
	def get_client(cls) -> Client:
		"""Get or create Supabase client instance."""
		if cls._instance is None:
			if not settings.supabase_url or not settings.supabase_anon_key:
				raise RuntimeError('Supabase not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY in .env')
			if settings.supabase_service_key:
				cls._instance = create_client(settings.supabase_url, settings.supabase_service_key.get_secret_value())
				logger.info('Supabase client initialized with service role key')
			else:
				cls._instance = create_client(settings.supabase_url, settings.supabase_anon_key)
				logger.warning('Supabase client initialized with anon key (service key missing)')
		return cls._instance

	@classmethod
	def get_admin_client(cls) -> Client:
		"""Get admin client with service role key (for bypassing RLS)."""
		if settings.supabase_service_key:
			return create_client(settings.supabase_url, settings.supabase_service_key.get_secret_value())
		raise ValueError('Service key not configured. Set SUPABASE_SERVICE_KEY in .env')


def _get_supabase_client() -> Client:
	"""Lazy-initialize and return the Supabase client singleton."""
	return SupabaseClient.get_client()


# Lazy proxy - avoids crash at import time if env vars are missing
class _LazySupabaseClient:
	"""Proxy that defers Supabase initialization until first attribute access."""

	def __getattr__(self, name):
		client = _get_supabase_client()
		return getattr(client, name)


supabase_client = _LazySupabaseClient()


# Database helper functions
async def get_resume_templates():
	"""Fetch all resume templates."""
	response = supabase_client.table('resume_templates').select('*').execute()
	return response.data


async def get_default_template():
	"""Fetch the default ATS template."""
	response = supabase_client.table('resume_templates').select('*').eq('is_default', True).single().execute()
	return response.data


async def save_generated_resume(
	user_id: str,
	job_url: str,
	job_title: str,
	company_name: str,
	original_content: dict,
	tailored_content: dict,
	latex_source: str = None,
	pdf_url: str = None,
	ats_score: int = None,
):
	"""Save a generated resume to the database."""
	data = {
		'user_id': user_id,
		'job_url': job_url,
		'job_title': job_title,
		'company_name': company_name,
		'original_content': original_content,
		'tailored_content': tailored_content,
		'latex_source': latex_source,
		'pdf_url': pdf_url,
		'ats_score': ats_score,
	}
	# Save to user_generated_resumes which has the correct schema for content
	response = supabase_client.table(db_tables.GENERATED_RESUMES).insert(data).execute()
	return response.data[0] if response.data else None


async def save_cover_letter(
	user_id: str,
	job_url: str,
	job_title: str,
	company_name: str,
	content: dict,
	tone: str = 'professional',
	resume_id: str = None,
	latex_source: str = None,
	pdf_url: str = None,
):
	"""Save a generated cover letter to the database."""
	data = {
		'user_id': user_id,
		'content': content.get('text', '') if isinstance(content, dict) else str(content),
		'version': 1,
		'metadata': {
			'resume_id': resume_id,
			'job_url': job_url,
			'job_title': job_title,
			'company_name': company_name,
			'tone': tone,
			'latex_source': latex_source,
			'pdf_url': pdf_url,
		},
	}
	response = supabase_client.table('cover_letters').insert(data).execute()
	return response.data[0] if response.data else None


async def save_job_search(user_id: str, query: str, location: str, platforms: list = None):
	"""Save a job search to track history."""
	data = {'user_id': user_id, 'query': query, 'location': location, 'platforms': platforms or ['greenhouse', 'lever', 'ashby']}
	response = supabase_client.table('job_searches').insert(data).execute()
	return response.data[0] if response.data else None


async def save_discovered_job(user_id: str, url: str, title: str = '', company: str = '', location: str = '', source: str = 'scout'):
	"""Save a discovered job."""
	data = {
		'user_id': user_id,
		'url': url,
		'title': title or 'Unknown',
		'company': company or 'Unknown',
		'location': location or 'Remote',
		'source': source,
	}
	response = supabase_client.table('discovered_jobs').insert(data).execute()
	return response.data[0] if response.data else None


async def save_job_analysis(
	job_id: str,
	user_profile_id: str,
	role: str,
	company: str,
	match_score: int,
	tech_stack: list = None,
	matching_skills: list = None,
	missing_skills: list = None,
	reasoning: str = None,
	salary_range: str = None,
):
	"""Save job analysis results."""
	# user_profile_id and salary_range are missing in DB schema, removing them from payload
	data = {
		'job_id': job_id,
		'role': role,
		'company': company,
		'tech_stack': tech_stack,
		'matching_skills': matching_skills,
		'missing_skills': missing_skills,
		'match_score': match_score,
		'reasoning': reasoning,
	}
	response = supabase_client.table(db_tables.JOB_ANALYSES).insert(data).execute()
	return response.data[0] if response.data else None


async def save_application(
	user_id: str,
	job_id: str,
	resume_id: str = None,
	cover_letter_id: str = None,
	status: str = 'pending',
	platform: str = None,
):
	"""Save an application record."""
	data = {
		'user_id': user_id,
		'job_id': job_id,
		'status': status,
	}
	if resume_id:
		data['resume_id'] = resume_id
	if cover_letter_id:
		data['cover_letter_id'] = cover_letter_id
	# 'platform' column is missing from applications table, skipping for now
	response = supabase_client.table(db_tables.APPLICATIONS).insert(data).execute()
	return response.data[0] if response.data else None


async def update_application_status(application_id: str, status: str, error: str = None):
	"""Update application status."""
	data = {'status': status}
	if status == 'applied':
		data['applied_date'] = 'now()'  # Fix: applied_at -> applied_date
	if error:
		data['timeline'] = {'last_error': error}  # Fix: application_metadata -> timeline

	response = supabase_client.table(db_tables.APPLICATIONS).update(data).eq('id', application_id).execute()
	return response.data[0] if response.data else None
