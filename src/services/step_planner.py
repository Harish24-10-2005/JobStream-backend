"""
Intelligent Step Planner — LLM-driven pipeline step optionalization.

Analyses the user's query, profile context, and existing resume
quality to decide which pipeline steps to enable/skip.

Examples of skippable steps:
  - Resume tailoring: if the user's resume is already a strong match
    for the target role (high ATS score against the query keywords).
  - Cover letter: if the user explicitly says "no cover letter" or
    the target portal is known not to accept them.
  - Company research: if the user already provided company context
    or asks for a quick-apply-only run.

The planner uses a cheap/fast LLM call (Groq 8B) to classify intent,
then augments the decision with heuristic signals from the user profile
and resume service.
"""

import json
import logging
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ─── Planner Output Schema ──────────────────────────────────────


class StepPlan(BaseModel):
    """Decides which optional pipeline steps to enable."""

    use_resume_tailoring: bool = Field(
        True,
        description='Whether to tailor the resume for each job.',
    )
    use_cover_letter: bool = Field(
        True,
        description='Whether to generate a cover letter for each job.',
    )
    use_company_research: bool = Field(
        False,
        description='Whether to run deep company research before applying.',
    )
    reasoning: str = Field(
        '',
        description='Short natural-language explanation of why these steps were chosen.',
    )


# ─── Prompt ─────────────────────────────────────────────────────

_PLANNER_SYSTEM = """\
You are a pipeline step planner for an AI job-application system.

Given the user's search query, their profile summary (if available),
and any explicit instructions they provided, decide which *optional*
pipeline steps should be enabled.

Pipeline steps you control:
  1. **resume_tailoring** — Rewrite/tailor the user's resume per job.
     Skip when:
       • The user says their resume is ready / perfect / don't touch it.
       • The user only wants to *search* or *track* jobs, not apply.
  2. **cover_letter** — Generate a cover letter per job.
     Skip when:
       • The user explicitly says "no cover letter".
       • The query is research-only ("find me companies in…").
  3. **company_research** — Deep background research on each company.
     Enable when:
       • The user asks to research companies or culture.
       • The user says "I want to know more about…" or "deep apply".
     Skip for quick-apply or high-volume application runs.

Always-on steps (you cannot disable):
  • Job scouting (search)
  • Job analysis / scoring
  • Application submission (controlled by auto_apply flag, not you)

Respond ONLY with valid JSON matching this schema:
{
  "use_resume_tailoring": true/false,
  "use_cover_letter": true/false,
  "use_company_research": true/false,
  "reasoning": "one-sentence explanation"
}
"""

_PLANNER_USER = """\
User query: "{query}"
Location: "{location}"
{profile_section}
Decide which steps to enable.
"""


class StepPlanner:
    """
    LLM-driven step planner with heuristic fallback.

    Uses Groq 8B for fast classification (~200ms).
    Falls back to keyword heuristics if LLM is unavailable.
    """

    def __init__(self):
        self._llm = None

    async def plan(
        self,
        query: str,
        location: str = '',
        user_id: Optional[str] = None,
    ) -> StepPlan:
        """
        Analyse the query and return a StepPlan.

        Tries LLM first, falls back to keyword heuristics.
        """
        # Build profile context (best-effort, non-blocking)
        profile_section = await self._get_profile_section(user_id)

        # Try LLM-based planning
        try:
            return await self._plan_with_llm(query, location, profile_section)
        except Exception as e:
            logger.warning(f'LLM step planner failed, using heuristics: {e}')

        # Fallback: keyword heuristics
        return self._plan_with_heuristics(query)

    # ─── LLM path ──────────────────────────────────────────

    async def _plan_with_llm(
        self, query: str, location: str, profile_section: str
    ) -> StepPlan:
        from src.core.llm_provider import get_llm

        llm = get_llm()

        user_msg = _PLANNER_USER.format(
            query=query,
            location=location,
            profile_section=profile_section,
        )

        response = await llm.ainvoke(
            [
                {'role': 'system', 'content': _PLANNER_SYSTEM},
                {'role': 'user', 'content': user_msg},
            ]
        )

        text = response.content if hasattr(response, 'content') else str(response)

        # Extract JSON from potential markdown fences
        text = text.strip()
        if text.startswith('```'):
            text = text.split('\n', 1)[-1].rsplit('```', 1)[0].strip()

        data = json.loads(text)
        return StepPlan(**data)

    # ─── Keyword heuristics ────────────────────────────────

    def _plan_with_heuristics(self, query: str) -> StepPlan:
        q = query.lower()

        # Detect "no resume change" intent
        skip_resume_keywords = [
            'resume is ready', 'resume is perfect', 'resume is already',
            'already perfect', "don't touch resume", "don't touch my resume",
            'no resume', 'skip resume', 'resume already done',
            'keep my resume', 'keep resume', 'dont change resume',
            "don't change resume", 'search only', 'just search',
            'just find', 'track only', 'resume is good',
            'resume is fine', 'my resume is great',
        ]
        use_resume = not any(kw in q for kw in skip_resume_keywords)

        # Detect "no cover letter" intent
        skip_cl_keywords = [
            'no cover letter', 'skip cover letter', 'without cover',
            'no cl', 'quick apply', 'fast apply', 'search only',
            'just search', 'just find', 'track only',
        ]
        use_cl = not any(kw in q for kw in skip_cl_keywords)

        # Detect "research" intent
        research_keywords = [
            'research', 'culture', 'deep apply', 'investigate',
            'background check', 'learn about', 'tell me about',
            'company info', 'glassdoor',
        ]
        use_research = any(kw in q for kw in research_keywords)

        parts = []
        if not use_resume:
            parts.append('resume tailoring skipped (user indicated resume is ready)')
        if not use_cl:
            parts.append('cover letter skipped (user requested quick apply)')
        if use_research:
            parts.append('company research enabled (user requested deep info)')
        reasoning = '; '.join(parts) if parts else 'All steps enabled (default)'

        return StepPlan(
            use_resume_tailoring=use_resume,
            use_cover_letter=use_cl,
            use_company_research=use_research,
            reasoning=reasoning,
        )

    # ─── Profile context helper ────────────────────────────

    async def _get_profile_section(self, user_id: Optional[str]) -> str:
        """Build a short profile summary for the planner prompt."""
        if not user_id:
            return 'Profile: not available.'

        try:
            from src.services.user_profile_service import user_profile_service

            profile = await user_profile_service.get_profile(user_id)
            if profile:
                name = getattr(profile, 'name', 'Unknown')
                headline = getattr(profile, 'headline', '') or getattr(profile, 'current_title', '')
                skills_list = getattr(profile, 'skills', []) or []
                skills = ', '.join(skills_list[:15]) if skills_list else 'N/A'
                return (
                    f'Profile: {name}, {headline}.\n'
                    f'Top skills: {skills}.'
                )
        except Exception as e:
            logger.debug(f'Profile fetch for planner failed: {e}')

        return 'Profile: not available.'
