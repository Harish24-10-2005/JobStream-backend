# Agents module - Lazy imports

def get_resume_agent():
    from src.agents.resume_agent import resume_agent
    return resume_agent

def get_cover_letter_agent():
    from src.agents.cover_letter_agent import cover_letter_agent
    return cover_letter_agent

def get_interview_agent():
    from src.agents.interview_agent import interview_agent
    return interview_agent

def get_salary_agent():
    from src.agents.salary_agent import salary_agent
    return salary_agent

def get_company_agent():
    from src.agents.company_agent import company_agent
    return company_agent

def get_tracker_agent():
    from src.agents.tracker_agent import job_tracker_agent
    return job_tracker_agent

__all__ = [
    "get_resume_agent",
    "get_cover_letter_agent",
    "get_interview_agent",
    "get_salary_agent",
    "get_company_agent",
    "get_tracker_agent",
]


