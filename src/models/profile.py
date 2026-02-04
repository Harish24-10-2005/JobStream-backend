
from typing import List, Optional, Dict, Literal
from pydantic import BaseModel, Field, HttpUrl, ConfigDict

class Location(BaseModel):
    city: str
    country: str
    address: str
    
    model_config = ConfigDict(extra='ignore')

class Urls(BaseModel):
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    
    model_config = ConfigDict(extra='ignore')

class PersonalInfo(BaseModel):
    first_name: str
    last_name: str
    full_name: str
    email: str
    phone: str
    location: Location
    urls: Urls
    summary: Optional[str] = None  # Professional summary/bio
    
    model_config = ConfigDict(extra='ignore')

class Education(BaseModel):
    degree: str
    major: str
    university: str
    start_date: str
    end_date: str
    cgpa: Optional[str] = None
    is_current: Optional[bool] = False
    
    model_config = ConfigDict(extra='ignore')

class Experience(BaseModel):
    title: str
    company: str
    start_date: str
    end_date: str
    description: str
    
    model_config = ConfigDict(extra='ignore')

class Project(BaseModel):
    name: str
    tech_stack: List[str]
    description: str
    
    model_config = ConfigDict(extra='ignore')

class Files(BaseModel):
    resume: str = Field(..., description="Absolute path to the resume PDF")
    
    model_config = ConfigDict(extra='ignore')

class ApplicationPreferences(BaseModel):
    expected_salary: str
    notice_period: str
    work_authorization: str
    relocation: str
    employment_type: List[str]
    
    model_config = ConfigDict(extra='ignore')

class UserProfile(BaseModel):
    """
    Complete User Profile Model matching the yaml structure.
    """
    personal_information: PersonalInfo
    education: List[Education]
    experience: List[Experience]
    projects: List[Project]
    skills: Dict[str, List[str]]
    files: Files
    application_preferences: Optional[ApplicationPreferences] = None
    behavioral_questions: Optional[Dict[str, str]] = None
    
    model_config = ConfigDict(extra='ignore')
    
    def to_resume_text(self) -> str:
        """Helper to convert profile to text for Analyst Agent"""
        lines = []
        p = self.personal_information
        lines.append(f"Name: {p.full_name}")
        lines.append(f"Email: {p.email}")
        lines.append(f"Phone: {p.phone}")
        lines.append(f"Location: {p.location.address}")
        lines.append(f"Links: {p.urls.model_dump()}")
        
        lines.append("\nSKILLS:")
        for category, items in self.skills.items():
            lines.append(f"- {category.title()}: {', '.join(items)}")
            
        lines.append("\nEXPERIENCE:")
        for exp in self.experience:
            lines.append(f"{exp.title} at {exp.company} ({exp.start_date} - {exp.end_date})")
            lines.append(f"{exp.description}")
            
        lines.append("\nPROJECTS:")
        for proj in self.projects:
            lines.append(f"{proj.name} (Tech: {', '.join(proj.tech_stack)})")
            lines.append(f"{proj.description}")
            
        lines.append("\nEDUCATION:")
        for edu in self.education:
            lines.append(f"{edu.degree} in {edu.major} - {edu.university} ({edu.start_date} - {edu.end_date})")
            
        return "\n".join(lines)


# ============================================================================
# NetworkAI Models - LinkedIn X-Ray Search & Referral Intelligence
# ============================================================================

class NetworkMatch(BaseModel):
    """A potential networking contact found via X-Ray search."""
    name: str = Field(..., description="Full name of the contact")
    headline: str = Field(..., description="LinkedIn headline (role + company)")
    profile_url: str = Field(..., description="LinkedIn profile URL")
    connection_type: Literal["alumni", "location", "company", "mutual"] = Field(
        ..., description="How they connect to the user"
    )
    college_match: Optional[str] = Field(None, description="Matching university if alumni")
    company_match: Optional[str] = Field(None, description="Matching company if shared employer")
    location_match: Optional[str] = Field(None, description="Matching city/region if location-based")
    confidence_score: float = Field(default=0.0, ge=0, le=1, description="Match confidence 0-1")
    outreach_draft: Optional[str] = Field(None, description="AI-generated connection request message")
    
    model_config = ConfigDict(extra='ignore')


class NetworkSearchResult(BaseModel):
    """Result of a NetworkAI search for connections at a company."""
    company: str = Field(..., description="Target company searched")
    total_matches: int = Field(default=0, description="Number of matches found")
    alumni_matches: List[NetworkMatch] = Field(default_factory=list, description="College alumni at company")
    location_matches: List[NetworkMatch] = Field(default_factory=list, description="People from same location")
    company_matches: List[NetworkMatch] = Field(default_factory=list, description="People from shared past employers")
    search_query: str = Field(..., description="The X-Ray search query used")
    search_source: str = Field(default="duckduckgo", description="Search engine used")
    
    model_config = ConfigDict(extra='ignore')


# ============================================================================
# GapAnalyst Models - Actionable Skill Gap Analysis
# ============================================================================

class LearningResource(BaseModel):
    """A learning resource for skill development."""
    title: str = Field(..., description="Resource title")
    url: str = Field(..., description="Link to the resource")
    platform: str = Field(..., description="Platform name (YouTube, Udemy, etc.)")
    resource_type: Literal["video", "course", "documentation", "article", "interactive"] = Field(
        default="video", description="Type of learning resource"
    )
    estimated_hours: float = Field(default=1.0, description="Estimated time to complete")
    is_free: bool = Field(default=True, description="Whether the resource is free")
    
    model_config = ConfigDict(extra='ignore')


class SkillGap(BaseModel):
    """A single skill gap with actionable learning path."""
    skill_name: str = Field(..., description="Name of the missing skill")
    severity: Literal["critical", "important", "nice-to-have"] = Field(
        ..., description="How important this skill is for the role"
    )
    job_requirement: str = Field(..., description="How the job description mentions this skill")
    learning_resources: List[LearningResource] = Field(
        default_factory=list, description="Curated learning resources"
    )
    estimated_hours: float = Field(default=10.0, description="Total hours to reach competency")
    suggested_project: str = Field(
        ..., description="Project idea to demonstrate this skill on resume"
    )
    score_impact: int = Field(default=5, ge=1, le=20, description="Score increase if acquired")
    
    model_config = ConfigDict(extra='ignore')


class GapAnalysis(BaseModel):
    """Complete gap analysis with actionable improvement roadmap."""
    current_score: int = Field(..., ge=0, le=100, description="Current match score")
    reachable_score: int = Field(..., ge=0, le=100, description="Score achievable with learning")
    skill_gaps: List[SkillGap] = Field(default_factory=list, description="Identified skill gaps")
    matching_skills: List[str] = Field(default_factory=list, description="Skills already possessed")
    action_plan: str = Field(..., description="Concise action plan summary")
    estimated_total_hours: float = Field(default=0, description="Total hours to reach reachable_score")
    priority_order: List[str] = Field(
        default_factory=list, description="Skills in order of priority to learn"
    )
    
    model_config = ConfigDict(extra='ignore')
