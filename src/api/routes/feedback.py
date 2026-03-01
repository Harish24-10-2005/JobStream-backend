"""
Feedback API Routes — User Feedback Loop for Agent Learning

Allows users to rate agent outputs (resumes, cover letters, interviews)
and report application outcomes. Feedback feeds back into the Agent
Memory system to improve future generations.
"""

from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.core.agent_memory import agent_memory
from src.core.auth import AuthUser, get_current_user

router = APIRouter()


# ── Request Models ──────────────────────────────────────────────


class FeedbackRequest(BaseModel):
	"""Base feedback model for all agent outputs."""

	rating: float = Field(..., ge=1.0, le=5.0, description='Rating from 1 to 5')
	comments: str = Field('', max_length=2000, description='Optional feedback text')
	session_id: str = Field('', description='Session that produced the output')
	context: Dict[str, Any] = Field(default_factory=dict, description='Extra context')


class ResumeFeedbackRequest(FeedbackRequest):
	job_title: str = Field('', description='Job the resume was tailored for')
	what_worked: str = Field('', description='What the user liked')
	what_didnt: str = Field('', description='What needs improvement')


class ApplicationOutcomeRequest(BaseModel):
	"""Report the outcome of a job application."""

	job_id: str = Field('', description='Job ID from the system')
	company: str = Field('', description='Company name')
	outcome: str = Field(..., description='interview_scheduled, rejected, offer_received, ghosted, withdrawn')
	notes: str = Field('', max_length=2000)


# ── Feedback Endpoints ──────────────────────────────────────────


@router.post('/resume')
async def submit_resume_feedback(
	req: ResumeFeedbackRequest,
	user: Annotated[AuthUser, Depends(get_current_user)],
):
	"""Rate a generated resume. Helps the Resume Agent improve."""
	context = {
		**req.context,
		'job_title': req.job_title,
		'what_worked': req.what_worked,
		'what_didnt': req.what_didnt,
	}
	success = await agent_memory.record_feedback(
		agent_name='resume_agent',
		user_id=user.id,
		session_id=req.session_id,
		rating=req.rating,
		comments=req.comments,
		context=context,
	)

	# Store specific learnings if the user gave detailed feedback
	if req.what_worked:
		await agent_memory.remember(
			'resume_agent',
			user.id,
			f'liked:{req.job_title or "general"}',
			req.what_worked,
			memory_type='learning',
		)

	return {
		'status': 'recorded',
		'message': 'Thanks for the feedback — the Resume Agent will use this to improve.',
	}


@router.post('/cover-letter')
async def submit_cover_letter_feedback(
	req: FeedbackRequest,
	user: Annotated[AuthUser, Depends(get_current_user)],
):
	"""Rate a generated cover letter."""
	await agent_memory.record_feedback(
		agent_name='cover_letter_agent',
		user_id=user.id,
		session_id=req.session_id,
		rating=req.rating,
		comments=req.comments,
		context=req.context,
	)
	return {'status': 'recorded', 'message': 'Cover letter feedback saved.'}


@router.post('/interview')
async def submit_interview_feedback(
	req: FeedbackRequest,
	user: Annotated[AuthUser, Depends(get_current_user)],
):
	"""Rate interview prep quality."""
	await agent_memory.record_feedback(
		agent_name='interview_agent',
		user_id=user.id,
		session_id=req.session_id,
		rating=req.rating,
		comments=req.comments,
		context=req.context,
	)
	return {'status': 'recorded', 'message': 'Interview prep feedback saved.'}


@router.post('/application-outcome')
async def report_application_outcome(
	req: ApplicationOutcomeRequest,
	user: Annotated[AuthUser, Depends(get_current_user)],
):
	"""
	Report the outcome of a job application.

	Helps the system learn which application strategies work.
	"""
	# Store as a memory for the relevant agents
	outcome_data = {
		'job_id': req.job_id,
		'company': req.company,
		'outcome': req.outcome,
		'notes': req.notes,
	}

	# Multiple agents can learn from outcomes
	for agent in ['scout_agent', 'analyst_agent', 'resume_agent', 'cover_letter_agent']:
		await agent_memory.remember(
			agent,
			user.id,
			f'outcome:{req.company}:{req.outcome}',
			outcome_data,
		)

	return {
		'status': 'recorded',
		'message': f"Outcome '{req.outcome}' recorded. This helps improve future applications.",
	}


@router.get('/summary/{agent_name}')
async def get_feedback_summary(
	agent_name: str,
	user: Annotated[AuthUser, Depends(get_current_user)],
):
	"""Get feedback summary for a specific agent."""
	valid_agents = [
		'resume_agent',
		'cover_letter_agent',
		'interview_agent',
		'company_agent',
		'scout_agent',
	]
	if agent_name not in valid_agents:
		raise HTTPException(400, f'Unknown agent. Valid: {valid_agents}')

	summary = await agent_memory.get_feedback_summary(agent_name, user.id)
	return {'agent': agent_name, 'feedback': summary}
