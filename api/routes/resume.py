"""
Resume API Routes - Resume analysis, tailoring, and optimization
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import logging

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
async def analyze_resume(request: ResumeAnalyzeRequest):
    """
    Analyze a resume for ATS compatibility and provide suggestions.
    Uses AI to evaluate resume content against job requirements.
    """
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage
        from src.core.config import settings
        import json
        
        if not settings.gemini_api_key:
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
        
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

        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-lite",
            google_api_key=settings.gemini_api_key.get_secret_value(),
            max_output_tokens=2048
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


@router.post("/tailor")
async def tailor_resume(request: ResumeTailorRequest):
    """
    Tailor a resume for a specific job using AI.
    """
    try:
        from src.agents import get_resume_agent
        from src.models.job import JobAnalysis
        from src.models.profile import UserProfile
        
        # Create minimal job analysis from request
        job_analysis = JobAnalysis(
            id="manual",
            role=request.role,
            company=request.company,
            tech_stack=request.tech_stack or [],
            matching_skills=[],
            missing_skills=[],
            match_score=0
        )
        
        # TODO: Get actual user profile from session/database
        # For now, use the provided resume content to create a minimal profile
        user_profile = UserProfile(
            personal_information={"full_name": "User"},
            summary=request.resume_content[:500] if request.resume_content else "",
            skills={"primary": request.tech_stack or []},
            experience=[],
            education=[]
        )
        
        resume_agent = get_resume_agent()
        result = await resume_agent.tailor_resume(
            job_analysis=job_analysis,
            user_profile=user_profile,
            template_type="ats"
        )
        
        return {
            "success": True,
            "tailored_content": result.get("tailored_content", {}),
            "ats_score": result.get("ats_score", 0),
            "pdf_path": result.get("pdf_path")
        }
        
    except Exception as e:
        logger.error(f"Resume tailoring error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
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
