"""
User Profile Service - Multi-tenant profile management via Supabase
Replaces hardcoded user_profile.yaml with database-backed profiles
"""

import logging
from typing import Any, Dict, Optional

from pydantic import BaseModel

from src.core.cache import cache
from src.models.profile import (
	ApplicationPreferences,
	Education,
	Experience,
	Files,
	Location,
	PersonalInfo,
	Project,
	Urls,
	UserProfile,
)
from src.core import db_tables
from src.services.rag_service import rag_service
from src.services.supabase_client import SupabaseClient, supabase_client

logger = logging.getLogger(__name__)


class UserProfileDB(BaseModel):
	"""Database representation of user profile - based on actual Supabase schema."""

	id: Optional[str] = None
	user_id: str
	first_name: str
	last_name: str
	email: str
	phone: Optional[str] = None
	linkedin_url: Optional[str] = None
	github_url: Optional[str] = None
	portfolio_url: Optional[str] = None


class UserProfileService:
	"""Service for managing user profiles in Supabase."""

	def __init__(self):
		# Use admin client (service role key) to bypass RLS for profile operations
		try:
			self.client = SupabaseClient.get_admin_client()
			logger.info('UserProfileService initialized with admin client (RLS bypassed)')
		except ValueError:
			# Fallback to anon client if service key not available
			self.client = supabase_client
			logger.warning('Service key not configured, using anon client (RLS enforced)')

	async def get_profile_cache_key(self, user_id: str) -> str:
		return f'user:profile:{user_id}'

	async def get_profile(self, user_id: str) -> Optional[UserProfile]:
		"""
		Fetch complete user profile from Supabase.
		Returns UserProfile model compatible with existing agents.
		"""
		try:
			# Check cache first
			cache_key = await self.get_profile_cache_key(user_id)
			cached_profile = await cache.get_model(cache_key, UserProfile)

			if cached_profile:
				logger.debug(f'Returning cached profile for user {user_id}')
				return cached_profile

			# Fetch profile data - use maybe_single() to avoid error when no rows
			profile_data = self.client.table(db_tables.PROFILES).select('*').eq('user_id', user_id).maybe_single().execute()

			if not profile_data.data:
				logger.debug(f'No profile found for user {user_id}')
				return None

			p = profile_data.data

			# Get education, experience, projects from JSONB fields in user_profiles
			education_list = p.get('education', []) or []
			experience_list = p.get('experience', []) or []
			projects_list = p.get('projects', []) or []
			personal_info = p.get('personal_info', {}) or {}

			# Fetch primary resume (non-fatal if table missing or query fails)
			resume_resp = None
			primary_resume = None
			try:
				resume_resp = (
					self.client.table(db_tables.RESUMES)
					.select('*')
					.eq('user_id', user_id)
					.eq('is_primary', True)
					.limit(1)
					.execute()
				)
				if resume_resp and resume_resp.data:
					primary_resume = resume_resp.data[0]
			except Exception as resume_err:
				logger.warning(f'Could not fetch primary resume for user {user_id}: {resume_err}')

			# Build UserProfile model
			profile = UserProfile(
				id=p.get('id'),
				user_id=user_id,
				personal_information=PersonalInfo(
					first_name=p.get('first_name', '') or personal_info.get('first_name', ''),
					last_name=p.get('last_name', '') or personal_info.get('last_name', ''),
					full_name=f'{p.get("first_name", "")} {p.get("last_name", "")}',
					email=p.get('email', '') or personal_info.get('email', ''),
					phone=p.get('phone', '') or personal_info.get('phone', ''),
					location=Location(city=personal_info.get('location', '') or '', country='', address=''),
					urls=Urls(
						linkedin=p.get('linkedin_url') or personal_info.get('linkedin_url'),
						github=p.get('github_url') or personal_info.get('github_url'),
						portfolio=p.get('portfolio_url') or personal_info.get('portfolio_url'),
					),
				),
				education=[
					Education(
						degree=edu.get('degree', ''),
						major=edu.get('major', ''),
						university=edu.get('university', ''),
						start_date=str(edu.get('start_date', '')),
						end_date=str(edu.get('end_date', '')),
						cgpa=edu.get('cgpa'),
						is_current=edu.get('is_current', False),
					)
					for edu in education_list
				],
				experience=[
					Experience(
						title=exp.get('title', ''),
						company=exp.get('company', ''),
						start_date=str(exp.get('start_date', '')),
						end_date=str(exp.get('end_date', '')) if not exp.get('is_current') else 'Present',
						description=exp.get('description', ''),
					)
					for exp in experience_list
				],
				projects=[
					Project(
						name=proj.get('name', ''), tech_stack=proj.get('tech_stack', []), description=proj.get('description', '')
					)
					for proj in projects_list
				],
				skills=p.get('skills', {}),
				files=Files(resume=primary_resume.get('file_path', '') if primary_resume else ''),
				application_preferences=ApplicationPreferences(
					expected_salary=p.get('expected_salary', 'Negotiable'),
					notice_period=p.get('notice_period', 'Immediate'),
					work_authorization=p.get('work_authorization', ''),
					relocation=p.get('relocation', 'Yes'),
					employment_type=p.get('employment_types', ['Full-time']),
				)
				if p.get('expected_salary')
				else None,
				behavioral_questions=p.get('behavioral_questions', {}),
			)

			# Cache the profile
			await cache.set_model(cache_key, profile, ttl_seconds=3600)  # 1 hour cache
			logger.info(f'Loaded profile for user {user_id}: {profile.personal_information.full_name}')

			return profile

		except Exception as e:
			logger.error(f'Error fetching profile for user {user_id}: {e}')
			return None

	async def create_profile(self, user_id: str, data: Dict[str, Any]) -> Optional[str]:
		"""
		Create a new user profile.
		Called during user onboarding.
		"""
		try:
			# Handle full_name -> first_name/last_name
			first_name = data.get('first_name', '')
			last_name = data.get('last_name', '')
			if 'full_name' in data and data['full_name']:
				parts = data['full_name'].split(' ', 1)
				first_name = parts[0]
				last_name = parts[1] if len(parts) > 1 else ''

			# Handle skills - convert list to dict if needed
			skills = data.get('skills', {})
			if isinstance(skills, list):
				skills = {'primary': skills} if skills else {}

			# Build personal_info JSONB object (required by database)
			personal_info = {
				'first_name': first_name or 'Unknown',
				'last_name': last_name or '',
				'email': data.get('email', ''),
				'phone': data.get('phone', ''),
				'location': data.get('city', '') or data.get('location', ''),
				'linkedin_url': data.get('linkedin_url', ''),
				'github_url': data.get('github_url', ''),
				'portfolio_url': data.get('portfolio_url', ''),
				'summary': data.get('summary', ''),
			}

			# Build profile data with all required fields
			profile_data = {
				'user_id': user_id,
				'first_name': first_name or 'Unknown',
				'last_name': last_name or '',
				'email': data.get('email', ''),
				'personal_info': personal_info,  # Required JSONB field
				'skills': skills or {},
				'education': [],
				'experience': [],
				'projects': [],
			}

			# Add optional fields only if they have values
			# Note: 'summary' is stored inside personal_info JSONB, not as a top-level column
			optional_fields = {
				'phone': data.get('phone'),
				'linkedin_url': data.get('linkedin_url'),
				'github_url': data.get('github_url'),
				'portfolio_url': data.get('portfolio_url'),
			}

			for key, value in optional_fields.items():
				if value:
					profile_data[key] = value

			logger.info(f'Creating profile with data: {list(profile_data.keys())}')

			response = self.client.table(db_tables.PROFILES).insert(profile_data).execute()

			if response.data:
				profile_id = response.data[0]['id']
				logger.info(f'Created profile {profile_id} for user {user_id}')

				# Invalidate cache
				cache_key = await self.get_profile_cache_key(user_id)
				await cache.delete(cache_key)

				# Sync to RAG
				await self._sync_to_rag(user_id)

				return profile_id

			return None

		except Exception as e:
			logger.error(f'Error creating profile for user {user_id}: {e}')
			raise

	async def update_profile(self, user_id: str, data: Dict[str, Any]) -> bool:
		"""Update user profile fields."""
		try:
			# Handle full_name -> first_name/last_name
			if 'full_name' in data and data['full_name']:
				parts = data['full_name'].split(' ', 1)
				data['first_name'] = parts[0]
				data['last_name'] = parts[1] if len(parts) > 1 else ''

			# Handle skills - convert list to dict if needed (DB column is JSONB object)
			if 'skills' in data and isinstance(data['skills'], list):
				data['skills'] = {'primary': data['skills']} if data['skills'] else {}

			# Merge summary/location into personal_info JSONB
			# (these are not top-level DB columns — they live inside personal_info)
			personal_info_updates: Dict[str, Any] = {}
			if 'summary' in data and data['summary']:
				personal_info_updates['summary'] = data.pop('summary')
			if 'location' in data and data['location']:
				personal_info_updates['location'] = data.pop('location')
			if 'city' in data and data['city']:
				personal_info_updates['location'] = data.pop('city')

			if personal_info_updates:
				# Fetch current personal_info so we merge rather than overwrite
				existing = (
					self.client.table('user_profiles')
					.select('personal_info')
					.eq('user_id', user_id)
					.maybe_single()
					.execute()
				)
				current_pi = (existing.data or {}).get('personal_info') or {}
				current_pi.update(personal_info_updates)
				# Also keep name/email in sync inside personal_info
				if 'first_name' in data:
					current_pi['first_name'] = data['first_name']
				if 'last_name' in data:
					current_pi['last_name'] = data['last_name']
				if 'email' in data:
					current_pi['email'] = data['email']
				data['personal_info'] = current_pi

			# Columns that actually exist in the database schema
			allowed_fields = {
				'first_name',
				'last_name',
				'email',
				'phone',
				'linkedin_url',
				'github_url',
				'portfolio_url',
				'personal_info',
				'skills',
				'education',
				'experience',
				'projects',
				'onboarding_completed',
			}

			update_data = {k: v for k, v in data.items() if k in allowed_fields and v is not None}

			if not update_data:
				return False

			logger.info(f'Updating profile with fields: {list(update_data.keys())}')

			response = self.client.table(db_tables.PROFILES).update(update_data).eq('user_id', user_id).execute()

			# Invalidate cache
			cache_key = await self.get_profile_cache_key(user_id)
			await cache.delete(cache_key)

			# Sync to RAG
			await self._sync_to_rag(user_id)

			logger.info(f'Updated profile for user {user_id}')
			return bool(response.data)

		except Exception as e:
			logger.error(f'Error updating profile for user {user_id}: {e}')
			return False

	async def add_education(self, user_id: str, education: Dict[str, Any]) -> Optional[str]:
		"""Add education entry for user (stored in JSONB array)."""
		try:
			# Get current profile
			profile_resp = self.client.table(db_tables.PROFILES).select('education').eq('user_id', user_id).maybe_single().execute()

			current_education = []
			if profile_resp.data:
				current_education = profile_resp.data.get('education', []) or []

			# Create new education entry with unique ID
			import uuid

			new_entry = {
				'id': str(uuid.uuid4()),
				'degree': education.get('degree', ''),
				'major': education.get('major', ''),
				'university': education.get('university', ''),
				'cgpa': education.get('cgpa'),
				'start_date': education.get('start_date'),
				'end_date': education.get('end_date'),
				'is_current': education.get('is_current', False),
			}

			current_education.append(new_entry)

			# Update profile with new education array
			response = (
				self.client.table(db_tables.PROFILES).update({'education': current_education}).eq('user_id', user_id).execute()
			)
			cache_key = await self.get_profile_cache_key(user_id)
			await cache.delete(cache_key)
			await self._sync_to_rag(user_id)

			return new_entry['id'] if response.data else None

		except Exception as e:
			logger.error(f'Error adding education for user {user_id}: {e}')
			return None

	async def add_experience(self, user_id: str, experience: Dict[str, Any]) -> Optional[str]:
		"""Add work experience entry for user (stored in JSONB array)."""
		try:
			# Get current profile
			profile_resp = self.client.table(db_tables.PROFILES).select('experience').eq('user_id', user_id).maybe_single().execute()

			current_experience = []
			if profile_resp.data:
				current_experience = profile_resp.data.get('experience', []) or []

			# Create new experience entry with unique ID
			import uuid

			new_entry = {
				'id': str(uuid.uuid4()),
				'title': experience.get('title', ''),
				'company': experience.get('company', ''),
				'start_date': experience.get('start_date'),
				'end_date': experience.get('end_date'),
				'is_current': experience.get('is_current', False),
				'description': experience.get('description', ''),
			}

			current_experience.append(new_entry)

			# Update profile with new experience array
			response = (
				self.client.table(db_tables.PROFILES).update({'experience': current_experience}).eq('user_id', user_id).execute()
			)
			cache_key = await self.get_profile_cache_key(user_id)
			await cache.delete(cache_key)
			await self._sync_to_rag(user_id)

			return new_entry['id'] if response.data else None

		except Exception as e:
			logger.error(f'Error adding experience for user {user_id}: {e}')
			return None

	async def add_project(self, user_id: str, project: Dict[str, Any]) -> Optional[str]:
		"""Add project entry for user (stored in JSONB array)."""
		try:
			# Get current profile
			profile_resp = self.client.table(db_tables.PROFILES).select('projects').eq('user_id', user_id).maybe_single().execute()

			current_projects = []
			if profile_resp.data:
				current_projects = profile_resp.data.get('projects', []) or []

			# Create new project entry with unique ID
			import uuid

			new_entry = {
				'id': str(uuid.uuid4()),
				'name': project.get('name', ''),
				'tech_stack': project.get('tech_stack', []),
				'description': project.get('description', ''),
				'project_url': project.get('project_url'),
			}

			current_projects.append(new_entry)

			# Update profile with new projects array
			response = self.client.table(db_tables.PROFILES).update({'projects': current_projects}).eq('user_id', user_id).execute()
			cache_key = await self.get_profile_cache_key(user_id)
			await cache.delete(cache_key)
			await self._sync_to_rag(user_id)

			return new_entry['id'] if response.data else None

		except Exception as e:
			logger.error(f'Error adding project for user {user_id}: {e}')
			return None
	async def update_education(self, user_id: str, education_id: str, education: Dict[str, Any]) -> bool:
		"""Update a specific education entry."""
		try:
			profile_resp = self.client.table(db_tables.PROFILES).select('education').eq('user_id', user_id).maybe_single().execute()
			current_education = []
			if profile_resp.data:
				current_education = profile_resp.data.get('education', []) or []
			
			updated = False
			for i, entry in enumerate(current_education):
				if entry.get('id') == education_id:
					# Update fields, keeping the original ID
					current_education[i] = {
						'id': education_id,
						'degree': education.get('degree', entry.get('degree')),
						'major': education.get('major', entry.get('major')),
						'university': education.get('university', entry.get('university')),
						'cgpa': education.get('cgpa', entry.get('cgpa')),
						'start_date': education.get('start_date', entry.get('start_date')),
						'end_date': education.get('end_date', entry.get('end_date')),
						'is_current': education.get('is_current', entry.get('is_current')),
					}
					updated = True
					break
					
			if not updated:
				return False
				
			response = self.client.table(db_tables.PROFILES).update({'education': current_education}).eq('user_id', user_id).execute()
			cache_key = await self.get_profile_cache_key(user_id)
			await cache.delete(cache_key)
			await self._sync_to_rag(user_id)
			return bool(response.data)
		except Exception as e:
			logger.error(f'Error updating education {education_id} for user {user_id}: {e}')
			return False

	async def delete_education(self, user_id: str, education_id: str) -> bool:
		"""Delete a specific education entry."""
		try:
			profile_resp = self.client.table(db_tables.PROFILES).select('education').eq('user_id', user_id).maybe_single().execute()
			if not profile_resp.data:
				return False
			
			current_education = profile_resp.data.get('education', []) or []
			new_education = [e for e in current_education if e.get('id') != education_id]
			
			if len(new_education) == len(current_education):
				return False
				
			response = self.client.table(db_tables.PROFILES).update({'education': new_education}).eq('user_id', user_id).execute()
			cache_key = await self.get_profile_cache_key(user_id)
			await cache.delete(cache_key)
			await self._sync_to_rag(user_id)
			return bool(response.data)
		except Exception as e:
			logger.error(f'Error deleting education {education_id} for user {user_id}: {e}')
			return False

	async def update_experience(self, user_id: str, experience_id: str, experience: Dict[str, Any]) -> bool:
		"""Update a specific work experience entry."""
		try:
			profile_resp = self.client.table(db_tables.PROFILES).select('experience').eq('user_id', user_id).maybe_single().execute()
			current_experience = []
			if profile_resp.data:
				current_experience = profile_resp.data.get('experience', []) or []
			
			updated = False
			for i, entry in enumerate(current_experience):
				if entry.get('id') == experience_id:
					current_experience[i] = {
						'id': experience_id,
						'title': experience.get('title', entry.get('title')),
						'company': experience.get('company', entry.get('company')),
						'start_date': experience.get('start_date', entry.get('start_date')),
						'end_date': experience.get('end_date', entry.get('end_date')),
						'is_current': experience.get('is_current', entry.get('is_current')),
						'description': experience.get('description', entry.get('description')),
					}
					updated = True
					break
					
			if not updated:
				return False
				
			response = self.client.table(db_tables.PROFILES).update({'experience': current_experience}).eq('user_id', user_id).execute()
			cache_key = await self.get_profile_cache_key(user_id)
			await cache.delete(cache_key)
			await self._sync_to_rag(user_id)
			return bool(response.data)
		except Exception as e:
			logger.error(f'Error updating experience {experience_id} for user {user_id}: {e}')
			return False

	async def delete_experience(self, user_id: str, experience_id: str) -> bool:
		"""Delete a specific work experience entry."""
		try:
			profile_resp = self.client.table(db_tables.PROFILES).select('experience').eq('user_id', user_id).maybe_single().execute()
			if not profile_resp.data:
				return False
			
			current_experience = profile_resp.data.get('experience', []) or []
			new_experience = [e for e in current_experience if e.get('id') != experience_id]
			
			if len(new_experience) == len(current_experience):
				return False
				
			response = self.client.table(db_tables.PROFILES).update({'experience': new_experience}).eq('user_id', user_id).execute()
			cache_key = await self.get_profile_cache_key(user_id)
			await cache.delete(cache_key)
			await self._sync_to_rag(user_id)
			return bool(response.data)
		except Exception as e:
			logger.error(f'Error deleting experience {experience_id} for user {user_id}: {e}')
			return False

	async def update_project(self, user_id: str, project_id: str, project: Dict[str, Any]) -> bool:
		"""Update a specific project entry."""
		try:
			profile_resp = self.client.table(db_tables.PROFILES).select('projects').eq('user_id', user_id).maybe_single().execute()
			current_projects = []
			if profile_resp.data:
				current_projects = profile_resp.data.get('projects', []) or []
			
			updated = False
			for i, entry in enumerate(current_projects):
				if entry.get('id') == project_id:
					current_projects[i] = {
						'id': project_id,
						'name': project.get('name', entry.get('name')),
						'tech_stack': project.get('tech_stack', entry.get('tech_stack')),
						'description': project.get('description', entry.get('description')),
						'project_url': project.get('project_url', entry.get('project_url')),
					}
					updated = True
					break
					
			if not updated:
				return False
				
			response = self.client.table(db_tables.PROFILES).update({'projects': current_projects}).eq('user_id', user_id).execute()
			cache_key = await self.get_profile_cache_key(user_id)
			await cache.delete(cache_key)
			await self._sync_to_rag(user_id)
			return bool(response.data)
		except Exception as e:
			logger.error(f'Error updating project {project_id} for user {user_id}: {e}')
			return False

	async def delete_project(self, user_id: str, project_id: str) -> bool:
		"""Delete a specific project entry."""
		try:
			profile_resp = self.client.table(db_tables.PROFILES).select('projects').eq('user_id', user_id).maybe_single().execute()
			if not profile_resp.data:
				return False
			
			current_projects = profile_resp.data.get('projects', []) or []
			new_projects = [p for p in current_projects if p.get('id') != project_id]
			
			if len(new_projects) == len(current_projects):
				return False
				
			response = self.client.table(db_tables.PROFILES).update({'projects': new_projects}).eq('user_id', user_id).execute()
			cache_key = await self.get_profile_cache_key(user_id)
			await cache.delete(cache_key)
			await self._sync_to_rag(user_id)
			return bool(response.data)
		except Exception as e:
			logger.error(f'Error deleting project {project_id} for user {user_id}: {e}')
			return False

	async def update_skills(self, user_id: str, skills: Dict[str, Any]) -> bool:
		"""Update skills for user (stored in JSONB)."""
		try:
			response = self.client.table(db_tables.PROFILES).update({'skills': skills}).eq('user_id', user_id).execute()
			cache_key = await self.get_profile_cache_key(user_id)
			await cache.delete(cache_key)
			await self._sync_to_rag(user_id)

			return bool(response.data)

		except Exception as e:
			logger.error(f'Error updating skills for user {user_id}: {e}')
			return False

	async def check_profile_exists(self, user_id: str) -> bool:
		"""Check if user has completed their profile."""
		try:
			response = self.client.table(db_tables.PROFILES).select('id').eq('user_id', user_id).maybe_single().execute()

			return response.data is not None

		except Exception as e:
			logger.debug(f'Profile check failed for user {user_id}: {e}')
			return False

	async def get_profile_completion(self, user_id: str) -> Dict[str, bool]:
		"""Get profile completion status for onboarding UI."""
		try:
			profile = await self.get_profile(user_id)

			if not profile:
				return {
					'has_profile': False,
					'has_education': False,
					'has_experience': False,
					'has_projects': False,
					'has_skills': False,
					'has_resume': False,
					'completion_percent': 0,
				}

			has_education = len(profile.education) > 0
			has_experience = len(profile.experience) > 0
			has_projects = len(profile.projects) > 0
			has_skills = bool(profile.skills)
			has_resume = bool(profile.files.resume)

			completed = sum(
				[
					True,  # has_profile
					has_education,
					has_experience,
					has_projects,
					has_skills,
					has_resume,
				]
			)
			return {
				'has_profile': True,
				'has_education': has_education,
				'has_experience': has_experience,
				'has_projects': has_projects,
				'has_skills': has_skills,
				'has_resume': has_resume,
				'completion_percent': int((completed / 6) * 100),
			}

		except Exception as e:
			logger.error(f'Error checking profile completion: {e}')
			return {'has_profile': False, 'completion_percent': 0}

	async def sync_onboarding_status(self, user_id: str) -> bool:
		"""Synchronize onboarding_completed flag based on current profile readiness."""
		try:
			completion = await self.get_profile_completion(user_id)
			onboarding_ready = bool(
				completion.get('has_profile')
				and completion.get('has_resume')
				and completion.get('has_skills')
				and (
					completion.get('has_experience')
					or completion.get('has_projects')
					or completion.get('has_education')
				)
			)
			current = (
				self.client.table(db_tables.PROFILES)
				.select('onboarding_completed')
				.eq('user_id', user_id)
				.maybe_single()
				.execute()
			)
			current_flag = bool((current.data or {}).get('onboarding_completed', False))
			if current_flag != onboarding_ready:
				self.client.table(db_tables.PROFILES).update({'onboarding_completed': onboarding_ready}).eq('user_id', user_id).execute()
			return onboarding_ready
		except Exception as e:
			logger.warning(f'Failed to sync onboarding_completed for {user_id}: {e}')
			return False

	async def invalidate_cache(self, user_id: str):
		"""Clear cached profile for user."""
		cache_key = await self.get_profile_cache_key(user_id)
		await cache.delete(cache_key)

	def _profile_to_text(self, profile: UserProfile) -> str:
		"""Convert profile object to text format for RAG."""
		lines = [f'User Profile for {profile.personal_information.full_name}']

		p = profile.personal_information
		lines.append(f'Contact: {p.email} | {p.phone}')
		lines.append(f'Location: {p.location.city}, {p.location.country}')
		if p.summary:
			lines.append(f'Summary: {p.summary}')

		if p.urls:
			lines.append(f'Links: LinkedIn: {p.urls.linkedin}, GitHub: {p.urls.github}, Portfolio: {p.urls.portfolio}')

		# Skills
		skills = profile.skills
		if isinstance(skills, dict):
			primary = skills.get('primary', [])
			lines.append(f'Skills: {", ".join(primary)}')
		elif isinstance(skills, list):
			lines.append(f'Skills: {", ".join(skills)}')

		# Experience
		if profile.experience:
			lines.append('\nWork Experience:')
			for exp in profile.experience:
				lines.append(f'- {exp.title} at {exp.company} ({exp.start_date} - {exp.end_date})')
				if exp.description:
					lines.append(f'  Details: {exp.description}')

		# Education
		if profile.education:
			lines.append('\nEducation:')
			for edu in profile.education:
				lines.append(f'- {edu.degree} in {edu.major} at {edu.university} ({edu.start_date} - {edu.end_date})')

		# Projects
		if profile.projects:
			lines.append('\nProjects:')
			for proj in profile.projects:
				lines.append(f'- {proj.name}: {proj.description}')
				if proj.tech_stack:
					lines.append(f'  Tech Stack: {", ".join(proj.tech_stack)}')

		# Preferences
		if profile.application_preferences:
			pref = profile.application_preferences
			lines.append(f'\nPreferences: Expected Salary: {pref.expected_salary}, Notice Period: {pref.notice_period}')
			lines.append(f'Relocation: {pref.relocation}, Employment Types: {", ".join(pref.employment_type)}')

		return '\n'.join(lines)

	async def _sync_to_rag(self, user_id: str):
		"""Fetch latest profile and sync to RAG."""
		try:
			profile = await self.get_profile(user_id)
			if profile:
				text = self._profile_to_text(profile)
				await rag_service.sync_user_profile(user_id, text)
		except Exception as e:
			logger.error(f'Failed to sync profile RAG for {user_id}: {e}')


user_profile_service = UserProfileService()
