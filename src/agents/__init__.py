# Agents module - Lazy imports


def get_resume_agent():
	from src.agents.resume_agent import get_resume_agent as _get_resume_agent

	return _get_resume_agent()


def get_cover_letter_agent():
	from src.agents.cover_letter_agent import cover_letter_agent

	return cover_letter_agent


def get_interview_agent():
	from src.agents.interview_agent import get_interview_agent as _get_interview_agent

	return _get_interview_agent()


def get_company_agent():
	from src.agents.company_agent import company_agent

	return company_agent


def get_tracker_agent():
	from src.agents.tracker_agent import JobTrackerAgent

	# Tracker is user-scoped; return class for explicit per-user construction.
	return JobTrackerAgent


__all__ = [
	'get_resume_agent',
	'get_cover_letter_agent',
	'get_interview_agent',
	'get_company_agent',
	'get_tracker_agent',
]
