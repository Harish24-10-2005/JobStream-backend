"""
Interview Prep Routes
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict

from src.agents.interview_agent import interview_agent

router = APIRouter()

class InterviewPrepRequest(BaseModel):
    role: str
    company: str
    tech_stack: List[str]

class InterviewPrepResponse(BaseModel):
    success: bool
    analysis: Dict
    resources: Dict
    behavioral_questions: Dict
    technical_questions: Dict
    error: Optional[str] = None

@router.post("/prep", response_model=InterviewPrepResponse)
async def prepare_interview(request: InterviewPrepRequest):
    """
    Generate interview preparation materials.
    """
    try:
        result = await interview_agent.quick_prep(
            role=request.role,
            company=request.company,
            tech_stack=request.tech_stack
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
