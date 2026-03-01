"""
User Profile API Routes - Onboarding and Profile Management
Multi-tenant endpoints with JWT authentication
"""

import logging
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

	return {'profile': profile.model_dump()}


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

			return {'success': True, 'message': 'Profile updated successfully'}
		else:
			# Create new profile
			profile_id = await user_profile_service.create_profile(user_id=user.id, data=profile_data)

			if not profile_id:
				raise HTTPException(status_code=500, detail='Failed to create profile')

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


# ============================================================================
# Education Endpoints
# ============================================================================


@router.post('/education', response_model=EducationAddResponse)
async def add_education(request: AddEducationRequest, user: Annotated[AuthUser, Depends(rate_limit_check)]):
	"""Add an education entry."""
	education_id = await user_profile_service.add_education(user_id=user.id, education=request.model_dump())

	if not education_id:
		raise HTTPException(status_code=500, detail='Failed to add education')

	return {'success': True, 'education_id': education_id}


# ============================================================================
# Experience Endpoints
# ============================================================================


@router.post('/experience', response_model=ExperienceAddResponse)
async def add_experience(request: AddExperienceRequest, user: Annotated[AuthUser, Depends(rate_limit_check)]):
	"""Add a work experience entry."""
	experience_id = await user_profile_service.add_experience(user_id=user.id, experience=request.model_dump())

	if not experience_id:
		raise HTTPException(status_code=500, detail='Failed to add experience')

	return {'success': True, 'experience_id': experience_id}


# ============================================================================
# Projects Endpoints
# ============================================================================


@router.post('/projects', response_model=ProjectAddResponse)
async def add_project(request: AddProjectRequest, user: Annotated[AuthUser, Depends(rate_limit_check)]):
	"""Add a project entry."""
	project_id = await user_profile_service.add_project(user_id=user.id, project=request.model_dump())

	if not project_id:
		raise HTTPException(status_code=500, detail='Failed to add project')

	return {'success': True, 'project_id': project_id}


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
			user_id=user.id, file_content=content, filename=file.filename or 'resume.pdf', name=name, is_primary=is_primary
		)

		if not result:
			raise HTTPException(status_code=500, detail='Failed to upload resume')

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
