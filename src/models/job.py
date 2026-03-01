from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class JobAnalysis(BaseModel):
	"""
	Structured output from the Analyst Agent.
	"""

	role: str = Field(..., description='The job title')
	company: str = Field(..., description='The company name')
	match_score: int = Field(..., description='Match score between 0 and 100')
	matching_skills: List[str] = Field(default_factory=list, description='Skills present in resume and job description')
	missing_skills: List[str] = Field(default_factory=list, description='Skills required but missing in resume')
	tech_stack: List[str] = Field(default_factory=list, description='Technologies required for the job')
	gap_analysis_advice: Optional[str] = Field(default=None, description='Actionable advice to improve match score')
	salary: Optional[str] = Field(default=None, description='Salary range if available')
	reasoning: Optional[str] = Field(default='No reasoning provided', description='Explanation for the match score')
	analysis: Optional[str] = Field(default=None, description='Detailed analysis of the job match')

	model_config = ConfigDict(extra='ignore')


class JobApplication(BaseModel):
	"""
	Tracking model for a job application status.
	"""

	job_url: str
	role: str
	company: str
	status: str = 'pending'  # pending, applied, failed
	notes: Optional[str] = None
	last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())

	model_config = ConfigDict(extra='ignore')
	error_message: Optional[str] = None
