"""
Network API Routes - Find referral connections at target companies

Uses SerpAPI (Google Search) X-Ray search to find LinkedIn profiles of:
- College alumni at target company
- People from same city/location
- Ex-colleagues (shared past employers)

This is safe - no direct LinkedIn scraping, zero ban risk.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from src.agents.network_agent import network_agent
from src.models.profile import UserProfile, NetworkSearchResult
from src.services.user_profile_service import user_profile_service
from src.core.auth import get_current_user, AuthUser, rate_limit_check
from src.core.logger import logger
from src.api.schemas import NetworkHealthResponse


router = APIRouter(prefix="/network", tags=["NetworkAI"])


class NetworkSearchRequest(BaseModel):
    """Request to find networking connections at a company."""
    company: str = Field(..., description="Target company name", example="Google")
    include_alumni: bool = Field(default=True, description="Search for college alumni")
    include_location: bool = Field(default=True, description="Search for people from same city")
    include_past_companies: bool = Field(default=True, description="Search for ex-colleagues")
    generate_outreach: bool = Field(default=True, description="Generate AI outreach messages")
    max_per_category: int = Field(default=5, ge=1, le=10, description="Max results per category")


class NetworkSearchResponse(BaseModel):
    """Response containing networking matches."""
    success: bool
    result: Optional[NetworkSearchResult] = None
    error: Optional[str] = None


@router.post("/find-connections", response_model=NetworkSearchResponse)
async def find_connections(
    request: NetworkSearchRequest,
    user: AuthUser = Depends(rate_limit_check)
) -> NetworkSearchResponse:
    """
    Find networking connections at a target company.
    
    Uses X-Ray search (SerpAPI/Google) to find publicly indexed LinkedIn profiles
    that match the user's network criteria (alumni, location, past employers).
    
    This is SAFE - it searches Google's index, NOT LinkedIn directly.
    Zero risk of LinkedIn account bans.
    
    **How referrals help:**
    - Cold applications: <2% success rate
    - Referred applications: >40% success rate
    - One referral = 100 cold applications
    
    **Connection types:**
    - Alumni: People who went to the same university
    - Location: People from the same city
    - Company: People who worked at the same companies
    
    **Authentication Required:** Yes (JWT Bearer token)
    """
    try:
        # Load user profile from database
        user_profile = await user_profile_service.get_profile(user.id)
        
        if not user_profile:
            raise HTTPException(
                status_code=404, 
                detail="User profile not found. Please complete onboarding first."
            )
        
        logger.info(f"NetworkAI searching connections at {request.company} for user {user.id}")
        
        # Find connections
        result = await network_agent.find_connections(
            company=request.company,
            user_profile=user_profile,
            include_alumni=request.include_alumni,
            include_location=request.include_location,
            include_past_companies=request.include_past_companies,
            generate_outreach=request.generate_outreach,
            max_per_category=request.max_per_category,
        )
        
        # Persist results to database (The "Warmth" Persistence)
        from src.services.network_service import network_service
        
        all_matches = (
            result.alumni_matches + 
            result.location_matches + 
            result.company_matches
        )
        
        saved_count = 0
        for match in all_matches:
            # Propagate company name if missing in match
            if not match.company_match and result.company:
                 match.company_match = result.company
                 
            await network_service.save_lead(user.id, match)
            saved_count += 1
            
        logger.info(f"Persisted {saved_count} network leads for user {user.id}")
        
        return NetworkSearchResponse(success=True, result=result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Network search failed for user {user.id}: {e}")
        return NetworkSearchResponse(success=False, error=str(e))


@router.get("/health", response_model=NetworkHealthResponse)
async def health_check():
    """Check if NetworkAI agent is ready."""
    return {
        "status": "healthy",
        "agent": "NetworkAI",
        "search_engine": "SerpAPI (Google)",
        "features": [
            "Alumni search",
            "Location-based search",
            "Past employer search",
            "AI outreach generation"
        ]
    }
