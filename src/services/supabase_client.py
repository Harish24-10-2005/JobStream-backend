"""
Supabase Client - Singleton connection to Supabase
"""
import logging
from supabase import create_client, Client
from src.core.config import settings

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Singleton Supabase client for database operations."""
    
    _instance: Client = None
    
    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client instance."""
        if cls._instance is None:
            if not settings.supabase_url or not settings.supabase_anon_key:
                raise RuntimeError(
                    "Supabase not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY in .env"
                )
            cls._instance = create_client(
                settings.supabase_url,
                settings.supabase_anon_key
            )
            logger.info("Supabase client initialized")
        return cls._instance
    
    @classmethod
    def get_admin_client(cls) -> Client:
        """Get admin client with service role key (for bypassing RLS)."""
        if settings.supabase_service_key:
            return create_client(
                settings.supabase_url,
                settings.supabase_service_key.get_secret_value()
            )
        raise ValueError("Service key not configured. Set SUPABASE_SERVICE_KEY in .env")


def _get_supabase_client() -> Client:
    """Lazy-initialize and return the Supabase client singleton."""
    return SupabaseClient.get_client()


# Lazy proxy - avoids crash at import time if env vars are missing
class _LazySupabaseClient:
    """Proxy that defers Supabase initialization until first attribute access."""
    
    def __getattr__(self, name):
        client = _get_supabase_client()
        return getattr(client, name)

supabase_client = _LazySupabaseClient()


# Database helper functions
async def get_resume_templates():
    """Fetch all resume templates."""
    response = supabase_client.table("resume_templates").select("*").execute()
    return response.data


async def get_default_template():
    """Fetch the default ATS template."""
    response = supabase_client.table("resume_templates").select("*").eq("is_default", True).single().execute()
    return response.data


async def save_generated_resume(
    user_id: str,
    job_url: str,
    job_title: str,
    company_name: str,
    original_content: dict,
    tailored_content: dict,
    latex_source: str = None,
    pdf_url: str = None,
    ats_score: int = None
):
    """Save a generated resume to the database."""
    data = {
        "user_id": user_id,
        "job_url": job_url,
        "job_title": job_title,
        "company_name": company_name,
        "original_content": original_content,
        "tailored_content": tailored_content,
        "latex_source": latex_source,
        "pdf_url": pdf_url,
        "ats_score": ats_score
    }
    response = supabase_client.table("generated_resumes").insert(data).execute()
    return response.data[0] if response.data else None


async def save_cover_letter(
    user_id: str,
    job_url: str,
    job_title: str,
    company_name: str,
    content: dict,
    tone: str = "professional",
    resume_id: str = None,
    latex_source: str = None,
    pdf_url: str = None
):
    """Save a generated cover letter to the database."""
    data = {
        "user_id": user_id,
        "resume_id": resume_id,
        "job_url": job_url,
        "job_title": job_title,
        "company_name": company_name,
        "tone": tone,
        "content": content,
        "latex_source": latex_source,
        "pdf_url": pdf_url
    }
    response = supabase_client.table("cover_letters").insert(data).execute()
    return response.data[0] if response.data else None


async def save_job_search(user_id: str, query: str, location: str, platforms: list = None):
    """Save a job search to track history."""
    data = {
        "user_id": user_id,
        "query": query,
        "location": location,
        "platforms": platforms or ["greenhouse", "lever", "ashby"]
    }
    response = supabase_client.table("job_searches").insert(data).execute()
    return response.data[0] if response.data else None


async def save_discovered_job(search_id: str, url: str, platform: str, raw_data: dict = None):
    """Save a discovered job."""
    data = {
        "search_id": search_id,
        "url": url,
        "platform": platform,
        "raw_data": raw_data
    }
    response = supabase_client.table("discovered_jobs").insert(data).execute()
    return response.data[0] if response.data else None


async def save_job_analysis(
    job_id: str,
    user_profile_id: str,
    role: str,
    company: str,
    match_score: int,
    tech_stack: list = None,
    matching_skills: list = None,
    missing_skills: list = None,
    reasoning: str = None,
    salary_range: str = None
):
    """Save job analysis results."""
    data = {
        "job_id": job_id,
        "user_profile_id": user_profile_id,
        "role": role,
        "company": company,
        "salary_range": salary_range,
        "tech_stack": tech_stack,
        "matching_skills": matching_skills,
        "missing_skills": missing_skills,
        "match_score": match_score,
        "reasoning": reasoning
    }
    response = supabase_client.table("job_analyses").insert(data).execute()
    return response.data[0] if response.data else None


async def save_application(
    user_id: str,
    job_id: str,
    analysis_id: str = None,
    resume_id: str = None,
    cover_letter_id: str = None,
    status: str = "pending",
    scheduled_at: str = None
):
    """Save an application record."""
    data = {
        "user_id": user_id,
        "job_id": job_id,
        "analysis_id": analysis_id,
        "resume_id": resume_id,
        "cover_letter_id": cover_letter_id,
        "status": status,
        "scheduled_at": scheduled_at
    }
    response = supabase_client.table("applications").insert(data).execute()
    return response.data[0] if response.data else None


async def update_application_status(application_id: str, status: str, error: str = None):
    """Update application status."""
    data = {"status": status, "updated_at": "now()"}
    if status == "applied":
        data["applied_at"] = "now()"
    if error:
        data["last_error"] = error
    
    response = supabase_client.table("applications").update(data).eq("id", application_id).execute()
    return response.data[0] if response.data else None
