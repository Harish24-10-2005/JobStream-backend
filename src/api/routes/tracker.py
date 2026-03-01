"""
Job Tracker Routes
"""

from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from src.agents.tracker_agent import JobTrackerAgent
from src.api.schemas import TrackerAddResponse, TrackerStatsResponse, TrackerUpdateResponse
from src.core.auth import AuthUser, get_current_user

router = APIRouter()


class ApplicationCreate(BaseModel):
	company: str
	role: str
	url: Optional[str] = ''
	salary_range: Optional[str] = ''
	priority: Optional[str] = 'Medium'
	notes: Optional[str] = ''
	proof_screenshot: Optional[str] = None  # Base64 string


class ApplicationUpdate(BaseModel):
	status: str
	next_step: Optional[str] = ''
	notes: Optional[str] = ''


@router.get('/')
async def get_applications(user: Annotated[AuthUser, Depends(get_current_user)], status: Optional[str] = None):
	"""Get all tracked applications for the authenticated user."""
	try:
		agent = JobTrackerAgent(user.id)
		result = await agent.run(action='list', status=status)
		return result
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.post('/', response_model=TrackerAddResponse)
async def add_application(app: ApplicationCreate, user: Annotated[AuthUser, Depends(get_current_user)]):
	"""Track a new application for the authenticated user."""
	try:
		# Note: Tracker agent needs update to accept proof_screenshot if we want to store it
		# For now we'll put it in notes or handle it separately.

		agent = JobTrackerAgent(user.id)
		result = await agent.add_application(
			company=app.company, role=app.role, url=app.url, salary_range=app.salary_range, notes=app.notes, priority=app.priority
		)
		return result
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.patch('/{company}', response_model=TrackerUpdateResponse)
async def update_status(
	company: str, update: ApplicationUpdate, background_tasks: BackgroundTasks, user: Annotated[AuthUser, Depends(get_current_user)]
):
	"""
	Update application status.
	Triggers automation if moving to 'Interview'.
	"""
	try:
		agent = JobTrackerAgent(user.id)
		# Perform update
		result = await agent.update_status(
			company=company, new_status=update.status, next_step=update.next_step, notes=update.notes
		)

		# Automation: Trigger Interview Prep
		if update.status.lower() == 'interview':
			background_tasks.add_task(trigger_interview_prep, company, user.id)

		return result
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get('/stats', response_model=TrackerStatsResponse)
async def get_tracker_stats(user: Annotated[AuthUser, Depends(get_current_user)]):
	"""Get statistics report for the authenticated user."""
	try:
		agent = JobTrackerAgent(user.id)
		result = await agent.get_report()
		return result
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


async def trigger_interview_prep(company: str, user_id: str):
	"""Background task to generate interview prep when status changes."""
	print(f'🤖 Auto-generating interview prep for {company} (User: {user_id})...')
	try:
		from src.agents import get_interview_agent
		interview_agent = get_interview_agent()
		await interview_agent.quick_prep(role='Software Engineer', company=company, tech_stack=['General'])
		print(f'✅ Interview prep generated for {company}')
	except Exception as e:
		print(f'❌ Failed to auto-generate prep: {e}')
