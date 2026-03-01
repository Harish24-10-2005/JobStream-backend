"""
Centralized Pydantic response schemas for all API endpoints.
Provides typed response_model for FastAPI auto-documentation and validation.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

# ============================================================================
# Common / Shared
# ============================================================================


class SuccessResponse(BaseModel):
	"""Generic success envelope."""

	success: bool = True
	message: Optional[str] = None


class StatusResponse(BaseModel):
	"""Generic status envelope."""

	status: str
	message: Optional[str] = None


class HealthResponse(BaseModel):
	status: str = 'healthy'
	service: str


# ============================================================================
# Jobs
# ============================================================================


class SavedJob(BaseModel):
	id: str
	url: str


class JobSearchResponse(BaseModel):
	status: str
	query: str
	location: str
	jobs: List[SavedJob]
	total: int


class JobAnalyzeResponse(BaseModel):
	job_id: str
	status: str
	cached: bool = False
	role: Optional[str] = None
	company: Optional[str] = None
	match_score: Optional[int] = None
	matching_skills: Optional[List[str]] = None
	missing_skills: Optional[List[str]] = None
	tech_stack: Optional[List[str]] = None
	gap_analysis_advice: Optional[str] = None
	salary: Optional[str] = None
	reasoning: Optional[str] = None
	analysis: Optional[str] = None

	model_config = ConfigDict(extra='allow')


class JobApplyResponse(BaseModel):
	job_id: str
	application_id: Optional[str] = None
	status: str
	task_id: Optional[str] = None
	message: str


# ============================================================================
# Agents
# ============================================================================


class AgentStatusItem(BaseModel):
	id: str
	name: str
	status: str
	progress: int
	message: str


class AgentListResponse(BaseModel):
	agents: List[AgentStatusItem]


class AgentInvokeResponse(BaseModel):
	agent_id: str
	status: str
	message: str
	task_id: Optional[str] = None


# ============================================================================
# Pipeline
# ============================================================================


class PipelineStatusResponse(BaseModel):
	running: bool
	current_agent: Optional[str] = None
	progress: int = 0
	jobs_found: int = 0
	jobs_applied: int = 0


class PipelineStartResponse(BaseModel):
	status: str
	message: str
	session_id: str
	config: Dict[str, Any]


class PipelineActionResponse(BaseModel):
	status: str
	message: str


class HITLResponse(BaseModel):
	status: str
	hitl_id: str
	message: str


# ============================================================================
# Salary
# ============================================================================


class SalaryResearchResponse(BaseModel):
	"""Salary research results — flexible structure from LLM."""

	success: bool = True

	model_config = ConfigDict(extra='allow')


class SalaryNegotiationResponse(BaseModel):
	"""Negotiation strategy — flexible structure from LLM."""

	success: bool = True

	model_config = ConfigDict(extra='allow')


# ============================================================================
# Tracker
# ============================================================================


class TrackerApplication(BaseModel):
	company: str
	role: Optional[str] = None
	status: Optional[str] = None
	url: Optional[str] = None
	notes: Optional[str] = None

	model_config = ConfigDict(extra='allow')


class TrackerListResponse(BaseModel):
	"""Tracker list — structure varies by agent implementation."""

	model_config = ConfigDict(extra='allow')


class TrackerAddResponse(BaseModel):
	success: bool = True

	model_config = ConfigDict(extra='allow')


class TrackerUpdateResponse(BaseModel):
	success: bool = True

	model_config = ConfigDict(extra='allow')


class TrackerStatsResponse(BaseModel):
	"""Statistics report — flexible structure from agent."""

	model_config = ConfigDict(extra='allow')


# ============================================================================
# User Profile
# ============================================================================


class ProfileResponse(BaseModel):
	profile: Optional[Dict[str, Any]] = None
	message: Optional[str] = None


class ProfileCreateResponse(BaseModel):
	success: bool
	profile_id: Optional[str] = None
	message: Optional[str] = None


class ProfileUpdateResponse(BaseModel):
	success: bool
	message: Optional[str] = None


class ProfileCompletionResponse(BaseModel):
	has_profile: bool = False
	has_education: bool = False
	has_experience: bool = False
	has_projects: bool = False
	has_skills: bool = False
	has_resume: bool = False
	completion_percent: int = 0


class EducationAddResponse(BaseModel):
	success: bool
	education_id: Optional[str] = None


class ExperienceAddResponse(BaseModel):
	success: bool
	experience_id: Optional[str] = None


class ProjectAddResponse(BaseModel):
	success: bool
	project_id: Optional[str] = None


class ResumeUploadResponse(BaseModel):
	success: bool
	resume: Optional[Dict[str, Any]] = None
	parsed_data: Optional[Dict[str, Any]] = None


class ResumeListResponse(BaseModel):
	resumes: List[Dict[str, Any]] = []


class PrimaryResumeResponse(BaseModel):
	resume: Optional[Dict[str, Any]] = None
	message: Optional[str] = None


class GeneratedResumesResponse(BaseModel):
	generated_resumes: List[Dict[str, Any]] = []


# ============================================================================
# Cover Letter
# ============================================================================


class CoverLetterGenerateResponse(BaseModel):
	success: bool = True
	content: Optional[str] = None
	full_text: Optional[str] = None
	structured_content: Optional[Any] = None
	job_title: Optional[str] = None
	company_name: Optional[str] = None
	tone: Optional[str] = None


# ============================================================================
# Resume
# ============================================================================


class ResumeTemplateItem(BaseModel):
	id: str
	name: str
	description: str


class ResumeTemplatesResponse(BaseModel):
	templates: List[ResumeTemplateItem]


class ResumeDownloadResponse(BaseModel):
	url: str


class ResumeTailorResponse(BaseModel):
	"""Resume tailoring result — flexible structure from agent."""

	success: bool = True

	model_config = ConfigDict(extra='allow')


# ============================================================================
# RAG
# ============================================================================


class RAGUploadResponse(BaseModel):
	status: str
	message: str


class RAGQueryResponse(BaseModel):
	results: List[Any] = []


# ============================================================================
# Network
# ============================================================================


class NetworkHealthResponse(BaseModel):
	status: str
	agent: str
	search_engine: Optional[str] = None
	features: Optional[List[str]] = None


# ============================================================================
# LLM Admin
# ============================================================================


class LLMUsageSummary(BaseModel):
	total_invocations: int = 0
	successful: int = 0
	failed: int = 0
	total_input_tokens: int = 0
	total_output_tokens: int = 0
	total_tokens: int = 0
	estimated_cost_usd: float = 0.0
	avg_latency_ms: float = 0.0

	model_config = ConfigDict(extra='allow')


class LLMUsageResponse(BaseModel):
	summary: LLMUsageSummary
	per_agent: Dict[str, Any] = {}
