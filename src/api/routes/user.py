"""
User Profile API Routes - Onboarding and Profile Management
Multi-tenant endpoints with JWT authentication
"""

import logging
import inspect
from typing import Annotated, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from src.api.schemas import (
	EducationAddResponse,
	ExperienceAddResponse,
	GeneratedResumesResponse,
	HealthResponse,
	PrimaryResumeResponse,
	ProfileCreateResponse,
	ProfileResponse,
	ProfileUpdateResponse,
	ProjectAddResponse,
	ResumeListResponse,
	ResumeUploadResponse,
	SuccessResponse,
)
from src.core.auth import AuthUser, get_current_user, rate_limit_check
from src.services.resume_storage_service import resume_storage_service
from src.services.rag_service import rag_service
from src.services.user_profile_service import user_profile_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/user', tags=['User Profile'])


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateProfileRequest(BaseModel):
	"""Request model for creating user profile."""

	# Support both formats (frontend uses full_name/location, legacy uses first/last)
	full_name: Optional[str] = None  # Frontend format - will be split
	first_name: Optional[str] = None  # Legacy format
	last_name: Optional[str] = None  # Legacy format
	email: Optional[str] = None
	phone: Optional[str] = None
	location: Optional[str] = None  # Frontend format
	city: Optional[str] = None  # Legacy format
	country: Optional[str] = None
	address: Optional[str] = None
	linkedin_url: Optional[str] = None
	github_url: Optional[str] = None
	portfolio_url: Optional[str] = None
	summary: Optional[str] = None
	skills: Optional[List[str]] = None  # Frontend sends list
	years_of_experience: Optional[int] = None
	desired_roles: Optional[List[str]] = None
	desired_locations: Optional[List[str]] = None
	min_salary: Optional[int] = None
	expected_salary: Optional[str] = None
	notice_period: Optional[str] = None
	work_authorization: Optional[str] = None
	relocation: Optional[str] = None
	employment_types: Optional[List[str]] = None
	behavioral_questions: Optional[Dict[str, str]] = None


class UpdateProfileRequest(BaseModel):
	"""Request model for updating user profile."""

	# Support both formats (frontend uses full_name/location, legacy uses first/last/city/country)
	full_name: Optional[str] = None
	first_name: Optional[str] = None
	last_name: Optional[str] = None
	phone: Optional[str] = None
	location: Optional[str] = None  # Frontend format
	city: Optional[str] = None  # Legacy format
	country: Optional[str] = None  # Legacy format
	address: Optional[str] = None
	linkedin_url: Optional[str] = None
	github_url: Optional[str] = None
	portfolio_url: Optional[str] = None
	summary: Optional[str] = None
	skills: Optional[Dict[str, List[str]]] = None  # Changed to Dict for categorized skills
	years_of_experience: Optional[int] = None
	desired_roles: Optional[List[str]] = None
	desired_locations: Optional[List[str]] = None
	min_salary: Optional[int] = None
	expected_salary: Optional[str] = None
	notice_period: Optional[str] = None
	work_authorization: Optional[str] = None
	relocation: Optional[str] = None
	employment_types: Optional[List[str]] = None
	behavioral_questions: Optional[Dict[str, str]] = None


class AddEducationRequest(BaseModel):
	"""Request model for adding education."""

	degree: str
	major: str
	university: str
	cgpa: Optional[str] = None
	start_date: Optional[str] = None
	end_date: Optional[str] = None
	is_current: bool = False


class AddExperienceRequest(BaseModel):
	"""Request model for adding work experience."""

	title: str
	company: str
	start_date: Optional[str] = None
	end_date: Optional[str] = None
	is_current: bool = False
	description: Optional[str] = None


class AddProjectRequest(BaseModel):
	"""Request model for adding a project."""

	name: str
	tech_stack: List[str] = []
	description: Optional[str] = None
	project_url: Optional[str] = None


class ProfileCompletionResponse(BaseModel):
	"""Response for profile completion status."""

	has_profile: bool
	has_education: bool
	has_experience: bool
	has_projects: bool
	has_skills: bool
	has_resume: bool
	completion_percent: int


class ProfileReadinessResponse(BaseModel):
	ready: bool
	missing_requirements: List[str]
	completion: ProfileCompletionResponse


class DataIntegrityResponse(BaseModel):
	user_id: str
	db: Dict[str, int | bool]
	rag: Dict[str, int | bool]
	consistent: bool
	notes: List[str]


# ============================================================================
# Profile Endpoints
# ============================================================================


@router.get('/profile', response_model=ProfileResponse)
async def get_profile(user: Annotated[AuthUser, Depends(get_current_user)]):
	"""
	Get the current user's complete profile.
	Returns null if profile not yet created.
	"""
	profile = await user_profile_service.get_profile(user.id)

	if not profile:
		return {'profile': None, 'message': 'Profile not found. Please complete onboarding.'}

	profile_payload = profile.model_dump()
	if inspect.isawaitable(profile_payload):
		profile_payload = await profile_payload
	return {'profile': profile_payload}


@router.post('/profile', response_model=ProfileCreateResponse)
async def create_profile(request: CreateProfileRequest, user: Annotated[AuthUser, Depends(rate_limit_check)]):
	"""
	Create a new user profile or update if exists (upsert behavior).
	Called during onboarding flow.
	"""
	try:
		# Check if profile already exists
		exists = await user_profile_service.check_profile_exists(user.id)

		# Ensure email is populated from the authenticated user if not provided
		profile_data = request.model_dump(exclude_none=True)
		if not profile_data.get('email'):
			profile_data['email'] = user.email

		if exists:
			# Update existing profile instead of throwing error
			logger.info(f'Profile exists for user {user.id}, updating instead')
			success = await user_profile_service.update_profile(user_id=user.id, data=profile_data)

			if not success:
				raise HTTPException(status_code=500, detail='Failed to update existing profile')
			await user_profile_service.sync_onboarding_status(user.id)

			return {'success': True, 'message': 'Profile updated successfully'}
		else:
			# Create new profile
			profile_id = await user_profile_service.create_profile(user_id=user.id, data=profile_data)

			if not profile_id:
				raise HTTPException(status_code=500, detail='Failed to create profile')
			await user_profile_service.sync_onboarding_status(user.id)

			logger.info(f'Created profile for user {user.id}')

			return {'success': True, 'profile_id': profile_id, 'message': 'Profile created successfully'}
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f'Error creating/updating profile for user {user.id}: {e}')
		raise HTTPException(status_code=500, detail=f'Failed to create/update profile: {str(e)}')


@router.put('/profile', response_model=ProfileUpdateResponse)
async def update_profile(request: UpdateProfileRequest, user: Annotated[AuthUser, Depends(rate_limit_check)]):
	"""Update user profile fields."""
	try:
		success = await user_profile_service.update_profile(user_id=user.id, data=request.model_dump(exclude_none=True))

		if not success:
			raise HTTPException(
				status_code=404, detail='Profile not found. Please create a profile first using POST /api/user/profile'
			)
		await user_profile_service.sync_onboarding_status(user.id)

		return {'success': True, 'message': 'Profile updated successfully'}
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f'Error updating profile for user {user.id}: {e}')
		raise HTTPException(status_code=500, detail=f'Failed to update profile: {str(e)}')


@router.get('/profile/completion', response_model=ProfileCompletionResponse)
async def get_profile_completion(user: Annotated[AuthUser, Depends(get_current_user)]):
	"""
	Get profile completion status for onboarding progress UI.
	"""
	return await user_profile_service.get_profile_completion(user.id)


@router.get('/profile/readiness', response_model=ProfileReadinessResponse)
async def get_profile_readiness(user: Annotated[AuthUser, Depends(get_current_user)]):
	"""
	Readiness gate for pipeline execution.
	Provides explicit missing requirements.
	"""
	completion = await user_profile_service.get_profile_completion(user.id)
	missing: List[str] = []
	if not completion.get('has_profile'):
		missing.append('profile')
	if not completion.get('has_resume'):
		missing.append('resume')
	if not completion.get('has_skills'):
		missing.append('skills')
	if not (completion.get('has_experience') or completion.get('has_projects') or completion.get('has_education')):
		missing.append('experience_or_projects_or_education')

	return {'ready': len(missing) == 0, 'missing_requirements': missing, 'completion': completion}


@router.get('/data-integrity', response_model=DataIntegrityResponse)
async def get_data_integrity(user: Annotated[AuthUser, Depends(get_current_user)]):
	"""
	Verify user data persistence consistency across DB tables and RAG store.
	"""
	completion = await user_profile_service.get_profile_completion(user.id)
	resumes = await resume_storage_service.get_user_resumes(user.id)
	primary_resume = await resume_storage_service.get_primary_resume(user.id)

	total_docs = 0
	profile_docs = 0
	resume_docs = 0
	notes: List[str] = []
	try:
		all_docs = rag_service.client.table('documents').select('id', count='exact').eq('user_id', user.id).execute()
		total_docs = int(getattr(all_docs, 'count', 0) or 0)
		profile_rows = (
			rag_service.client.table('documents')
			.select('id', count='exact')
			.eq('user_id', user.id)
			.contains('metadata', {'type': 'profile'})
			.execute()
		)
		profile_docs = int(getattr(profile_rows, 'count', 0) or 0)
		resume_rows = (
			rag_service.client.table('documents')
			.select('id', count='exact')
			.eq('user_id', user.id)
			.contains('metadata', {'type': 'resume'})
			.execute()
		)
		resume_docs = int(getattr(resume_rows, 'count', 0) or 0)
	except Exception as e:
		notes.append(f'RAG verification fallback: {e}')

	consistent = True
	if completion.get('has_profile') and profile_docs == 0:
		consistent = False
		notes.append('Profile exists in DB but no profile chunks found in RAG.')
	if len(resumes) > 0 and resume_docs == 0:
		consistent = False
		notes.append('Resumes exist in DB but no resume chunks found in RAG.')
	if completion.get('has_resume') and not primary_resume:
		consistent = False
		notes.append('Completion says has_resume=true but primary resume is missing.')

	return {
		'user_id': user.id,
		'db': {
			'has_profile': bool(completion.get('has_profile')),
			'resumes_total': len(resumes),
			'has_primary_resume': bool(primary_resume),
			'has_skills': bool(completion.get('has_skills')),
			'completion_percent': int(completion.get('completion_percent', 0)),
		},
		'rag': {
			'rag_enabled': bool(rag_service.enabled),
			'total_docs': total_docs,
			'profile_docs': profile_docs,
			'resume_docs': resume_docs,
		},
		'consistent': consistent,
		'notes': notes,
	}




# ============================================================================
# Education Endpoints
# ============================================================================


@router.post('/education', response_model=EducationAddResponse)
async def add_education(request: AddEducationRequest, user: Annotated[AuthUser, Depends(rate_limit_check)]):
	"""Add an education entry."""
	education_id = await user_profile_service.add_education(user_id=user.id, education=request.model_dump())

	if not education_id:
		raise HTTPException(status_code=500, detail='Failed to add education')
	await user_profile_service.sync_onboarding_status(user.id)

	return {'success': True, 'education_id': education_id}


@router.put('/education/{education_id}', response_model=SuccessResponse)
async def update_education(education_id: str, request: AddEducationRequest, user: Annotated[AuthUser, Depends(rate_limit_check)]):
	"""Update an education entry."""
	success = await user_profile_service.update_education(
		user_id=user.id, education_id=education_id, education=request.model_dump()
	)

	if not success:
		raise HTTPException(status_code=404, detail='Education entry not found or update failed')
	await user_profile_service.sync_onboarding_status(user.id)

	return {'success': True, 'message': 'Education updated successfully'}


@router.delete('/education/{education_id}', response_model=SuccessResponse)
async def delete_education(education_id: str, user: Annotated[AuthUser, Depends(rate_limit_check)]):
	"""Delete an education entry."""
	success = await user_profile_service.delete_education(user_id=user.id, education_id=education_id)

	if not success:
		raise HTTPException(status_code=404, detail='Education entry not found or delete failed')
	await user_profile_service.sync_onboarding_status(user.id)

	return {'success': True, 'message': 'Education deleted successfully'}



# ============================================================================
# Experience Endpoints
# ============================================================================


@router.post('/experience', response_model=ExperienceAddResponse)
async def add_experience(request: AddExperienceRequest, user: Annotated[AuthUser, Depends(rate_limit_check)]):
	"""Add a work experience entry."""
	experience_id = await user_profile_service.add_experience(user_id=user.id, experience=request.model_dump())

	if not experience_id:
		raise HTTPException(status_code=500, detail='Failed to add experience')
	await user_profile_service.sync_onboarding_status(user.id)

	return {'success': True, 'experience_id': experience_id}


@router.put('/experience/{experience_id}', response_model=SuccessResponse)
async def update_experience(experience_id: str, request: AddExperienceRequest, user: Annotated[AuthUser, Depends(rate_limit_check)]):
	"""Update a work experience entry."""
	success = await user_profile_service.update_experience(
		user_id=user.id, experience_id=experience_id, experience=request.model_dump()
	)

	if not success:
		raise HTTPException(status_code=404, detail='Experience entry not found or update failed')
	await user_profile_service.sync_onboarding_status(user.id)

	return {'success': True, 'message': 'Experience updated successfully'}


@router.delete('/experience/{experience_id}', response_model=SuccessResponse)
async def delete_experience(experience_id: str, user: Annotated[AuthUser, Depends(rate_limit_check)]):
	"""Delete a work experience entry."""
	success = await user_profile_service.delete_experience(user_id=user.id, experience_id=experience_id)

	if not success:
		raise HTTPException(status_code=404, detail='Experience entry not found or delete failed')
	await user_profile_service.sync_onboarding_status(user.id)

	return {'success': True, 'message': 'Experience deleted successfully'}



# ============================================================================
# Projects Endpoints
# ============================================================================


@router.post('/projects', response_model=ProjectAddResponse)
async def add_project(request: AddProjectRequest, user: Annotated[AuthUser, Depends(rate_limit_check)]):
	"""Add a project entry."""
	project_id = await user_profile_service.add_project(user_id=user.id, project=request.model_dump())

	if not project_id:
		raise HTTPException(status_code=500, detail='Failed to add project')
	await user_profile_service.sync_onboarding_status(user.id)

	return {'success': True, 'project_id': project_id}


@router.put('/projects/{project_id}', response_model=SuccessResponse)
async def update_project(project_id: str, request: AddProjectRequest, user: Annotated[AuthUser, Depends(rate_limit_check)]):
	"""Update a project entry."""
	success = await user_profile_service.update_project(
		user_id=user.id, project_id=project_id, project=request.model_dump()
	)

	if not success:
		raise HTTPException(status_code=404, detail='Project entry not found or update failed')
	await user_profile_service.sync_onboarding_status(user.id)

	return {'success': True, 'message': 'Project updated successfully'}


@router.delete('/projects/{project_id}', response_model=SuccessResponse)
async def delete_project(project_id: str, user: Annotated[AuthUser, Depends(rate_limit_check)]):
	"""Delete a project entry."""
	success = await user_profile_service.delete_project(user_id=user.id, project_id=project_id)

	if not success:
		raise HTTPException(status_code=404, detail='Project entry not found or delete failed')
	await user_profile_service.sync_onboarding_status(user.id)

	return {'success': True, 'message': 'Project deleted successfully'}


# ============================================================================
# Resume Endpoints
# ============================================================================


@router.post('/resume/parse-and-upload', response_model=ResumeUploadResponse)
async def parse_and_upload_resume(
	file: Annotated[UploadFile, File()],
	user: Annotated[AuthUser, Depends(rate_limit_check)],
	name: Annotated[Optional[str], Form()] = None,
	is_primary: Annotated[bool, Form()] = True,
):
	"""
	Parse resume to extract data AND upload to storage.
	Returns both parsed data for auto-fill and resume metadata.
	"""
	# Validate file type
	if not file.filename or not file.filename.lower().endswith('.pdf'):
		raise HTTPException(status_code=400, detail='Only PDF files are supported')

	# Read file content
	content = await file.read()

	# Validate file size (max 10MB)
	if len(content) > 10 * 1024 * 1024:
		raise HTTPException(status_code=400, detail='File size must be less than 10MB')

	try:
		# Parse resume content first
		parsed_data = await resume_storage_service.parse_resume_content(content)

		# Upload to storage
		result = await resume_storage_service.upload_resume(
			user_id=user.id,
			file_content=content,
			filename=file.filename or 'resume.pdf',
			name=name,
			is_primary=is_primary,
			parsed_data=parsed_data,
		)

		if not result:
			raise HTTPException(status_code=500, detail='Failed to upload resume')

		# Best-effort profile enrichment from parsed resume data.
		try:
			update_payload = {}
			personal = parsed_data.get('personal_info', {}) if isinstance(parsed_data, dict) else {}
			if personal.get('first_name'):
				update_payload['first_name'] = personal.get('first_name')
			if personal.get('last_name'):
				update_payload['last_name'] = personal.get('last_name')
			if personal.get('phone'):
				update_payload['phone'] = personal.get('phone')
			if personal.get('linkedin_url'):
				update_payload['linkedin_url'] = personal.get('linkedin_url')
			if personal.get('github_url'):
				update_payload['github_url'] = personal.get('github_url')
			if personal.get('portfolio_url'):
				update_payload['portfolio_url'] = personal.get('portfolio_url')
			if personal.get('summary'):
				update_payload['summary'] = personal.get('summary')
			if personal.get('city'):
				update_payload['location'] = personal.get('city')
			if isinstance(parsed_data.get('skills'), dict) and parsed_data.get('skills'):
				update_payload['skills'] = parsed_data.get('skills')
			if isinstance(parsed_data.get('education'), list) and parsed_data.get('education'):
				update_payload['education'] = parsed_data.get('education')
			if isinstance(parsed_data.get('experience'), list) and parsed_data.get('experience'):
				update_payload['experience'] = parsed_data.get('experience')
			if isinstance(parsed_data.get('projects'), list) and parsed_data.get('projects'):
				update_payload['projects'] = parsed_data.get('projects')

			if update_payload:
				await user_profile_service.update_profile(user_id=user.id, data=update_payload)
			await user_profile_service.sync_onboarding_status(user.id)
		except Exception as enrich_err:
			logger.warning(f'Resume parsed-data profile enrichment failed (non-fatal): {enrich_err}')

		logger.info(f'User {user.id} uploaded and parsed resume: {result.file_name}')

		return {'success': True, 'resume': result.model_dump(), 'parsed_data': parsed_data}
	except Exception as e:
		logger.error(f'Error in parse_and_upload_resume: {str(e)}', exc_info=True)
		raise HTTPException(status_code=500, detail=f'Failed to process resume: {str(e)}')


@router.post('/resume/upload', response_model=ResumeUploadResponse)
async def upload_resume(
	file: Annotated[UploadFile, File()],
	user: Annotated[AuthUser, Depends(rate_limit_check)],
	name: Annotated[str, Form()] = 'Primary Resume',
	is_primary: Annotated[bool, Form()] = True,
):
	"""
	Upload a resume PDF file.
	Stores in Supabase Storage and creates metadata record.
	"""
	# Validate file type
	if not file.content_type or 'pdf' not in file.content_type.lower():
		raise HTTPException(status_code=400, detail='Only PDF files are supported')

	# Read file content
	content = await file.read()

	# Validate file size (max 10MB)
	if len(content) > 10 * 1024 * 1024:
		raise HTTPException(status_code=400, detail='File size must be less than 10MB')

	# Upload to storage
	result = await resume_storage_service.upload_resume(
		user_id=user.id, file_content=content, filename=file.filename or 'resume.pdf', name=name, is_primary=is_primary
	)

	if not result:
		raise HTTPException(status_code=500, detail='Failed to upload resume')
	await user_profile_service.sync_onboarding_status(user.id)

	logger.info(f'User {user.id} uploaded resume: {result.file_name}')

	return {'success': True, 'resume': result.model_dump()}


@router.get('/resumes', response_model=ResumeListResponse)
async def get_resumes(user: Annotated[AuthUser, Depends(get_current_user)]):
	"""Get all resumes for the current user."""
	resumes = await resume_storage_service.get_user_resumes(user.id)
	return {'resumes': [r.model_dump() for r in resumes]}


@router.get('/resume/primary', response_model=PrimaryResumeResponse)
async def get_primary_resume(user: Annotated[AuthUser, Depends(get_current_user)]):
	"""Get user's primary resume metadata and URL."""
	resume = await resume_storage_service.get_primary_resume(user.id)

	if not resume:
		return {'resume': None, 'message': 'No primary resume found'}

	return {'resume': resume.model_dump()}


@router.delete('/resume/{resume_id}', response_model=SuccessResponse)
async def delete_resume(resume_id: str, user: Annotated[AuthUser, Depends(rate_limit_check)]):
	"""Delete a resume file."""
	success = await resume_storage_service.delete_resume(user.id, resume_id)

	if not success:
		raise HTTPException(status_code=404, detail='Resume not found')
	await user_profile_service.sync_onboarding_status(user.id)

	return {'success': True, 'message': 'Resume deleted'}


@router.get('/generated-resumes', response_model=GeneratedResumesResponse)
async def get_generated_resumes(user: Annotated[AuthUser, Depends(get_current_user)], limit: int = 50):
	"""Get history of AI-generated tailored resumes."""
	resumes = await resume_storage_service.get_generated_resumes(user.id, limit)
	return {'generated_resumes': [r.model_dump() for r in resumes]}


# ============================================================================
# Health Check
# ============================================================================


@router.get('/health', response_model=HealthResponse)
async def user_health():
	"""User service health check (public endpoint)."""
	return {'status': 'healthy', 'service': 'user-profile'}
