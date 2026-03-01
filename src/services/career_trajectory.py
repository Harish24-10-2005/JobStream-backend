"""
Career Trajectory Engine — Career Path Modeling & Progression Analysis

Analyzes user experience, skills, and market data to model career
progression paths. Recommends next-role targets, identifies transition
gaps, and estimates timeline to reach target positions.

Usage:
    from src.services.career_trajectory import career_engine

    analysis = career_engine.analyze(user_profile)
    paths     = career_engine.suggest_paths("Senior Backend Engineer")
    timeline  = career_engine.estimate_timeline(current_role, target_role)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Career Ladder Definitions ──────────────────────────────────────
# Maps families of roles to ordered seniority levels.

CAREER_LADDERS: Dict[str, List[Dict[str, Any]]] = {
	'software_engineering': [
		{'title': 'Junior Software Engineer', 'level': 1, 'avg_years': 0, 'avg_salary_k': 65},
		{'title': 'Software Engineer', 'level': 2, 'avg_years': 2, 'avg_salary_k': 90},
		{'title': 'Senior Software Engineer', 'level': 3, 'avg_years': 5, 'avg_salary_k': 130},
		{'title': 'Staff Engineer', 'level': 4, 'avg_years': 8, 'avg_salary_k': 170},
		{'title': 'Principal Engineer', 'level': 5, 'avg_years': 12, 'avg_salary_k': 210},
		{'title': 'Distinguished Engineer', 'level': 6, 'avg_years': 18, 'avg_salary_k': 260},
	],
	'data_science': [
		{'title': 'Data Analyst', 'level': 1, 'avg_years': 0, 'avg_salary_k': 60},
		{'title': 'Data Scientist', 'level': 2, 'avg_years': 2, 'avg_salary_k': 95},
		{'title': 'Senior Data Scientist', 'level': 3, 'avg_years': 5, 'avg_salary_k': 135},
		{'title': 'Staff Data Scientist', 'level': 4, 'avg_years': 8, 'avg_salary_k': 165},
		{'title': 'Principal Data Scientist', 'level': 5, 'avg_years': 12, 'avg_salary_k': 200},
	],
	'product_management': [
		{'title': 'Associate PM', 'level': 1, 'avg_years': 0, 'avg_salary_k': 70},
		{'title': 'Product Manager', 'level': 2, 'avg_years': 2, 'avg_salary_k': 100},
		{'title': 'Senior Product Manager', 'level': 3, 'avg_years': 5, 'avg_salary_k': 140},
		{'title': 'Director of Product', 'level': 4, 'avg_years': 8, 'avg_salary_k': 180},
		{'title': 'VP of Product', 'level': 5, 'avg_years': 13, 'avg_salary_k': 230},
	],
	'engineering_management': [
		{'title': 'Tech Lead', 'level': 3, 'avg_years': 5, 'avg_salary_k': 140},
		{'title': 'Engineering Manager', 'level': 4, 'avg_years': 7, 'avg_salary_k': 165},
		{'title': 'Senior Engineering Manager', 'level': 5, 'avg_years': 10, 'avg_salary_k': 195},
		{'title': 'Director of Engineering', 'level': 6, 'avg_years': 13, 'avg_salary_k': 230},
		{'title': 'VP of Engineering', 'level': 7, 'avg_years': 17, 'avg_salary_k': 280},
	],
	'devops_sre': [
		{'title': 'Junior DevOps Engineer', 'level': 1, 'avg_years': 0, 'avg_salary_k': 60},
		{'title': 'DevOps Engineer', 'level': 2, 'avg_years': 2, 'avg_salary_k': 95},
		{'title': 'Senior DevOps Engineer', 'level': 3, 'avg_years': 5, 'avg_salary_k': 130},
		{'title': 'SRE / Platform Engineer', 'level': 4, 'avg_years': 7, 'avg_salary_k': 155},
		{'title': 'Staff SRE', 'level': 5, 'avg_years': 10, 'avg_salary_k': 185},
	],
	'design': [
		{'title': 'Junior Designer', 'level': 1, 'avg_years': 0, 'avg_salary_k': 55},
		{'title': 'Product Designer', 'level': 2, 'avg_years': 2, 'avg_salary_k': 85},
		{'title': 'Senior Product Designer', 'level': 3, 'avg_years': 5, 'avg_salary_k': 120},
		{'title': 'Design Lead', 'level': 4, 'avg_years': 8, 'avg_salary_k': 150},
		{'title': 'Head of Design', 'level': 5, 'avg_years': 12, 'avg_salary_k': 185},
	],
}

# Keywords that map free-text titles → ladder families
TITLE_KEYWORDS: Dict[str, str] = {
	'software': 'software_engineering',
	'backend': 'software_engineering',
	'frontend': 'software_engineering',
	'fullstack': 'software_engineering',
	'full stack': 'software_engineering',
	'full-stack': 'software_engineering',
	'web developer': 'software_engineering',
	'mobile': 'software_engineering',
	'data scientist': 'data_science',
	'data analyst': 'data_science',
	'machine learning': 'data_science',
	'ml engineer': 'data_science',
	'ai engineer': 'data_science',
	'product manager': 'product_management',
	'product owner': 'product_management',
	'engineering manager': 'engineering_management',
	'tech lead': 'engineering_management',
	'director of eng': 'engineering_management',
	'vp of eng': 'engineering_management',
	'devops': 'devops_sre',
	'sre': 'devops_sre',
	'site reliability': 'devops_sre',
	'platform engineer': 'devops_sre',
	'infrastructure': 'devops_sre',
	'designer': 'design',
	'ux': 'design',
	'ui': 'design',
}

# Skills typically required for career transitions
TRANSITION_SKILLS: Dict[str, List[str]] = {
	'software_engineering→engineering_management': [
		'People management',
		'Agile/Scrum',
		'Hiring & interviewing',
		'Project planning',
		'Stakeholder communication',
		'OKR setting',
	],
	'software_engineering→data_science': [
		'Statistics',
		'Python (ML libs)',
		'SQL analytics',
		'A/B testing',
		'Model evaluation',
		'Data visualization',
	],
	'data_science→product_management': [
		'User research',
		'Roadmap planning',
		'Stakeholder management',
		'Metrics/KPI definition',
		'Prioritization frameworks',
	],
	'software_engineering→devops_sre': [
		'CI/CD',
		'Infrastructure as Code',
		'Monitoring & observability',
		'Linux systems',
		'Container orchestration',
		'Incident management',
	],
}


@dataclass
class CareerPosition:
	"""A single position in a user's career history."""

	title: str
	company: str = ''
	start_year: int = 0
	end_year: Optional[int] = None  # None = current
	skills_used: List[str] = field(default_factory=list)


@dataclass
class CareerPath:
	"""A suggested career progression path."""

	name: str
	ladder: str
	current_level: int
	target_level: int
	steps: List[Dict[str, Any]]
	estimated_years: float
	salary_delta_k: int
	transition_skills: List[str] = field(default_factory=list)
	confidence: float = 0.7


class CareerTrajectoryEngine:
	"""
	Analyzes career history and models forward progression.

	Capabilities:
	  - Determine current career level from job history
	  - Suggest next-step and stretch-goal positions
	  - Estimate timeline to reach target roles
	  - Identify skill gaps for career transitions
	  - Support lateral moves (e.g., IC → management)
	"""

	def __init__(self):
		self._ladders = CAREER_LADDERS
		self._title_keywords = TITLE_KEYWORDS

	# ── Public API ──────────────────────────────────────────────

	def analyze(self, profile: Dict[str, Any]) -> Dict[str, Any]:
		"""
		Full career trajectory analysis from a user profile.

		Args:
		    profile: User profile dict with experience, skills, etc.

		Returns:
		    Dict with current_level, suggested_paths, timeline, gaps
		"""
		experience = profile.get('experience', [])
		skills = self._extract_skills(profile)

		# Determine current position
		current = self._current_position(experience)
		ladder_family = self._resolve_ladder(current.title)
		current_level = self._estimate_level(current, ladder_family)

		# Generate forward paths
		paths = self._generate_paths(current, ladder_family, current_level, skills)

		# Calculate total years of experience
		total_yoe = self._total_years(experience)

		return {
			'current_role': current.title,
			'current_company': current.company,
			'ladder_family': ladder_family,
			'estimated_level': current_level,
			'total_years_experience': total_yoe,
			'suggested_paths': [self._path_to_dict(p) for p in paths],
			'lateral_transitions': self._lateral_options(ladder_family, current_level),
			'market_positioning': self._market_position(current_level, ladder_family, total_yoe),
		}

	def suggest_paths(self, current_title: str, years_experience: float = 0) -> List[Dict[str, Any]]:
		"""Quick suggestion from just a title string."""
		ladder = self._resolve_ladder(current_title)
		level = self._level_from_title(current_title, ladder)
		current = CareerPosition(title=current_title)

		paths = self._generate_paths(current, ladder, level, [])
		return [self._path_to_dict(p) for p in paths]

	def estimate_timeline(self, current_title: str, target_title: str) -> Dict[str, Any]:
		"""
		Estimate years and requirements to reach target role.
		"""
		src_ladder = self._resolve_ladder(current_title)
		tgt_ladder = self._resolve_ladder(target_title)

		src_level = self._level_from_title(current_title, src_ladder)
		tgt_level = self._level_from_title(target_title, tgt_ladder)

		is_lateral = src_ladder != tgt_ladder

		if is_lateral:
			transition_key = f'{src_ladder}→{tgt_ladder}'
			needed_skills = TRANSITION_SKILLS.get(transition_key, [])
			base_years = max(1, tgt_level - src_level) * 2.5
			transition_penalty = 1.5  # lateral moves typically take longer
		else:
			needed_skills = []
			base_years = self._years_between_levels(src_level, tgt_level, src_ladder)
			transition_penalty = 1.0

		total_years = round(base_years * transition_penalty, 1)

		return {
			'current': current_title,
			'target': target_title,
			'is_lateral_move': is_lateral,
			'estimated_years': total_years,
			'transition_skills_needed': needed_skills,
			'milestones': self._milestones(src_level, tgt_level, tgt_ladder),
		}

	# ── Internal Helpers ───────────────────────────────────────

	def _resolve_ladder(self, title: str) -> str:
		"""Map a free-text job title to a career ladder family."""
		title_lower = title.lower()
		for keyword, family in self._title_keywords.items():
			if keyword in title_lower:
				return family
		return 'software_engineering'  # sensible default

	def _current_position(self, experience: List[Dict]) -> CareerPosition:
		"""Extract the most recent position from experience history."""
		if not experience:
			return CareerPosition(title='Software Engineer')

		# Find current/most recent
		sorted_exp = sorted(
			experience,
			key=lambda x: x.get('end_date') or '9999',
			reverse=True,
		)
		latest = sorted_exp[0]
		return CareerPosition(
			title=latest.get('title', 'Software Engineer'),
			company=latest.get('company', ''),
			skills_used=latest.get('technologies', []),
		)

	def _estimate_level(self, position: CareerPosition, ladder: str) -> int:
		"""Estimate the seniority level of a position."""
		return self._level_from_title(position.title, ladder)

	def _level_from_title(self, title: str, ladder: str) -> int:
		"""Match a title string to its approximate level.

		Scores every rung and picks the best match so that
		'Software Engineer' → level 2 (exact) beats the partial
		substring hit on 'Junior Software Engineer' (level 1).
		"""
		title_lower = title.lower().strip()
		rungs = self._ladders.get(ladder, [])

		best_level: Optional[int] = None
		best_score = -1

		for rung in rungs:
			rung_lower = rung['title'].lower()

			# Exact match is highest priority
			if rung_lower == title_lower:
				return rung['level']

			score = 0
			if rung_lower in title_lower:
				# Rung title is a substring of user title — good
				score = len(rung_lower)
			elif title_lower in rung_lower:
				# User title is a substring of rung — weaker
				score = len(title_lower) * 0.5

			if score > best_score:
				best_score = score
				best_level = rung['level']

		if best_level is not None and best_score > 0:
			return best_level

		# Keyword heuristics
		if any(kw in title_lower for kw in ['principal', 'distinguished', 'fellow']):
			return 5
		if any(kw in title_lower for kw in ['staff', 'lead']):
			return 4
		if 'senior' in title_lower or 'sr' in title_lower:
			return 3
		if any(kw in title_lower for kw in ['junior', 'jr', 'associate', 'intern']):
			return 1
		return 2  # mid-level default

	def _extract_skills(self, profile: Dict) -> List[str]:
		"""Pull flat skill list from profile."""
		skills_data = profile.get('skills', {})
		if isinstance(skills_data, list):
			return skills_data
		# Handle nested {primary: [], secondary: [], tools: []}
		flat = []
		for category in ['primary', 'secondary', 'tools']:
			flat.extend(skills_data.get(category, []))
		return flat

	def _total_years(self, experience: List[Dict]) -> float:
		"""Estimate total years of professional experience."""
		if not experience:
			return 0

		years_set = set()
		for exp in experience:
			start = exp.get('start_date', '')
			end = exp.get('end_date', '')
			try:
				start_year = int(start[:4]) if start else datetime.now().year
				end_year = int(end[:4]) if end else datetime.now().year
				for y in range(start_year, end_year + 1):
					years_set.add(y)
			except (ValueError, IndexError):
				continue

		return max(0, len(years_set) - 1) if years_set else 0

	def _generate_paths(
		self,
		current: CareerPosition,
		ladder: str,
		level: int,
		skills: List[str],
	) -> List[CareerPath]:
		"""Generate 2-3 suggested career paths."""
		paths = []
		rungs = self._ladders.get(ladder, [])

		# Path 1: Natural next step
		next_rungs = [r for r in rungs if r['level'] == level + 1]
		if next_rungs:
			nxt = next_rungs[0]
			paths.append(
				CareerPath(
					name='Next Step',
					ladder=ladder,
					current_level=level,
					target_level=nxt['level'],
					steps=[nxt],
					estimated_years=self._years_between_levels(level, nxt['level'], ladder),
					salary_delta_k=nxt['avg_salary_k'] - self._salary_at_level(level, ladder),
					confidence=0.85,
				)
			)

		# Path 2: Stretch goal (2 levels up)
		stretch_rungs = [r for r in rungs if r['level'] == level + 2]
		if stretch_rungs:
			stretch = stretch_rungs[0]
			intermediate = next_rungs[0] if next_rungs else None
			steps = []
			if intermediate:
				steps.append(intermediate)
			steps.append(stretch)
			paths.append(
				CareerPath(
					name='Stretch Goal',
					ladder=ladder,
					current_level=level,
					target_level=stretch['level'],
					steps=steps,
					estimated_years=self._years_between_levels(level, stretch['level'], ladder),
					salary_delta_k=stretch['avg_salary_k'] - self._salary_at_level(level, ladder),
					confidence=0.65,
				)
			)

		# Path 3: Lateral move (e.g., IC → management)
		lateral = self._best_lateral(ladder, level)
		if lateral:
			transition_key = f'{ladder}→{lateral["ladder"]}'
			paths.append(
				CareerPath(
					name=f'Lateral: {lateral["title"]}',
					ladder=lateral['ladder'],
					current_level=level,
					target_level=lateral['level'],
					steps=[lateral],
					estimated_years=round(
						self._years_between_levels(level, lateral['level'], lateral['ladder']) * 1.5,
						1,
					),
					salary_delta_k=lateral['avg_salary_k'] - self._salary_at_level(level, ladder),
					transition_skills=TRANSITION_SKILLS.get(transition_key, []),
					confidence=0.55,
				)
			)

		return paths

	def _best_lateral(self, current_ladder: str, level: int) -> Optional[Dict]:
		"""Find the best lateral career move from the current ladder."""
		lateral_map = {
			'software_engineering': 'engineering_management',
			'data_science': 'product_management',
			'devops_sre': 'software_engineering',
		}
		target_ladder = lateral_map.get(current_ladder)
		if not target_ladder:
			return None

		rungs = self._ladders.get(target_ladder, [])
		# Find the closest rung at same or +1 level
		candidates = [r for r in rungs if abs(r['level'] - level) <= 1]
		if candidates:
			best = min(candidates, key=lambda r: abs(r['level'] - level))
			return {**best, 'ladder': target_ladder}
		return None

	def _years_between_levels(self, src: int, tgt: int, ladder: str) -> float:
		"""Estimated years to progress between two levels."""
		rungs = self._ladders.get(ladder, [])
		src_years = next((r['avg_years'] for r in rungs if r['level'] == src), 0)
		tgt_years = next((r['avg_years'] for r in rungs if r['level'] == tgt), 10)
		return max(1, tgt_years - src_years)

	def _salary_at_level(self, level: int, ladder: str) -> int:
		"""Get average salary at a given level."""
		rungs = self._ladders.get(ladder, [])
		match = [r for r in rungs if r['level'] == level]
		return match[0]['avg_salary_k'] if match else 80

	def _milestones(self, src_level: int, tgt_level: int, ladder: str) -> List[Dict]:
		"""Build milestone list between two levels."""
		rungs = self._ladders.get(ladder, [])
		return [
			{'title': r['title'], 'level': r['level'], 'typical_years': r['avg_years']}
			for r in rungs
			if src_level < r['level'] <= tgt_level
		]

	def _lateral_options(self, ladder: str, level: int) -> List[Dict]:
		"""List all viable lateral career transitions."""
		options = []
		for src_ladder, tgt_ladder in [
			('software_engineering', 'engineering_management'),
			('software_engineering', 'data_science'),
			('software_engineering', 'devops_sre'),
			('data_science', 'product_management'),
		]:
			if ladder != src_ladder:
				continue
			transition_key = f'{src_ladder}→{tgt_ladder}'
			target_rungs = self._ladders.get(tgt_ladder, [])
			candidates = [r for r in target_rungs if abs(r['level'] - level) <= 1]
			if candidates:
				best = min(candidates, key=lambda r: abs(r['level'] - level))
				options.append(
					{
						'target_family': tgt_ladder,
						'target_role': best['title'],
						'skills_needed': TRANSITION_SKILLS.get(transition_key, []),
						'salary_change_k': best['avg_salary_k'] - self._salary_at_level(level, ladder),
					}
				)
		return options

	def _market_position(self, level: int, ladder: str, yoe: float) -> Dict:
		"""Assess where the user stands relative to market averages."""
		rungs = self._ladders.get(ladder, [])
		current_rung = next((r for r in rungs if r['level'] == level), None)

		if not current_rung:
			return {'assessment': 'unknown', 'details': 'Could not determine market position'}

		expected_yoe = current_rung['avg_years']
		delta = yoe - expected_yoe

		if delta < -2:
			assessment = 'ahead_of_curve'
			detail = f'You reached level {level} ~{abs(delta):.0f} years faster than average'
		elif delta > 3:
			assessment = 'consider_promotion'
			detail = f'You have ~{delta:.0f} more years than typical for level {level}'
		else:
			assessment = 'on_track'
			detail = f'Your experience aligns well with level {level} expectations'

		return {
			'assessment': assessment,
			'details': detail,
			'your_yoe': round(yoe, 1),
			'avg_yoe_for_level': expected_yoe,
			'salary_benchmark_k': current_rung['avg_salary_k'],
		}

	def _path_to_dict(self, path: CareerPath) -> Dict:
		"""Serialize a CareerPath to a JSON-friendly dict."""
		return {
			'name': path.name,
			'ladder': path.ladder,
			'current_level': path.current_level,
			'target_level': path.target_level,
			'steps': path.steps,
			'estimated_years': path.estimated_years,
			'salary_delta_k': path.salary_delta_k,
			'transition_skills': path.transition_skills,
			'confidence': path.confidence,
		}


# ── Singleton ──────────────────────────────────────────────────
career_engine = CareerTrajectoryEngine()
