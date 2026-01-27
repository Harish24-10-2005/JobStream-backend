"""
User Profile Service - Multi-tenant profile management via Supabase
Replaces hardcoded user_profile.yaml with database-backed profiles
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel
import logging
from src.services.supabase_client import supabase_client, SupabaseClient
from src.models.profile import (
    UserProfile, PersonalInfo, Location, Urls,
    Education, Experience, Project, Files, ApplicationPreferences
)
from src.services.rag_service import rag_service

logger = logging.getLogger(__name__)


class UserProfileDB(BaseModel):
    """Database representation of user profile - based on actual Supabase schema."""
    id: Optional[str] = None
    user_id: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None


class UserProfileService:
    """Service for managing user profiles in Supabase."""
    
    def __init__(self):
        # Use admin client (service role key) to bypass RLS for profile operations
        try:
            self.client = SupabaseClient.get_admin_client()
            logger.info("UserProfileService initialized with admin client (RLS bypassed)")
        except ValueError:
            # Fallback to anon client if service key not available
            self.client = supabase_client
            logger.warning("Service key not configured, using anon client (RLS enforced)")
        self._profile_cache: Dict[str, UserProfile] = {}
    
    async def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """
        Fetch complete user profile from Supabase.
        Returns UserProfile model compatible with existing agents.
        """
        try:
            # Check cache first
            if user_id in self._profile_cache:
                logger.debug(f"Returning cached profile for user {user_id}")
                return self._profile_cache[user_id]
            
            # Fetch profile data - use maybe_single() to avoid error when no rows
            profile_data = self.client.table("user_profiles") \
                .select("*") \
                .eq("user_id", user_id) \
                .maybe_single() \
                .execute()
            
            if not profile_data.data:
                logger.debug(f"No profile found for user {user_id}")
                return None
            
            p = profile_data.data
            
            # Fetch related data in parallel-ish
            education_resp = self.client.table("user_education") \
                .select("*") \
                .eq("user_id", user_id) \
                .order("start_date", desc=True) \
                .execute()
            
            experience_resp = self.client.table("user_experience") \
                .select("*") \
                .eq("user_id", user_id) \
                .order("start_date", desc=True) \
                .execute()
            
            projects_resp = self.client.table("user_projects") \
                .select("*") \
                .eq("user_id", user_id) \
                .execute()
            
            # Fetch primary resume
            resume_resp = self.client.table("user_resumes") \
                .select("*") \
                .eq("user_id", user_id) \
                .eq("is_primary", True) \
                .single() \
                .execute()
            
            # Build UserProfile model
            profile = UserProfile(
                personal_information=PersonalInfo(
                    first_name=p.get("first_name", ""),
                    last_name=p.get("last_name", ""),
                    full_name=f"{p.get('first_name', '')} {p.get('last_name', '')}",
                    email=p.get("email", ""),
                    phone=p.get("phone", ""),
                    location=Location(
                        city=p.get("city", ""),
                        country=p.get("country", ""),
                        address=p.get("address", "")
                    ),
                    urls=Urls(
                        linkedin=p.get("linkedin_url"),
                        github=p.get("github_url"),
                        portfolio=p.get("portfolio_url")
                    )
                ),
                education=[
                    Education(
                        degree=edu.get("degree", ""),
                        major=edu.get("major", ""),
                        university=edu.get("university", ""),
                        start_date=str(edu.get("start_date", "")),
                        end_date=str(edu.get("end_date", "")),
                        cgpa=edu.get("cgpa"),
                        is_current=edu.get("is_current", False)
                    )
                    for edu in education_resp.data or []
                ],
                experience=[
                    Experience(
                        title=exp.get("title", ""),
                        company=exp.get("company", ""),
                        start_date=str(exp.get("start_date", "")),
                        end_date=str(exp.get("end_date", "")) if not exp.get("is_current") else "Present",
                        description=exp.get("description", "")
                    )
                    for exp in experience_resp.data or []
                ],
                projects=[
                    Project(
                        name=proj.get("name", ""),
                        tech_stack=proj.get("tech_stack", []),
                        description=proj.get("description", "")
                    )
                    for proj in projects_resp.data or []
                ],
                skills=p.get("skills", {}),
                files=Files(
                    resume=resume_resp.data.get("file_url", "") if resume_resp.data else ""
                ),
                application_preferences=ApplicationPreferences(
                    expected_salary=p.get("expected_salary", "Negotiable"),
                    notice_period=p.get("notice_period", "Immediate"),
                    work_authorization=p.get("work_authorization", ""),
                    relocation=p.get("relocation", "Yes"),
                    employment_type=p.get("employment_types", ["Full-time"])
                ) if p.get("expected_salary") else None,
                behavioral_questions=p.get("behavioral_questions", {})
            )
            
            # Cache the profile
            self._profile_cache[user_id] = profile
            logger.info(f"Loaded profile for user {user_id}: {profile.personal_information.full_name}")
            
            return profile
            
        except Exception as e:
            logger.error(f"Error fetching profile for user {user_id}: {e}")
            return None
    
    async def create_profile(self, user_id: str, data: Dict[str, Any]) -> Optional[str]:
        """
        Create a new user profile.
        Called during user onboarding.
        """
        try:
            # Handle full_name -> first_name/last_name
            first_name = data.get("first_name", "")
            last_name = data.get("last_name", "")
            if "full_name" in data and data["full_name"]:
                parts = data["full_name"].split(" ", 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ""
            
            # Handle location -> city
            city = data.get("city")
            if "location" in data and data["location"]:
                city = data["location"]
            
            # Handle skills - convert list to dict if needed
            skills = data.get("skills", {})
            if isinstance(skills, list):
                skills = {"primary": skills} if skills else {}
            
            # Build personal_info JSONB object (required by database)
            personal_info = {
                "first_name": first_name or "Unknown",
                "last_name": last_name or "",
                "email": data.get("email", ""),
                "phone": data.get("phone", ""),
                "location": city or data.get("location", ""),
                "linkedin_url": data.get("linkedin_url", ""),
                "github_url": data.get("github_url", ""),
                "portfolio_url": data.get("portfolio_url", ""),
                "summary": data.get("summary", ""),
            }
            
            # Build profile data with all required fields
            profile_data = {
                "user_id": user_id,
                "first_name": first_name or "Unknown",
                "last_name": last_name or "",
                "email": data.get("email", ""),
                "personal_info": personal_info,  # Required JSONB field
                "skills": skills or {},
                "education": [],
                "experience": [],
                "projects": [],
            }
            
            # Add optional fields only if they have values
            optional_fields = {
                "phone": data.get("phone"),
                "linkedin_url": data.get("linkedin_url"),
                "github_url": data.get("github_url"),
                "portfolio_url": data.get("portfolio_url"),
                "city": city,
                "summary": data.get("summary"),
            }
            
            for key, value in optional_fields.items():
                if value:
                    profile_data[key] = value
            
            logger.info(f"Creating profile with data: {list(profile_data.keys())}")
            
            response = self.client.table("user_profiles").insert(profile_data).execute()
            
            if response.data:
                profile_id = response.data[0]["id"]
                logger.info(f"Created profile {profile_id} for user {user_id}")
                
                # Invalidate cache
                self._profile_cache.pop(user_id, None)
                
                # Sync to RAG
                await self._sync_to_rag(user_id)
                
                return profile_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating profile for user {user_id}: {e}")
            raise
    
    async def update_profile(self, user_id: str, data: Dict[str, Any]) -> bool:
        """Update user profile fields."""
        try:
            # Handle full_name -> first_name/last_name
            if "full_name" in data and data["full_name"]:
                parts = data["full_name"].split(" ", 1)
                data["first_name"] = parts[0]
                data["last_name"] = parts[1] if len(parts) > 1 else ""
            
            # Only include columns that actually exist in the database
            # Based on actual schema: first_name, last_name, email, phone,
            # linkedin_url, github_url, portfolio_url
            allowed_fields = {
                "first_name", "last_name", "email", "phone",
                "linkedin_url", "github_url", "portfolio_url",
            }
            
            update_data = {k: v for k, v in data.items() if k in allowed_fields and v is not None}
            
            if not update_data:
                return False
            
            logger.info(f"Updating profile with fields: {list(update_data.keys())}")
            
            response = self.client.table("user_profiles") \
                .update(update_data) \
                .eq("user_id", user_id) \
                .execute()
            
            # Invalidate cache
            self._profile_cache.pop(user_id, None)
            
            # Sync to RAG
            await self._sync_to_rag(user_id)
            
            logger.info(f"Updated profile for user {user_id}")
            return bool(response.data)
            
        except Exception as e:
            logger.error(f"Error updating profile for user {user_id}: {e}")
            return False
    
    async def add_education(self, user_id: str, education: Dict[str, Any]) -> Optional[str]:
        """Add education entry for user."""
        try:
            data = {
                "user_id": user_id,
                "degree": education.get("degree", ""),
                "major": education.get("major", ""),
                "university": education.get("university", ""),
                "cgpa": education.get("cgpa"),
                "start_date": education.get("start_date"),
                "end_date": education.get("end_date"),
                "is_current": education.get("is_current", False)
            }
            
            response = self.client.table("user_education").insert(data).execute()
            
            self._profile_cache.pop(user_id, None)
            
            return response.data[0]["id"] if response.data else None
            
        except Exception as e:
            logger.error(f"Error adding education for user {user_id}: {e}")
            return None
    
    async def add_experience(self, user_id: str, experience: Dict[str, Any]) -> Optional[str]:
        """Add work experience entry for user."""
        try:
            data = {
                "user_id": user_id,
                "title": experience.get("title", ""),
                "company": experience.get("company", ""),
                "start_date": experience.get("start_date"),
                "end_date": experience.get("end_date"),
                "is_current": experience.get("is_current", False),
                "description": experience.get("description", "")
            }
            
            response = self.client.table("user_experience").insert(data).execute()
            
            self._profile_cache.pop(user_id, None)
            
            return response.data[0]["id"] if response.data else None
            
        except Exception as e:
            logger.error(f"Error adding experience for user {user_id}: {e}")
            return None
    
    async def add_project(self, user_id: str, project: Dict[str, Any]) -> Optional[str]:
        """Add project entry for user."""
        try:
            data = {
                "user_id": user_id,
                "name": project.get("name", ""),
                "tech_stack": project.get("tech_stack", []),
                "description": project.get("description", ""),
                "project_url": project.get("project_url")
            }
            
            response = self.client.table("user_projects").insert(data).execute()
            
            self._profile_cache.pop(user_id, None)
            
            return response.data[0]["id"] if response.data else None
            
        except Exception as e:
            logger.error(f"Error adding project for user {user_id}: {e}")
            return None
    
    async def check_profile_exists(self, user_id: str) -> bool:
        """Check if user has completed their profile."""
        try:
            response = self.client.table("user_profiles") \
                .select("id") \
                .eq("user_id", user_id) \
                .maybe_single() \
                .execute()
            
            return response.data is not None
            
        except Exception as e:
            logger.debug(f"Profile check failed for user {user_id}: {e}")
            return False
    
    async def get_profile_completion(self, user_id: str) -> Dict[str, bool]:
        """Get profile completion status for onboarding UI."""
        try:
            profile = await self.get_profile(user_id)
            
            if not profile:
                return {
                    "has_profile": False,
                    "has_education": False,
                    "has_experience": False,
                    "has_projects": False,
                    "has_skills": False,
                    "has_resume": False,
                    "completion_percent": 0
                }
            
            has_education = len(profile.education) > 0
            has_experience = len(profile.experience) > 0
            has_projects = len(profile.projects) > 0
            has_skills = bool(profile.skills)
            has_resume = bool(profile.files.resume)
            
            completed = sum([
                True,  # has_profile
                has_education,
                has_experience,
                has_projects,
                has_skills,
                has_resume
            ])
            
            return {
                "has_profile": True,
                "has_education": has_education,
                "has_experience": has_experience,
                "has_projects": has_projects,
                "has_skills": has_skills,
                "has_resume": has_resume,
                "completion_percent": int((completed / 6) * 100)
            }
            
        except Exception as e:
            logger.error(f"Error checking profile completion: {e}")
            return {"has_profile": False, "completion_percent": 0}
    
    def invalidate_cache(self, user_id: str):
        """Clear cached profile for user."""
        self._profile_cache.pop(user_id, None)

    def _profile_to_text(self, profile: UserProfile) -> str:
        """Convert profile object to text format for RAG."""
        lines = [f"User Profile for {profile.personal_information.full_name}"]
        
        p = profile.personal_information
        lines.append(f"Contact: {p.email} | {p.phone}")
        lines.append(f"Location: {p.location.city}, {p.location.country}")
        if p.summary:
            lines.append(f"Summary: {p.summary}")
            
        if p.urls:
            lines.append(f"Links: LinkedIn: {p.urls.linkedin}, GitHub: {p.urls.github}, Portfolio: {p.urls.portfolio}")

        # Skills
        skills = profile.skills
        if isinstance(skills, dict):
            primary = skills.get("primary", [])
            lines.append(f"Skills: {', '.join(primary)}")
        elif isinstance(skills, list):
            lines.append(f"Skills: {', '.join(skills)}")

        # Experience
        if profile.experience:
            lines.append("\nWork Experience:")
            for exp in profile.experience:
                lines.append(f"- {exp.title} at {exp.company} ({exp.start_date} - {exp.end_date})")
                if exp.description:
                    lines.append(f"  Details: {exp.description}")

        # Education
        if profile.education:
            lines.append("\nEducation:")
            for edu in profile.education:
                lines.append(f"- {edu.degree} in {edu.major} at {edu.university} ({edu.start_date} - {edu.end_date})")

        # Projects
        if profile.projects:
            lines.append("\nProjects:")
            for proj in profile.projects:
                lines.append(f"- {proj.name}: {proj.description}")
                if proj.tech_stack:
                    lines.append(f"  Tech Stack: {', '.join(proj.tech_stack)}")
        
        # Preferences
        if profile.application_preferences:
            pref = profile.application_preferences
            lines.append(f"\nPreferences: Expected Salary: {pref.expected_salary}, Notice Period: {pref.notice_period}")
            lines.append(f"Relocation: {pref.relocation}, Employment Types: {', '.join(pref.employment_type)}")

        return "\n".join(lines)

    async def _sync_to_rag(self, user_id: str):
        """Fetch latest profile and sync to RAG."""
        try:
            profile = await self.get_profile(user_id)
            if profile:
                text = self._profile_to_text(profile)
                await rag_service.sync_user_profile(user_id, text)
        except Exception as e:
            logger.error(f"Failed to sync profile RAG for {user_id}: {e}")
user_profile_service = UserProfileService()
