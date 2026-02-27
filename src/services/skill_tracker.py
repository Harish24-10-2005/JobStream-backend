"""
Skill Tracker — Skill Gap Intelligence & Career Growth

Cross-references user skills against job market demands to identify
gaps, suggest learning paths, and track skill growth over time.

Usage:
    from src.services.skill_tracker import skill_tracker
    
    report = await skill_tracker.analyze_gap(
        user_skills=["Python", "FastAPI", "React"],
        target_roles=["Senior Backend Engineer"]
    )
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── Common skill requirements by role ───────────────────────────
# These serve as baseline data — in production, this gets enriched
# by actual job postings from the Scout Agent.

ROLE_SKILL_MAP: Dict[str, List[Dict[str, Any]]] = {
    "backend_engineer": [
        {"skill": "Python", "importance": "critical", "weight": 1.0},
        {"skill": "SQL", "importance": "critical", "weight": 0.9},
        {"skill": "REST APIs", "importance": "critical", "weight": 0.9},
        {"skill": "Docker", "importance": "high", "weight": 0.7},
        {"skill": "Git", "importance": "high", "weight": 0.7},
        {"skill": "System Design", "importance": "high", "weight": 0.8},
        {"skill": "CI/CD", "importance": "medium", "weight": 0.5},
        {"skill": "Kubernetes", "importance": "medium", "weight": 0.5},
        {"skill": "Redis", "importance": "medium", "weight": 0.5},
        {"skill": "Message Queues", "importance": "medium", "weight": 0.4},
    ],
    "frontend_engineer": [
        {"skill": "JavaScript", "importance": "critical", "weight": 1.0},
        {"skill": "React", "importance": "critical", "weight": 0.9},
        {"skill": "TypeScript", "importance": "high", "weight": 0.8},
        {"skill": "CSS", "importance": "high", "weight": 0.7},
        {"skill": "HTML", "importance": "high", "weight": 0.7},
        {"skill": "Git", "importance": "high", "weight": 0.6},
        {"skill": "Testing", "importance": "medium", "weight": 0.5},
        {"skill": "Next.js", "importance": "medium", "weight": 0.5},
        {"skill": "Webpack", "importance": "low", "weight": 0.3},
    ],
    "fullstack_engineer": [
        {"skill": "JavaScript", "importance": "critical", "weight": 1.0},
        {"skill": "Python", "importance": "high", "weight": 0.8},
        {"skill": "React", "importance": "high", "weight": 0.8},
        {"skill": "SQL", "importance": "high", "weight": 0.7},
        {"skill": "REST APIs", "importance": "high", "weight": 0.7},
        {"skill": "Docker", "importance": "medium", "weight": 0.5},
        {"skill": "TypeScript", "importance": "medium", "weight": 0.6},
        {"skill": "Git", "importance": "high", "weight": 0.6},
    ],
    "ml_engineer": [
        {"skill": "Python", "importance": "critical", "weight": 1.0},
        {"skill": "Machine Learning", "importance": "critical", "weight": 1.0},
        {"skill": "PyTorch", "importance": "high", "weight": 0.8},
        {"skill": "TensorFlow", "importance": "high", "weight": 0.7},
        {"skill": "SQL", "importance": "high", "weight": 0.6},
        {"skill": "Docker", "importance": "medium", "weight": 0.5},
        {"skill": "MLOps", "importance": "medium", "weight": 0.6},
        {"skill": "Statistics", "importance": "high", "weight": 0.8},
        {"skill": "Data Engineering", "importance": "medium", "weight": 0.5},
    ],
    "data_scientist": [
        {"skill": "Python", "importance": "critical", "weight": 1.0},
        {"skill": "Statistics", "importance": "critical", "weight": 0.9},
        {"skill": "SQL", "importance": "high", "weight": 0.8},
        {"skill": "Machine Learning", "importance": "high", "weight": 0.8},
        {"skill": "Pandas", "importance": "high", "weight": 0.7},
        {"skill": "Data Visualization", "importance": "medium", "weight": 0.6},
        {"skill": "R", "importance": "low", "weight": 0.3},
        {"skill": "Experiment Design", "importance": "medium", "weight": 0.5},
    ],
    "devops_engineer": [
        {"skill": "Linux", "importance": "critical", "weight": 1.0},
        {"skill": "Docker", "importance": "critical", "weight": 0.9},
        {"skill": "Kubernetes", "importance": "critical", "weight": 0.9},
        {"skill": "CI/CD", "importance": "critical", "weight": 0.9},
        {"skill": "AWS", "importance": "high", "weight": 0.8},
        {"skill": "Terraform", "importance": "high", "weight": 0.7},
        {"skill": "Python", "importance": "medium", "weight": 0.5},
        {"skill": "Networking", "importance": "medium", "weight": 0.6},
        {"skill": "Monitoring", "importance": "medium", "weight": 0.6},
    ],
}

# Learning resources (curated, not placeholder links)
LEARNING_PATHS: Dict[str, Dict[str, Any]] = {
    "Python": {"difficulty": "beginner", "est_weeks": 4, "resources": ["Official Python Tutorial", "Automate the Boring Stuff"]},
    "SQL": {"difficulty": "beginner", "est_weeks": 3, "resources": ["SQLBolt", "Mode SQL Tutorial"]},
    "Docker": {"difficulty": "intermediate", "est_weeks": 2, "resources": ["Docker Getting Started", "Docker Curriculum"]},
    "Kubernetes": {"difficulty": "advanced", "est_weeks": 6, "resources": ["Kubernetes Docs", "KodeKloud"]},
    "System Design": {"difficulty": "advanced", "est_weeks": 8, "resources": ["System Design Primer", "Designing Data-Intensive Apps"]},
    "React": {"difficulty": "intermediate", "est_weeks": 4, "resources": ["React Docs", "Full Stack Open"]},
    "TypeScript": {"difficulty": "intermediate", "est_weeks": 3, "resources": ["TypeScript Handbook", "Total TypeScript"]},
    "Machine Learning": {"difficulty": "advanced", "est_weeks": 12, "resources": ["fast.ai", "Andrew Ng ML Course"]},
    "REST APIs": {"difficulty": "intermediate", "est_weeks": 2, "resources": ["RESTful API Design", "FastAPI Docs"]},
    "Git": {"difficulty": "beginner", "est_weeks": 1, "resources": ["Pro Git Book", "Learn Git Branching"]},
    "CI/CD": {"difficulty": "intermediate", "est_weeks": 2, "resources": ["GitHub Actions Docs", "GitLab CI Tutorial"]},
    "Redis": {"difficulty": "intermediate", "est_weeks": 2, "resources": ["Redis University", "Redis Docs"]},
    "AWS": {"difficulty": "advanced", "est_weeks": 8, "resources": ["AWS Skill Builder", "A Cloud Guru"]},
    "Terraform": {"difficulty": "intermediate", "est_weeks": 3, "resources": ["Terraform Docs", "HashiCorp Learn"]},
    "PyTorch": {"difficulty": "advanced", "est_weeks": 6, "resources": ["PyTorch Tutorials", "Deep Learning with PyTorch"]},
    "TensorFlow": {"difficulty": "advanced", "est_weeks": 6, "resources": ["TensorFlow Docs", "DeepLearning.AI"]},
}


@dataclass
class SkillGap:
    """A single skill gap identified."""
    skill: str
    importance: str
    weight: float
    has_skill: bool
    learning_path: Optional[Dict[str, Any]] = None


@dataclass
class SkillGapReport:
    """Complete skill gap analysis for a target role."""
    target_role: str
    match_percentage: float
    matched_skills: List[str]
    missing_skills: List[SkillGap]
    extra_skills: List[str]
    priority_gaps: List[str]
    estimated_weeks_to_close: int
    recommendation: str


@dataclass
class MarketDemandItem:
    """Market demand data for a single skill."""
    skill: str
    roles_requiring: List[str]
    importance_avg: float
    trend: str  # rising, stable, declining


class SkillTracker:
    """
    Skill gap analysis and career growth intelligence.
    
    Compares user skills against role requirements to produce
    actionable gap reports with learning paths.
    """

    def __init__(self):
        self._supabase = None

    def _normalize_skill(self, skill: str) -> str:
        """Normalize skill name for comparison."""
        return skill.strip().lower()

    def _normalize_role(self, role: str) -> str:
        """Normalize role name to match our role map keys."""
        role_lower = role.strip().lower()
        # Map common variations
        mappings = {
            "backend": "backend_engineer",
            "backend engineer": "backend_engineer",
            "backend developer": "backend_engineer",
            "senior backend engineer": "backend_engineer",
            "frontend": "frontend_engineer",
            "frontend engineer": "frontend_engineer",
            "frontend developer": "frontend_engineer",
            "fullstack": "fullstack_engineer",
            "full stack": "fullstack_engineer",
            "full-stack": "fullstack_engineer",
            "full stack engineer": "fullstack_engineer",
            "ml": "ml_engineer",
            "ml engineer": "ml_engineer",
            "machine learning engineer": "ml_engineer",
            "data scientist": "data_scientist",
            "data science": "data_scientist",
            "devops": "devops_engineer",
            "devops engineer": "devops_engineer",
            "sre": "devops_engineer",
            "site reliability engineer": "devops_engineer",
        }
        return mappings.get(role_lower, role_lower)

    async def analyze_gap(
        self,
        user_skills: List[str],
        target_roles: List[str],
    ) -> List[SkillGapReport]:
        """
        Analyze skill gaps for one or more target roles.
        
        Returns a list of SkillGapReport, one per target role.
        """
        user_skills_normalized = {self._normalize_skill(s) for s in user_skills}
        reports = []

        for role in target_roles:
            role_key = self._normalize_role(role)
            requirements = ROLE_SKILL_MAP.get(role_key, [])

            if not requirements:
                # No data for this role, return a basic report
                reports.append(SkillGapReport(
                    target_role=role,
                    match_percentage=0,
                    matched_skills=[],
                    missing_skills=[],
                    extra_skills=list(user_skills),
                    priority_gaps=[],
                    estimated_weeks_to_close=0,
                    recommendation=f"No skill data available for '{role}'. Try: {list(ROLE_SKILL_MAP.keys())}",
                ))
                continue

            matched = []
            missing = []
            total_weight = sum(r["weight"] for r in requirements)
            matched_weight = 0

            for req in requirements:
                skill_lower = self._normalize_skill(req["skill"])
                has_it = skill_lower in user_skills_normalized

                if has_it:
                    matched.append(req["skill"])
                    matched_weight += req["weight"]
                else:
                    lp = LEARNING_PATHS.get(req["skill"])
                    missing.append(SkillGap(
                        skill=req["skill"],
                        importance=req["importance"],
                        weight=req["weight"],
                        has_skill=False,
                        learning_path=lp,
                    ))

            match_pct = round((matched_weight / total_weight) * 100, 1) if total_weight > 0 else 0

            # Sort missing by weight (highest priority first)
            missing.sort(key=lambda g: g.weight, reverse=True)
            priority_gaps = [g.skill for g in missing if g.importance in ("critical", "high")]

            # Estimate weeks to close gaps
            weeks = sum(
                (LEARNING_PATHS.get(g.skill, {}).get("est_weeks", 4))
                for g in missing if g.importance in ("critical", "high")
            )

            # Extra skills user has that aren't required
            required_normalized = {self._normalize_skill(r["skill"]) for r in requirements}
            extra = [s for s in user_skills if self._normalize_skill(s) not in required_normalized]

            # Recommendation
            if match_pct >= 90:
                rec = "You're a strong match. Focus on deepening expertise in your current skills."
            elif match_pct >= 70:
                rec = f"Good foundation. Focus on: {', '.join(priority_gaps[:3])} to become competitive."
            elif match_pct >= 50:
                rec = f"Moderate match. Key gaps: {', '.join(priority_gaps[:3])}. Dedicate ~{weeks} weeks to close them."
            else:
                rec = f"Significant gaps exist. Start with: {', '.join(priority_gaps[:2])} as foundations."

            reports.append(SkillGapReport(
                target_role=role,
                match_percentage=match_pct,
                matched_skills=matched,
                missing_skills=missing,
                extra_skills=extra,
                priority_gaps=priority_gaps,
                estimated_weeks_to_close=weeks,
                recommendation=rec,
            ))

        return reports

    async def get_market_demand(self, skills: List[str]) -> List[MarketDemandItem]:
        """
        Check market demand for specific skills.
        
        Cross-references skills against all known role requirements
        to show which roles need them and their importance.
        """
        results = []
        for skill in skills:
            skill_lower = self._normalize_skill(skill)
            roles_needing = []
            importances = []

            for role_key, requirements in ROLE_SKILL_MAP.items():
                for req in requirements:
                    if self._normalize_skill(req["skill"]) == skill_lower:
                        roles_needing.append(role_key)
                        importances.append(req["weight"])

            avg_importance = (
                round(sum(importances) / len(importances), 2) if importances else 0
            )

            # Simple trend heuristic based on role count
            if len(roles_needing) >= 4:
                trend = "rising"
            elif len(roles_needing) >= 2:
                trend = "stable"
            else:
                trend = "niche"

            results.append(MarketDemandItem(
                skill=skill,
                roles_requiring=roles_needing,
                importance_avg=avg_importance,
                trend=trend,
            ))

        return results

    async def suggest_learning_path(
        self,
        gaps: List[str],
        max_items: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Generate a prioritized learning path for skill gaps.
        
        Returns ordered list of skills to learn with resources.
        """
        path = []
        for skill in gaps[:max_items]:
            lp = LEARNING_PATHS.get(skill, {
                "difficulty": "intermediate",
                "est_weeks": 4,
                "resources": ["Search online for tutorials"],
            })
            path.append({
                "skill": skill,
                "difficulty": lp.get("difficulty", "intermediate"),
                "estimated_weeks": lp.get("est_weeks", 4),
                "resources": lp.get("resources", []),
            })

        return path


# ── Singleton ───────────────────────────────────────────────────

skill_tracker = SkillTracker()
