"""
Cover Letter API Routes - Generation and Management
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

from src.core.auth import get_current_user, AuthUser
from src.services.user_profile_service import user_profile_service
from src.services.resume_storage_service import resume_storage_service
from src.agents import get_cover_letter_agent
from src.models.job import JobAnalysis
from src.models.profile import UserProfile

router = APIRouter()
logger = logging.getLogger(__name__)


class CoverLetterRequest(BaseModel):
    role: str
    company: str
    tech_stack: List[str] = []
    tone: str = "professional"  # professional, enthusiastic, formal, casual
    job_description: Optional[str] = None


@router.post("/generate")
async def generate_cover_letter(
    request: CoverLetterRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate a personalized cover letter.
    """
    try:
        user_id = current_user["id"]
        
        # 1. Fetch Profile
        user_profile = await user_profile_service.get_profile(user_id)
        if not user_profile:
            # Fallback if profile doesn't exist yet (edge case)
            raise HTTPException(status_code=404, detail="User profile required. Please complete onboard.")
            
        # 2. Prepare Job Analysis
        job_analysis = JobAnalysis(
            id="manual",
            role=request.role,
            company=request.company,
            tech_stack=request.tech_stack or [],
            matching_skills=[],
            missing_skills=[],
            match_score=0
        )
        
        # 3. Run Agent (Handles RAG + Persistence)
        agent = get_cover_letter_agent()
        result = await agent.run(
            job_analysis=job_analysis,
            user_profile=user_profile,
            tone=request.tone
        )
        
        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])
            
        return result
        
    except Exception as e:
        logger.error(f"Cover letter generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=List[Dict[str, Any]])
async def get_cover_letter_history(
    limit: int = 20,
    current_user: dict = Depends(get_current_user)
):
    """Get history of generated cover letters."""
    return await resume_storage_service.get_cover_letters(current_user["id"], limit)


@router.get("/{letter_id}")
async def get_cover_letter(
    letter_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get specific cover letter details."""
    letter = await resume_storage_service.get_cover_letter(current_user["id"], letter_id)
    if not letter:
        raise HTTPException(status_code=404, detail="Cover letter not found")
    return letter
