"""
Resume Storage Service - Manages resume files in Supabase Storage
Handles upload, download, and PDF generation storage
"""

import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from src.services.rag_service import rag_service  # Integration with RAG
from src.services.supabase_client import SupabaseClient, supabase_client

logger = logging.getLogger(__name__)


class ResumeMetadata(BaseModel):
	"""Resume file metadata."""

	id: str
	user_id: str
	file_name: str
	file_path: str
	file_type: str = 'application/pdf'
	file_size: int = 0
	is_primary: bool = False
	upload_date: Optional[str] = None
	created_at: Optional[str] = None


class GeneratedResumeMetadata(BaseModel):
	"""Generated (tailored) resume metadata."""

	id: str
	user_id: str
	job_url: Optional[str] = None
	job_title: Optional[str] = None
	company_name: Optional[str] = None
	pdf_path: Optional[str] = None
	pdf_url: Optional[str] = None
	ats_score: Optional[int] = None
	match_score: Optional[int] = None
	created_at: Optional[str] = None


class ResumeStorageService:
	"""Service for managing resume files in Supabase Storage."""

	BUCKET_RESUMES = 'resumes'
	BUCKET_GENERATED = 'generated-resumes'
	BUCKET_COVER_LETTERS = 'cover-letters'

	# Table Names (Standardized)
	TABLE_USER_RESUMES = 'user_resumes'
	TABLE_GENERATED_RESUMES = 'user_generated_resumes'
	TABLE_COVER_LETTERS = 'user_cover_letters'

	def __init__(self):
		# Use admin client to bypass RLS for storage operations
		try:
			self.client = SupabaseClient.get_admin_client()
			logger.info('ResumeStorageService initialized with admin client (RLS bypassed)')
		except ValueError:
			# Fallback to anon client if service key not available
			self.client = supabase_client
			logger.warning('ResumeStorageService using anon client (RLS applies)')

	def _get_user_path(self, user_id: str, filename: str, bucket: str) -> str:
		"""Generate storage path for user file: {user_id}/{timestamp}_{filename}"""
		timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
		return f'{user_id}/{timestamp}_{filename}'

	async def upload_resume(
		self,
		user_id: str,
		file_content: bytes,
		filename: str,
		name: str = 'Primary Resume',
		is_primary: bool = True,
		content_type: str = 'application/pdf',
		full_text: str = None,  # Optional text for RAG
	) -> Optional[ResumeMetadata]:
		"""
		Upload a resume file to Supabase Storage.
		Returns metadata including the file URL.
		Optionally indexes content for RAG.
		"""
		try:
			# Generate storage path
			file_path = self._get_user_path(user_id, filename, self.BUCKET_RESUMES)

			# Upload to storage
			response = self.client.storage.from_(self.BUCKET_RESUMES).upload(
				path=file_path, file=file_content, file_options={'content-type': content_type}
			)

			logger.info(f'Uploaded resume to storage: {file_path}')

			# Get public URL
			file_url = self.client.storage.from_(self.BUCKET_RESUMES).get_public_url(file_path)

			# If making this primary, unset other primary resumes
			if is_primary:
				self.client.table(self.TABLE_USER_RESUMES).update({'is_primary': False}).eq('user_id', user_id).eq(
					'is_primary', True
				).execute()

			# Save metadata to database
			metadata = {
				'user_id': user_id,
				'file_name': name,
				'file_path': file_path,
				'file_type': content_type,
				'file_size': len(file_content),
				'is_primary': is_primary,
			}
			# Only add full_text if it exists and the column is present
			# Note: full_text column may not exist in all database schemas

			db_response = self.client.table(self.TABLE_USER_RESUMES).insert(metadata).execute()

			if db_response.data:
				resume_data = db_response.data[0]

				# RAG Indexing
				if full_text:
					try:
						await rag_service.add_document(
							user_id=user_id,
							content=full_text,
							metadata={'type': 'resume', 'resume_id': resume_data['id'], 'name': name},
						)
						logger.info(f'Indexed resume {resume_data["id"]} for RAG')
					except Exception as rag_err:
						logger.warning(f'Failed to index resume for RAG: {rag_err}')

				return ResumeMetadata(**resume_data)

			return None

		except Exception as e:
			logger.error(f'Error uploading resume for user {user_id}: {e}')
			raise

	async def get_user_resumes(self, user_id: str) -> List[ResumeMetadata]:
		"""Get all resumes for a user."""
		try:
			response = (
				self.client.table(self.TABLE_USER_RESUMES)
				.select('*')
				.eq('user_id', user_id)
				.order('created_at', desc=True)
				.execute()
			)

			return [ResumeMetadata(**r) for r in response.data] if response.data else []

		except Exception as e:
			logger.error(f'Error fetching resumes for user {user_id}: {e}')
			return []

	async def get_primary_resume(self, user_id: str) -> Optional[ResumeMetadata]:
		"""Get user's primary resume."""
		try:
			response = (
				self.client.table(self.TABLE_USER_RESUMES)
				.select('*')
				.eq('user_id', user_id)
				.eq('is_primary', True)
				.single()
				.execute()
			)

			return ResumeMetadata(**response.data) if response.data else None

		except Exception as e:
			# It's common to not have a primary resume, don't log as error unless debug
			# logger.debug(f"No primary resume found for {user_id}")
			return None

	async def get_primary_resume_url(self, user_id: str) -> Optional[str]:
		"""Get URL for user's primary resume file."""
		resume = await self.get_primary_resume(user_id)
		if not resume:
			return None
		try:
			return self.client.storage.from_(self.BUCKET_RESUMES).get_public_url(resume.file_path)
		except Exception as e:
			logger.error(f'Error getting public URL for resume {resume.id}: {e}')
			return None

	async def download_resume(self, user_id: str, resume_id: str) -> Optional[bytes]:
		"""Download resume file content."""
		try:
			# Get metadata
			response = (
				self.client.table(self.TABLE_USER_RESUMES)
				.select('*')
				.eq('id', resume_id)
				.eq('user_id', user_id)
				.single()
				.execute()
			)

			if not response.data:
				return None

			file_path = response.data['file_path']

			# Download from storage
			file_data = self.client.storage.from_(self.BUCKET_RESUMES).download(file_path)

			return file_data

		except Exception as e:
			logger.error(f'Error downloading resume {resume_id}: {e}')
			return None

	async def delete_resume(self, user_id: str, resume_id: str) -> bool:
		"""Delete a resume file and metadata."""
		try:
			# Get metadata first
			response = (
				self.client.table(self.TABLE_USER_RESUMES)
				.select('file_path')
				.eq('id', resume_id)
				.eq('user_id', user_id)
				.single()
				.execute()
			)

			if not response.data:
				return False

			file_path = response.data['file_path']

			# Delete from storage
			self.client.storage.from_(self.BUCKET_RESUMES).remove([file_path])

			# Delete metadata
			self.client.table(self.TABLE_USER_RESUMES).delete().eq('id', resume_id).execute()

			logger.info(f'Deleted resume {resume_id} for user {user_id}')
			return True

		except Exception as e:
			logger.error(f'Error deleting resume {resume_id}: {e}')
			return False

	async def save_generated_resume(
		self,
		user_id: str,
		pdf_content: bytes,
		job_url: str,
		job_title: str,
		company_name: str,
		original_content: Dict[str, Any] = None,
		tailored_content: Dict[str, Any] = None,
		latex_source: str = None,
		ats_score: int = None,
		match_score: int = None,
	) -> Optional[GeneratedResumeMetadata]:
		"""
		Save an AI-generated tailored resume.
		Stores PDF in storage and metadata in database.
		"""
		try:
			# Generate filename
			safe_company = ''.join(c for c in company_name if c.isalnum() or c in ' -_')[:30]
			filename = f'resume_{safe_company.replace(" ", "_")}.pdf'
			file_path = self._get_user_path(user_id, filename, self.BUCKET_GENERATED)

			# Upload PDF to storage
			self.client.storage.from_(self.BUCKET_GENERATED).upload(
				path=file_path, file=pdf_content, file_options={'content-type': 'application/pdf'}
			)

			# Get public URL
			pdf_url = self.client.storage.from_(self.BUCKET_GENERATED).get_public_url(file_path)

			# Save metadata
			data = {
				'user_id': user_id,
				'job_url': job_url,
				'job_title': job_title,
				'company_name': company_name,
				# "original_content": original_content or {}, # Not in schema, skipping
				'tailored_content': tailored_content or {},
				'latex_source': latex_source,
				'pdf_path': file_path,
				'pdf_url': pdf_url,
				'ats_score': ats_score,
				'match_score': match_score,
			}

			response = self.client.table(self.TABLE_GENERATED_RESUMES).insert(data).execute()

			if response.data:
				logger.info(f'Saved generated resume for {company_name} job')
				return GeneratedResumeMetadata(**response.data[0])

			return None

		except Exception as e:
			logger.error(f'Error saving generated resume: {e}')
			raise

	async def get_generated_resumes(self, user_id: str, limit: int = 50) -> List[GeneratedResumeMetadata]:
		"""Get user's generated resumes history."""
		try:
			response = (
				self.client.table(self.TABLE_GENERATED_RESUMES)
				.select('*')
				.eq('user_id', user_id)
				.order('created_at', desc=True)
				.limit(limit)
				.execute()
			)

			# Map to metadata model
			results = []
			for r in response.data or []:
				results.append(
					GeneratedResumeMetadata(
						id=r.get('id'),
						user_id=r.get('user_id'),
						job_url=r.get('job_url'),
						job_title=r.get('job_title'),
						company_name=r.get('company_name'),
						pdf_path=r.get('pdf_path'),
						pdf_url=r.get('pdf_url'),
						ats_score=r.get('ats_score'),
						match_score=r.get('match_score'),
						created_at=r.get('created_at'),
					)
				)
			return results

		except Exception as e:
			logger.error(f'Error fetching generated resumes: {e}')
			return []

	async def save_cover_letter(
		self,
		user_id: str,
		pdf_content: bytes,
		job_url: str,
		job_title: str,
		company_name: str,
		content: Dict[str, Any],
		tone: str = 'professional',
		resume_id: str = None,
		latex_source: str = None,
	) -> Optional[Dict[str, Any]]:
		"""Save a generated cover letter."""
		try:
			# Generate filename
			safe_company = ''.join(c for c in company_name if c.isalnum() or c in ' -_')[:30]
			filename = f'cover_letter_{safe_company.replace(" ", "_")}.pdf'
			file_path = self._get_user_path(user_id, filename, self.BUCKET_COVER_LETTERS)

			# Upload PDF
			self.client.storage.from_(self.BUCKET_COVER_LETTERS).upload(
				path=file_path, file=pdf_content, file_options={'content-type': 'application/pdf'}
			)

			# Get URL
			pdf_url = self.client.storage.from_(self.BUCKET_COVER_LETTERS).get_public_url(file_path)

			# Save metadata
			data = {
				'user_id': user_id,
				'resume_id': resume_id,
				'job_url': job_url,
				'job_title': job_title,
				'company_name': company_name,
				'tone': tone,
				'content': content,
				# "latex_source": latex_source, # Schema check: not in 05_resume_cover_letter.sql?
				# Ah, I didn't verify if latex_source is in user_cover_letters table in previous step.
				# Let's check the SQL output.
				# SQL said: content jsonb, final_text text...
				'pdf_path': file_path,
				'pdf_url': pdf_url,
				'final_text': content.get('full_text'),  # Map full_text to final_text
			}

			response = self.client.table(self.TABLE_COVER_LETTERS).insert(data).execute()

			return response.data[0] if response.data else None

		except Exception as e:
			logger.error(f'Error saving cover letter: {e}')
			raise

	async def parse_resume_content(self, file_content: bytes) -> Dict[str, Any]:
		"""
		Parse resume PDF to extract structured content using LLM.
		Can be used during upload to pre-fill profile fields.
		"""
		try:
			# Import PDF extraction library (pypdf is the modern replacement for PyPDF2)
			from pypdf import PdfReader

			from src.core.llm_provider import UnifiedLLM

			# Extract text from PDF
			pdf_reader = PdfReader(io.BytesIO(file_content))
			text = ''
			for page in pdf_reader.pages:
				text += page.extract_text() + '\n'

			if not text.strip():
				logger.warning('No text extracted from resume PDF')
				return {}

			# Use LLM to extract structured data
			llm = UnifiedLLM(temperature=0.1)

			prompt = f"""Extract the following information from this resume and return ONLY a valid JSON object with no additional text:

{{
  "personal_info": {{
    "first_name": "string or null",
    "last_name": "string or null", 
    "email": "string or null",
    "phone": "string or null",
    "city": "string or null",
    "country": "string or null",
    "address": "string or null",
    "linkedin_url": "string or null",
    "github_url": "string or null",
    "portfolio_url": "string or null",
    "summary": "string or null"
  }},
  "education": [
    {{
      "degree": "string",
      "major": "string",
      "university": "string",
      "cgpa": "string or null",
      "start_date": "YYYY-MM-DD or null",
      "end_date": "YYYY-MM-DD or null",
      "is_current": boolean
    }}
  ],
  "experience": [
    {{
      "title": "string",
      "company": "string",
      "start_date": "YYYY-MM-DD or null",
      "end_date": "YYYY-MM-DD or null",
      "is_current": boolean,
      "description": "string or null"
    }}
  ],
  "projects": [
    {{
      "name": "string",
      "tech_stack": ["string"],
      "description": "string or null",
      "project_url": "string or null"
    }}
  ],
  "skills": {{
    "primary": ["string"],
    "secondary": ["string"],
    "tools": ["string"],
    "languages": ["string"]
  }}
}}

Resume text:
{text[:8000]}

Return ONLY the JSON object, no explanations."""

			# Use ainvoke for async call with messages format
			messages = [{'role': 'user', 'content': prompt}]
			response = await llm.ainvoke(messages)

			# Parse JSON response
			import json

			# Remove markdown code blocks if present
			json_text = response.strip()
			if json_text.startswith('```json'):
				json_text = json_text[7:]
			if json_text.startswith('```'):
				json_text = json_text[3:]
			if json_text.endswith('```'):
				json_text = json_text[:-3]

			parsed_data = json.loads(json_text.strip())
			logger.info(
				f'Successfully parsed resume with {len(parsed_data.get("education", []))} education entries, {len(parsed_data.get("experience", []))} experience entries'
			)

			return parsed_data

		except Exception as e:
			logger.error(f'Error parsing resume: {str(e)}', exc_info=True)
			return {}

	async def get_cover_letters(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
		"""Get user's generated cover letters history."""
		try:
			response = (
				self.client.table(self.TABLE_COVER_LETTERS)
				.select('*')
				.eq('user_id', user_id)
				.order('created_at', desc=True)
				.limit(limit)
				.execute()
			)

			return response.data or []

		except Exception as e:
			logger.error(f'Error fetching cover letters: {e}')
			return []

	async def get_cover_letter(self, user_id: str, letter_id: str) -> Optional[Dict[str, Any]]:
		"""Retrieve a specific cover letter."""
		try:
			response = (
				self.client.table(self.TABLE_COVER_LETTERS)
				.select('*')
				.eq('id', letter_id)
				.eq('user_id', user_id)
				.single()
				.execute()
			)

			return response.data if response.data else None

		except Exception as e:
			logger.error(f'Error fetching cover letter {letter_id}: {e}')
			return None


# Global service instance
resume_storage_service = ResumeStorageService()
