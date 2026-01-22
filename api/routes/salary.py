"""
Salary Negotiation Routes
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict

from src.agents.salary_agent import salary_agent

router = APIRouter()

class SalaryResearchRequest(BaseModel):
    role: str
    location: str
    experience_years: int = 3

class SalaryNegotiationRequest(BaseModel):
    role: str
    location: str
    current_offer: int
    bonus: int = 0
    equity: int = 0
    experience_years: int = 3
    competing_offers: Optional[List[int]] = None

@router.post("/research")
async def research_salary(request: SalaryResearchRequest):
    """
    Research market salary for a role.
    """
    try:
        result = await salary_agent.research_salary(
            role=request.role,
            location=request.location,
            experience_years=request.experience_years
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/negotiate")
async def negotiate_offer(request: SalaryNegotiationRequest):
    """
    Generate negotiation strategy for an offer.
    """
    try:
        result = await salary_agent.negotiate_offer(
            role=request.role,
            location=request.location,
            current_offer=request.current_offer,
            bonus=request.bonus,
            equity=request.equity,
            experience_years=request.experience_years,
            competing_offers=request.competing_offers
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
