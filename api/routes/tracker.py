"""
Job Tracker Routes
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

from src.agents.tracker_agent import job_tracker_agent

router = APIRouter()

class ApplicationCreate(BaseModel):
    company: str
    role: str
    url: Optional[str] = ""
    salary_range: Optional[str] = ""
    priority: Optional[str] = "Medium"
    notes: Optional[str] = ""
    proof_screenshot: Optional[str] = None # Base64 string

class ApplicationUpdate(BaseModel):
    status: str
    next_step: Optional[str] = ""
    notes: Optional[str] = ""

@router.get("/")
async def get_applications(status: Optional[str] = None):
    """Get all tracked applications."""
    try:
        result = await job_tracker_agent.run(action='list', status=status)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/")
async def add_application(app: ApplicationCreate):
    """Track a new application."""
    try:
        # Note: Tracker agent needs update to accept proof_screenshot if we want to store it
        # For now we'll put it in notes or handle it separately.
        # Let's assume we update the agent logic or just pass it through if possible.
        # Ideally, we save the image to disk and store the path.
        
        # Simple storage for now
        if app.proof_screenshot:
            # In a real app, decode base64 and save to file storage
            # For this MVP, we might truncate it or store as is (heavy!)
            # Better to store "Has Proof" flag and save image separately.
            pass

        result = await job_tracker_agent.add_application(
            company=app.company,
            role=app.role,
            url=app.url,
            salary_range=app.salary_range,
            notes=app.notes,
            priority=app.priority
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{company}")
async def update_status(company: str, update: ApplicationUpdate, background_tasks: BackgroundTasks):
    """
    Update application status.
    Triggers automation if moving to 'Interview'.
    """
    try:
        # Perform update
        result = await job_tracker_agent.update_status(
            company=company,
            new_status=update.status,
            next_step=update.next_step,
            notes=update.notes
        )
        
        # Automation: Trigger Interview Prep
        if update.status.lower() == "interview":
            background_tasks.add_task(trigger_interview_prep, company)
            
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_tracker_stats():
    """Get statistics report."""
    try:
        result = await job_tracker_agent.get_report()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def trigger_interview_prep(company: str):
    """Background task to generate interview prep when status changes."""
    print(f"🤖 Auto-generating interview prep for {company}...")
    try:
        from src.agents.interview_agent import interview_agent
        await interview_agent.quick_prep(
            role="Software Engineer", # Ideal: fetch from tracker
            company=company,
            tech_stack=["General"] 
        )
        print(f"✅ Interview prep generated for {company}")
    except Exception as e:
        print(f"❌ Failed to auto-generate prep: {e}")
