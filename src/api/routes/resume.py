"""
Resume API Routes - Resume analysis, tailoring, and optimization
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from src.core.auth import get_current_user, AuthUser
from src.services.user_profile_service import user_profile_service
from src.services.resume_storage_service import resume_storage_service
from src.agents import get_resume_agent
from src.models.job import JobAnalysis
from src.models.profile import UserProfile, PersonalInfo, Location, Urls, Files
from src.api.schemas import ResumeTailorResponse, ResumeDownloadResponse, ResumeTemplatesResponse

router = APIRouter()
logger = logging.getLogger(__name__)


class ResumeAnalyzeRequest(BaseModel):
    content: Optional[str] = None  # Resume text content
    job_description: Optional[str] = None  # Optional job to match against
    role: Optional[str] = None
    company: Optional[str] = None


class ATSSuggestion(BaseModel):
    type: str  # improvement, keyword, format
    text: str
    priority: str  # high, medium, low


class ATSMetrics(BaseModel):
    keywords_found: int
    keywords_total: int
    format_status: str  # Good, Fair, Poor
    length_status: str  # Good, Long, Short
    contact_complete: bool


class ResumeAnalyzeResponse(BaseModel):
    success: bool
    ats_score: int
    metrics: ATSMetrics
    suggestions: List[ATSSuggestion]
    matched_keywords: List[str]
    missing_keywords: List[str]


class ResumeTailorRequest(BaseModel):
    resume_content: str
    job_description: str
    role: str
    company: str
    tech_stack: Optional[List[str]] = []


@router.post("/analyze", response_model=ResumeAnalyzeResponse)
async def analyze_resume(
    request: ResumeAnalyzeRequest,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Analyze a resume for ATS compatibility and provide suggestions.
    Uses AI to evaluate resume content against job requirements.
    """
    try:
        from langchain_groq import ChatGroq
        from langchain_core.messages import HumanMessage
        from src.core.config import settings
        import json
        
        if not settings.groq_api_key:
            raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")
        
        # Build the analysis prompt
        resume_text = request.content or ""
        job_context = ""
        if request.job_description:
            job_context = f"\n\nJob Description:\n{request.job_description}"
        elif request.role and request.company:
            job_context = f"\n\nTarget Role: {request.role} at {request.company}"
        
        prompt = f"""Analyze this resume for ATS (Applicant Tracking System) compatibility.
{job_context}

Resume Content:
{resume_text if resume_text else "No resume content provided - analyze for general best practices"}

Provide a JSON response with:
{{
    "ats_score": <integer 0-100>,
    "keywords_found": <number of relevant keywords found>,
    "keywords_total": <estimated total keywords needed>,
    "format_status": "Good" | "Fair" | "Poor",
    "length_status": "Good" | "Long" | "Short",
    "contact_complete": true | false,
    "matched_keywords": ["keyword1", "keyword2", ...],
    "missing_keywords": ["keyword1", "keyword2", ...],
    "suggestions": [
        {{"type": "improvement" | "keyword" | "format", "text": "suggestion text", "priority": "high" | "medium" | "low"}}
    ]
}}

Be specific and actionable with suggestions. Focus on real improvements."""

        llm = ChatGroq(
            model="llama-3.1-8b-instant",
            api_key=settings.groq_api_key.get_secret_value(),
            max_tokens=2048
        )
        
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        
        # Parse the response
        response_text = response.content
        
        # Extract JSON from response
        import re
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            result = json.loads(json_match.group())
        else:
            # Default response if parsing fails
            result = {
                "ats_score": 65,
                "keywords_found": 8,
                "keywords_total": 15,
                "format_status": "Fair",
                "length_status": "Good",
                "contact_complete": True,
                "matched_keywords": [],
                "missing_keywords": [],
                "suggestions": [
                    {"type": "improvement", "text": "Add quantifiable achievements to your experience section", "priority": "high"},
                    {"type": "keyword", "text": "Include more industry-specific keywords", "priority": "medium"},
                    {"type": "format", "text": "Use bullet points for better readability", "priority": "low"}
                ]
            }
        
        return ResumeAnalyzeResponse(
            success=True,
            ats_score=result.get("ats_score", 70),
            metrics=ATSMetrics(
                keywords_found=result.get("keywords_found", 10),
                keywords_total=result.get("keywords_total", 15),
                format_status=result.get("format_status", "Good"),
                length_status=result.get("length_status", "Good"),
                contact_complete=result.get("contact_complete", True)
            ),
            suggestions=[
                ATSSuggestion(**s) for s in result.get("suggestions", [])
            ],
            matched_keywords=result.get("matched_keywords", []),
            missing_keywords=result.get("missing_keywords", [])
        )
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        # Return default analysis
        return ResumeAnalyzeResponse(
            success=True,
            ats_score=70,
            metrics=ATSMetrics(
                keywords_found=10,
                keywords_total=15,
                format_status="Good",
                length_status="Good",
                contact_complete=True
            ),
            suggestions=[
                ATSSuggestion(type="improvement", text="Add quantifiable achievements", priority="high"),
                ATSSuggestion(type="keyword", text="Include more industry keywords", priority="medium"),
                ATSSuggestion(type="format", text="Consider using bullet points", priority="low")
            ],
            matched_keywords=[],
            missing_keywords=[]
        )
    except Exception as e:
        logger.error(f"Resume analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tailor", response_model=ResumeTailorResponse)
async def tailor_resume(
    request: ResumeTailorRequest,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Tailor a resume for a specific job using AI.
    Requires authentication.
    """
    try:
        user_id = current_user.id
        
        # 1. Fetch User Profile
        user_profile = await user_profile_service.get_profile(user_id)
        if not user_profile:
            # If no profile, create a minimal placeholder profile from provided resume content
            if request.resume_content:
                user_profile = UserProfile(
                    id=user_id,
                    user_id=user_id,
                    personal_information=PersonalInfo(
                        first_name="User",
                        last_name="",
                        full_name="User",
                        email="",
                        phone="",
                        location=Location(city="", country="", address=""),
                        urls=Urls(),
                        summary=request.resume_content[:500]
                    ),
                    education=[],
                    experience=[],
                    projects=[],
                    skills={"primary": request.tech_stack or []},
                    files=Files(resume="uploaded")
                )
            else:
                raise HTTPException(status_code=404, detail="User profile not found. Please complete profile first.")
        
        # 2. Prepare Job Analysis
        job_analysis = JobAnalysis(
            id="manual", # No specific job ID for manual entry
            role=request.role,
            company=request.company,
            tech_stack=request.tech_stack or [],
            matching_skills=[],
            missing_skills=[],
            match_score=0
        )
        
        # 3. Run Resume Agent (Handles RAG + Persistence internally)
        resume_agent = get_resume_agent()
        result = await resume_agent.tailor_resume(
            job_analysis=job_analysis,
            user_profile=user_profile,
            template_type="ats"
        )
        
        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])
            
        return result
        
    except Exception as e:
        logger.error(f"Resume tailoring error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=List[Any])
async def get_resume_history(
    limit: int = 20,
    current_user: AuthUser = Depends(get_current_user)
):
    """Get history of generated resumes."""
    return await resume_storage_service.get_generated_resumes(current_user.id, limit)


@router.get("/download/{resume_id}", response_model=ResumeDownloadResponse)
async def download_resume(
    resume_id: str,
    current_user: AuthUser = Depends(get_current_user)
):
    """Get download URL for a generated resume."""
    # Since get_generated_resumes returns metadata including URL, we can use that logic
    # Or iterate to find it. But we don't have a direct 'get_generated_resume(id)' method exposed yet efficiently
    # aside from listing.
    # Let's add a quick hack or assume frontend has the URL from list.
    # If we need secure download link generation:
    resumes = await resume_storage_service.get_generated_resumes(current_user.id, 100)
    for r in resumes:
        if str(r.id) == resume_id:
            return {"url": r.pdf_url}
    raise HTTPException(status_code=404, detail="Resume not found")


@router.get("/templates", response_model=ResumeTemplatesResponse)
async def get_resume_templates():
    """
    Get available resume templates.
    """
    return {
        "templates": [
            {"id": "ats", "name": "ATS Optimized", "description": "Clean, ATS-friendly format"},
            {"id": "modern", "name": "Modern", "description": "Contemporary design with subtle styling"},
            {"id": "minimal", "name": "Minimal", "description": "Simple and elegant layout"}
        ]
    }
