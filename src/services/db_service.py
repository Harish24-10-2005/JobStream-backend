"""
Database Service - Persistence layer for job tracking
Handles saving jobs, analyses, applications to Supabase
Production-ready with multi-user scoping, query methods, and proper error handling
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
import logging

from src.services.supabase_client import supabase_client
from src.core.console import console

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    Service for persisting job search data to Supabase.
    Production-ready with multi-user data isolation, query methods, pagination, and logging.
    
    All methods accept optional user_id for multi-tenant data isolation.
    When user_id is provided, data is scoped to that user only.
    """
    
    # ============================================
    # Query Methods
    # ============================================
    
    def get_discovered_jobs(
        self,
        limit: int = 20,
        offset: int = 0,
        source: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get discovered jobs with pagination, scoped to user.
        
        Args:
            limit: Max results to return
            offset: Pagination offset
            source: Filter by source (scout, manual)
            user_id: User ID for data isolation
            
        Returns:
            Dict with jobs list and total count
        """
        try:
            query = supabase_client.table("discovered_jobs").select("*", count="exact")
            
            if user_id:
                query = query.eq("user_id", user_id)
            if source:
                query = query.eq("source", source)
            
            query = query.order("discovered_at", desc=True)
            query = query.range(offset, offset + limit - 1)
            
            result = query.execute()
            
            return {
                "jobs": result.data or [],
                "total": result.count or 0,
                "offset": offset,
                "limit": limit
            }
            
        except Exception as e:
            logger.error(f"Failed to get discovered jobs: {e}")
            return {"jobs": [], "total": 0, "offset": offset, "limit": limit, "error": str(e)}
    
    def get_job_by_id(self, job_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
        """Get a single job by ID, optionally scoped to user."""
        try:
            query = supabase_client.table("discovered_jobs").select("*").eq("id", job_id)
            if user_id:
                query = query.eq("user_id", user_id)
            result = query.single().execute()
            return result.data
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None
    
    def get_job_with_analysis(self, job_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
        """
        Get a job with its analysis data.
        
        Args:
            job_id: Job UUID
            user_id: User ID for data isolation
            
        Returns:
            Job with analysis or None
        """
        try:
            # Get job
            query = supabase_client.table("discovered_jobs").select("*").eq("id", job_id)
            if user_id:
                query = query.eq("user_id", user_id)
            job_result = query.single().execute()
            
            if not job_result.data:
                return None
            
            job = job_result.data
            
            # Get analysis
            analysis_result = supabase_client.table("job_analyses").select("*").eq("job_id", job_id).order("analyzed_at", desc=True).limit(1).execute()
            
            if analysis_result.data:
                job["analysis"] = analysis_result.data[0]
                job["match_score"] = job["analysis"].get("match_score", 0)
            else:
                job["match_score"] = 0
            
            return job
            
        except Exception as e:
            logger.error(f"Failed to get job with analysis {job_id}: {e}")
            return None
    
    def get_jobs_with_analyses(
        self,
        limit: int = 20,
        offset: int = 0,
        min_score: Optional[int] = None,
        source: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get jobs with their analysis data, scoped to user.
        
        Args:
            limit: Max results
            offset: Pagination offset
            min_score: Minimum match score filter
            source: Source filter
            user_id: User ID for data isolation
            
        Returns:
            Dict with jobs and total
        """
        try:
            # Get jobs
            query = supabase_client.table("discovered_jobs").select("*", count="exact")
            
            if user_id:
                query = query.eq("user_id", user_id)
            if source:
                query = query.eq("source", source)
            
            query = query.order("discovered_at", desc=True)
            query = query.range(offset, offset + limit - 1)
            
            jobs_result = query.execute()
            
            jobs = []
            for job in (jobs_result.data or []):
                # Get latest analysis for this job
                analysis_result = supabase_client.table("job_analyses").select("*").eq("job_id", job["id"]).order("analyzed_at", desc=True).limit(1).execute()
                
                if analysis_result.data:
                    job["analysis"] = analysis_result.data[0]
                    job["match_score"] = job["analysis"].get("match_score", 0)
                    job["tech_stack"] = job["analysis"].get("tech_stack", [])
                    job["matching_skills"] = job["analysis"].get("matching_skills", [])
                    job["missing_skills"] = job["analysis"].get("missing_skills", [])
                else:
                    job["match_score"] = 0
                
                # Filter by min_score if specified
                if min_score and job["match_score"] < min_score:
                    continue
                    
                jobs.append(job)
            
            return {
                "jobs": jobs,
                "total": jobs_result.count or 0,
                "offset": offset,
                "limit": limit
            }
            
        except Exception as e:
            logger.error(f"Failed to get jobs with analyses: {e}")
            return {"jobs": [], "total": 0, "offset": offset, "limit": limit, "error": str(e)}
    
    def get_analysis_by_job_id(self, job_id: str) -> Optional[Dict]:
        """Get latest analysis for a job."""
        try:
            result = supabase_client.table("job_analyses").select("*").eq("job_id", job_id).order("analyzed_at", desc=True).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to get analysis for job {job_id}: {e}")
            return None
    
    def get_application_by_job_id(self, job_id: str) -> Optional[Dict]:
        """Get application for a job."""
        try:
            result = supabase_client.table("applications").select("*").eq("job_id", job_id).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to get application for job {job_id}: {e}")
            return None
    
    def search_jobs(
        self,
        query: str = "",
        location: str = "",
        limit: int = 20
    ) -> List[Dict]:
        """Search jobs by title/company and location."""
        try:
            db_query = supabase_client.table("discovered_jobs").select("*")
            
            if query:
                # Search in title and company (case-insensitive)
                db_query = db_query.or_(f"title.ilike.%{query}%,company.ilike.%{query}%")
            
            if location and location.lower() != "remote":
                db_query = db_query.ilike("location", f"%{location}%")
            
            db_query = db_query.order("discovered_at", desc=True).limit(limit)
            
            result = db_query.execute()
            return result.data or []
            
        except Exception as e:
            logger.error(f"Failed to search jobs: {e}")
            return []

    # ============================================
    # Save Methods
    # ============================================
    
    def save_discovered_job(
        self,
        url: str,
        title: str = "",
        company: str = "",
        location: str = "",
        source: str = "scout",
        user_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Save a discovered job to the database.
        
        Args:
            url: Job posting URL
            title: Job title
            company: Company name
            location: Job location
            source: Discovery source (scout, manual)
            user_id: User ID for data ownership
            
        Returns:
            Job ID if saved successfully
        """
        try:
            job_id = str(uuid.uuid4())
            
            data = {
                "id": job_id,
                "url": url,
                "title": title or "Unknown",
                "company": company or "Unknown",
                "location": location or "Remote",
                "source": source,
                "discovered_at": datetime.now().isoformat()
            }
            
            if user_id:
                data["user_id"] = user_id
            
            result = supabase_client.table("discovered_jobs").insert(data).execute()
            
            if result.data:
                console.success(f"Saved job: {title} at {company}")
                return job_id
            
            return None
            
        except Exception as e:
            console.warning(f"Could not save job: {e}")
            return None
    
    def save_job_analysis(
        self,
        job_id: str,
        role: str,
        company: str,
        match_score: int,
        tech_stack: List[str] = None,
        matching_skills: List[str] = None,
        missing_skills: List[str] = None,
        reasoning: str = "",
        user_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Save job analysis to the database.
        
        Args:
            job_id: Reference to discovered_jobs.id
            role: Job role
            company: Company name
            match_score: 0-100 match score
            
        Returns:
            Analysis ID if saved
        """
        try:
            analysis_id = str(uuid.uuid4())
            
            data = {
                "id": analysis_id,
                "job_id": job_id,
                "role": role,
                "company": company,
                "match_score": match_score,
                "tech_stack": tech_stack or [],
                "matching_skills": matching_skills or [],
                "missing_skills": missing_skills or [],
                "reasoning": reasoning,
                "analyzed_at": datetime.now().isoformat()
            }
            
            if user_id:
                data["user_id"] = user_id
            
            result = supabase_client.table("job_analyses").insert(data).execute()
            
            if result.data:
                return analysis_id
            
            return None
            
        except Exception as e:
            console.warning(f"Could not save analysis: {e}")
            return None
    
    def save_application(
        self,
        job_id: str,
        analysis_id: str = None,
        resume_id: str = None,
        cover_letter_id: str = None,
        status: str = "pending",
        user_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Save job application to the database.
        
        Args:
            job_id: Reference to discovered_jobs.id
            analysis_id: Reference to job_analyses.id
            resume_id: Reference to generated_resumes.id
            cover_letter_id: Reference to cover_letters.id
            status: Application status
            
        Returns:
            Application ID if saved
        """
        try:
            app_id = str(uuid.uuid4())
            
            data = {
                "id": app_id,
                "job_id": job_id,
                "status": status,
                "applied_at": datetime.now().isoformat()
            }
            
            if analysis_id:
                data["analysis_id"] = analysis_id
            if resume_id:
                data["resume_id"] = resume_id
            if cover_letter_id:
                data["cover_letter_id"] = cover_letter_id
            if user_id:
                data["user_id"] = user_id
            
            result = supabase_client.table("applications").insert(data).execute()
            
            if result.data:
                console.success(f"Application logged")
                return app_id
            
            return None
            
        except Exception as e:
            console.warning(f"Could not save application: {e}")
            return None
    
    def save_cover_letter(
        self,
        job_title: str,
        company_name: str,
        content: Dict,
        job_url: str = "",
        tone: str = "professional",
        user_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Save generated cover letter.
        
        Args:
            job_title: Target job title
            company_name: Target company
            content: Cover letter content (JSONB) - REQUIRED
            
        Returns:
            Cover letter ID if saved
        """
        try:
            letter_id = str(uuid.uuid4())
            
            # Ensure content is a dict (required NOT NULL JSONB column)
            if not isinstance(content, dict):
                content = {"text": str(content)}
            
            data = {
                "id": letter_id,
                "job_title": job_title,
                "company_name": company_name,
                "content": content,  # REQUIRED: JSONB NOT NULL
                "job_url": job_url,
                "tone": tone,
                "created_at": datetime.now().isoformat()
            }
            
            if user_id:
                data["user_id"] = user_id
            
            result = supabase_client.table("cover_letters").insert(data).execute()
            
            if result.data:
                console.success(f"Cover letter saved")
                return letter_id
            
            return None
            
        except Exception as e:
            console.warning(f"Could not save cover letter: {e}")
            return None
    
    def save_generated_resume(
        self,
        tailored_content: Dict,
        original_content: Dict = None,
        template_id: str = None,
        job_title: str = "",
        company: str = "",
        job_url: str = "",
        user_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Save generated/tailored resume.
        
        Args:
            tailored_content: Tailored resume content (JSONB) - REQUIRED
            original_content: Original resume content (JSONB) - REQUIRED
            template_id: Reference to resume_templates.id (UUID)
            
        Returns:
            Resume ID if saved
        """
        try:
            resume_id = str(uuid.uuid4())
            
            # Ensure required JSONB fields are dicts
            if not isinstance(tailored_content, dict):
                tailored_content = {"content": str(tailored_content)}
            if original_content is None:
                original_content = tailored_content.copy()
            if not isinstance(original_content, dict):
                original_content = {"content": str(original_content)}
            
            data = {
                "id": resume_id,
                "original_content": original_content,  # REQUIRED: JSONB NOT NULL
                "tailored_content": tailored_content,  # REQUIRED: JSONB NOT NULL
                "job_title": job_title,
                "company_name": company,
                "job_url": job_url,
                "created_at": datetime.now().isoformat()
            }
            
            # Only add template_id if it's a valid UUID
            if template_id and template_id != "default":
                data["template_id"] = template_id
            if user_id:
                data["user_id"] = user_id
            
            result = supabase_client.table("generated_resumes").insert(data).execute()
            
            if result.data:
                console.success(f"Resume saved")
                return resume_id
            
            return None
            
        except Exception as e:
            console.warning(f"Could not save resume: {e}")
            return None
    
    def update_application_status(
        self,
        application_id: str,
        status: str
    ) -> bool:
        """Update application status."""
        try:
            result = supabase_client.table("applications").update(
                {"status": status}
            ).eq("id", application_id).execute()
            
            return bool(result.data)
            
        except Exception as e:
            console.warning(f"Could not update status: {e}")
            return False
    
    def get_applications_summary(self, user_id: Optional[str] = None) -> Dict:
        """Get summary of all applications, optionally scoped to user."""
        try:
            query = supabase_client.table("applications").select("*")
            if user_id:
                query = query.eq("user_id", user_id)
            result = query.execute()
            
            if not result.data:
                return {"total": 0, "by_status": {}}
            
            by_status = {}
            for app in result.data:
                status = app.get("status", "unknown")
                by_status[status] = by_status.get(status, 0) + 1
            
            return {
                "total": len(result.data),
                "by_status": by_status,
                "applications": result.data
            }
            
        except Exception as e:
            console.warning(f"Could not get summary: {e}")
            return {"total": 0, "by_status": {}, "error": str(e)}


# Singleton instance
db_service = DatabaseService()
