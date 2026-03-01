"""
Career Trajectory API Routes

Endpoints for career path analysis, progression modeling,
and skill-gap identification.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.core.auth import get_current_user
from src.services.career_trajectory import career_engine
from src.services.skill_tracker import SkillTracker

router = APIRouter()
skill_tracker = SkillTracker()


# ── Request / Response Models ─────────────────────────────────


class CareerAnalysisRequest(BaseModel):
	"""Full profile-based analysis."""

	experience: List[Dict[str, Any]] = Field(default_factory=list)
	skills: Any = Field(default_factory=dict)


class QuickPathRequest(BaseModel):
	"""Quick path suggestion from a title."""

	current_title: str
	years_experience: float = 0


class TimelineRequest(BaseModel):
	"""Timeline estimation between two roles."""

	current_title: str
	target_title: str


# ── Routes ────────────────────────────────────────────────────


@router.post('/analyze')
async def analyze_career(req: CareerAnalysisRequest, user=Depends(get_current_user)):
	"""
	Full career trajectory analysis from profile data.
	Returns current level, suggested paths, lateral options, and market positioning.
	"""
	profile = {
		'experience': req.experience,
		'skills': req.skills,
	}
	return career_engine.analyze(profile)


@router.post('/paths')
async def suggest_paths(req: QuickPathRequest, user=Depends(get_current_user)):
	"""Quick path suggestions from just a job title."""
	paths = career_engine.suggest_paths(req.current_title, req.years_experience)
	return {'current_title': req.current_title, 'paths': paths}


@router.post('/timeline')
async def estimate_timeline(req: TimelineRequest, user=Depends(get_current_user)):
	"""Estimate years and requirements to reach a target role."""
	return career_engine.estimate_timeline(req.current_title, req.target_title)


@router.get('/skill-gaps/{role}')
async def get_skill_gaps(role: str, user=Depends(get_current_user)):
	"""
	Analyze skill gaps for a target role against the user's known skills.
	Delegates to SkillTracker for market-aware gap analysis.
	"""
	# Build minimal profile from the user object
	user_skills = []
	if hasattr(user, 'skills'):
		user_skills = user.skills if isinstance(user.skills, list) else []

	analysis = skill_tracker.analyze_gaps(user_skills, role)
	return analysis


@router.get('/ladders')
async def list_career_ladders(user=Depends(get_current_user)):
	"""List available career ladder families and their levels."""
	from src.services.career_trajectory import CAREER_LADDERS

	return {
		family: [{'title': r['title'], 'level': r['level'], 'avg_salary_k': r['avg_salary_k']} for r in rungs]
		for family, rungs in CAREER_LADDERS.items()
	}
