"""
API Version 1 Router
Aggregates all domain routers under the /api/v1 prefix.
"""
from fastapi import APIRouter

from src.api.routes import (
    jobs,
    agents,
    chat,
    pipeline,
    company,
    interview,
    salary,
    resume,
    cover_letter,
    tracker,
    network,
    user,
    rag,
)

v1_router = APIRouter(prefix="/api/v1")

# Domain routers
v1_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
v1_router.include_router(agents.router, prefix="/agents", tags=["Agents"])
v1_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
v1_router.include_router(pipeline.router, prefix="/pipeline", tags=["Pipeline"])
v1_router.include_router(company.router, prefix="/company", tags=["Company"])
v1_router.include_router(interview.router, prefix="/interview", tags=["Interview"])
v1_router.include_router(salary.router, prefix="/salary", tags=["Salary"])
v1_router.include_router(resume.router, prefix="/resume", tags=["Resume"])
v1_router.include_router(cover_letter.router, prefix="/cover-letter", tags=["Cover Letter"])
v1_router.include_router(tracker.router, prefix="/tracker", tags=["Tracker"])
v1_router.include_router(rag.router, prefix="/rag", tags=["RAG"])

# These routers already have their own prefix (/user, /network)
v1_router.include_router(network.router, tags=["NetworkAI"])
v1_router.include_router(user.router, tags=["User Profile"])
