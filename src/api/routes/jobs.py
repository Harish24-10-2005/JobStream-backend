"""
Jobs API Routes - Production Ready
Connects to Supabase for real data persistence
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
import logging

from src.services.db_service import db_service
from src.core.auth import get_current_user, AuthUser
from src.api.schemas import JobSearchResponse, JobAnalyzeResponse, JobApplyResponse

logger = logging.getLogger(__name__)

router = APIRouter()


class JobSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    location: str = Field(default="Remote", max_length=100)
    platforms: List[str] = Field(default=["greenhouse", "lever", "ashby"])
    min_match_score: int = Field(default=70, ge=0, le=100)


class JobResponse(BaseModel):
    id: str
    title: str
    company: str
    location: str
    url: str
    match_score: int = 0
    platform: Optional[str] = None
    salary: Optional[str] = None
    tech_stack: Optional[List[str]] = None
    matching_skills: Optional[List[str]] = None
    missing_skills: Optional[List[str]] = None


@router.post("/search", response_model=JobSearchResponse)
async def search_jobs(
    request: JobSearchRequest,
    user: AuthUser = Depends(get_current_user)
):
    """
    Start a job search using the Scout Agent.
    Results are saved to database automatically.
    """
    try:
        from src.automators.scout import ScoutAgent
        
        scout = ScoutAgent()
        results = await scout.run(request.query, request.location)
        
        # Persist discovered jobs
        saved_jobs = []
        seen = set()
        for url in results:
            if url in seen:
                continue
            seen.add(url)
            job_id = db_service.save_discovered_job(
                url=url,
                title="Unknown",
                company="Unknown",
                location=request.location or "Remote",
                source="scout",
                user_id=user.id
            )
            if job_id:
                saved_jobs.append({"id": job_id, "url": url})
        
        logger.info(f"Job search completed: {len(results)} results for '{request.query}' ({len(saved_jobs)} saved)")
        
        return {
            "status": "success",
            "query": request.query,
            "location": request.location,
            "jobs": saved_jobs,
            "total": len(saved_jobs),
        }
    except Exception as e:
        logger.error(f"Job search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results")
async def get_job_results(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    min_score: Optional[int] = Query(default=None, ge=0, le=100),
    source: Optional[str] = Query(default=None),
    user: AuthUser = Depends(get_current_user),
):
    """
    Get job search results from database with optional filtering.
    
    Args:
        limit: Max results (1-100)
        offset: Pagination offset
        min_score: Minimum match score filter
        source: Filter by source (scout, manual)
    """
    try:
        result = db_service.get_jobs_with_analyses(
            limit=limit,
            offset=offset,
            min_score=min_score,
            source=source,
            user_id=user.id
        )
        
        if "error" in result:
            logger.warning(f"Database query warning: {result['error']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get job results: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve jobs")


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """
    Get a specific job with its analysis.
    """
    job = db_service.get_job_with_analysis(job_id, user_id=user.id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job


@router.post("/analyze/{job_id}", response_model=JobAnalyzeResponse)
async def analyze_job(
    job_id: str,
    user: AuthUser = Depends(get_current_user)
):
    """
    Analyze a specific job using the Analyst Agent.
    Returns existing analysis if available, or triggers new analysis.
    """
    try:
        # Check if job exists
        job = db_service.get_job_by_id(job_id, user_id=user.id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Check for existing analysis
        existing_analysis = db_service.get_analysis_by_job_id(job_id)
        if existing_analysis:
            return {
                "job_id": job_id,
                "status": "analyzed",
                "cached": True,
                **existing_analysis
            }
        
        # Run new analysis
        from src.automators.analyst import AnalystAgent
        
        analyst = AnalystAgent()
        analysis = await analyst.analyze_job(job["url"])
        
        return {
            "job_id": job_id,
            "status": "analyzed",
            "cached": False,
            **analysis
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Job analysis failed for {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply/{job_id}", response_model=JobApplyResponse)
async def apply_to_job(
    job_id: str, 
    trigger_agent: bool = Query(default=False),
    user: AuthUser = Depends(get_current_user)
):
    """
    Queue a job application.
    
    Args:
        job_id: The ID of the job to apply to
        trigger_agent: If True, triggers the live browser agent task
        user: Authenticated user (Auto-injected)
    """
    try:
        # Check if job exists
        job = db_service.get_job_with_analysis(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Check if already applied
        existing_app = db_service.get_application_by_job_id(job_id)
        if existing_app:
            return {
                "job_id": job_id,
                "status": existing_app.get("status", "unknown"),
                "message": "Application already exists",
                "application_id": existing_app.get("id")
            }
        
        # Create pending application
        analysis_id = job.get("analysis", {}).get("id") if job.get("analysis") else None
        app_id = db_service.save_application(
            job_id=job_id,
            analysis_id=analysis_id,
            status="queued" if trigger_agent else "pending"
        )
        
        task_id = None
        if trigger_agent:
            # Queue task in Celery
            try:
                from src.worker.tasks.applier_task import apply_to_job as apply_task
                from src.core.config import settings
                
                # Use a dummy session ID for API-triggered tasks if no WebSocket attached
                session_id = f"api_trigger_{app_id}"
                
                task = apply_task.delay(
                    job_url=job["url"],
                    session_id=session_id,
                    draft_mode=True, # Safety default
                    redis_url=settings.redis_url,
                    user_id=user.id
                )
                task_id = task.id
                logger.info(f"Applier task queued: {task_id} for app {app_id}")
            except Exception as e:
                logger.error(f"Failed to queue applier task: {e}")
                # Don't fail the request, just warn
                
        
        logger.info(f"Application saved: {app_id} for job {job_id}")
        
        return {
            "job_id": job_id,
            "application_id": app_id,
            "status": "queued" if task_id else "pending",
            "task_id": task_id,
            "message": "Application queued for processing" if task_id else "Application saved as pending",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to queue application for {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
