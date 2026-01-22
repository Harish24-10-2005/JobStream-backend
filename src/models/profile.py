
from typing import List, Optional, Dict
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
