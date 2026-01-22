"""
Company Research Routes
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict

from src.agents.company_agent import company_agent

router = APIRouter()

class CompanyResearchRequest(BaseModel):
    company: str
    role: Optional[str] = ""
    job_description: Optional[str] = ""

class CompanyResearchResponse(BaseModel):
    success: bool
    company: str
    company_info: Dict
    culture_analysis: Dict
    red_flags: Dict
    interview_insights: Dict
    error: Optional[str] = None

@router.post("/research", response_model=CompanyResearchResponse)
async def research_company(request: CompanyResearchRequest):
    """
    Research a company deeply.
    """
    try:
        result = await company_agent.research_company(
            company=request.company,
            role=request.role,
            job_description=request.job_description
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/quick-check")
async def quick_check_company(request: CompanyResearchRequest):
    """
    Quick check for company basic info and red flags.
    """
    try:
        result = await company_agent.quick_check(company=request.company)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
