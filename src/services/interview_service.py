"""
Interview Service - Manages real-time interview sessions and message history.
"""

import logging
from typing import Dict, List, Optional

from src.services.supabase_client import supabase_client

logger = logging.getLogger(__name__)


class InterviewService:
	"""Service for managing interview sessions in Supabase."""

	def __init__(self):
		self.client = supabase_client

	async def create_session(self, user_id: str, role: str, company: str, persona: str) -> Optional[str]:
		"""Start a new interview session.
		Schema: interview_sessions(id, user_id, job_id, interview_type, questions, answers, feedback, score, conducted_at, duration_minutes)
		"""
		try:
			data = {
				'user_id': user_id,
				'interview_type': role or 'general',
				'questions': [],  # will accumulate AI questions
				'answers': [],    # will accumulate user answers
				'feedback': {'company': company, 'persona': persona, 'status': 'active'},
			}
			response = self.client.table('interview_sessions').insert(data).execute()
			if response.data:
				return response.data[0]['id']
		except Exception as e:
			logger.error(f'Failed to create interview session: {e}')
			return None

	async def log_message(self, session_id: str, role: str, content: str, user_id: Optional[str] = None):
		"""Log a chat message by appending to questions (ai) or answers (user) JSONB arrays."""
		try:
			# Fetch current arrays
			query = self.client.table('interview_sessions').select('questions, answers').eq('id', session_id)
			if user_id:
				query = query.eq('user_id', user_id)
			resp = query.single().execute()
			if not resp.data:
				return

			questions = resp.data.get('questions') or []
			answers = resp.data.get('answers') or []

			if role == 'ai':
				questions.append({'content': content, 'index': len(questions)})
				update_query = self.client.table('interview_sessions').update({'questions': questions}).eq('id', session_id)
				if user_id:
					update_query = update_query.eq('user_id', user_id)
				update_query.execute()
			else:
				answers.append({'content': content, 'index': len(answers)})
				update_query = self.client.table('interview_sessions').update({'answers': answers}).eq('id', session_id)
				if user_id:
					update_query = update_query.eq('user_id', user_id)
				update_query.execute()
		except Exception as e:
			logger.error(f'Failed to log message: {e}')

	async def get_session_history(self, session_id: str, user_id: Optional[str] = None) -> List[Dict]:
		"""Get full chat history for a session by interleaving questions and answers."""
		try:
			query = self.client.table('interview_sessions').select('questions, answers').eq('id', session_id)
			if user_id:
				query = query.eq('user_id', user_id)
			response = query.single().execute()
			if not response.data:
				return []

			# Reconstruct ordered history from questions + answers arrays
			questions = response.data.get('questions') or []
			answers = response.data.get('answers') or []

			history = []
			for q in questions:
				history.append({'role': 'ai', 'content': q.get('content', ''), 'index': q.get('index', 0)})
			for a in answers:
				history.append({'role': 'user', 'content': a.get('content', ''), 'index': a.get('index', 0)})

			history.sort(key=lambda x: x.get('index', 0))
			return history
		except Exception as e:
			logger.error(f'Failed to get history: {e}')
			return []

	async def end_session(self, session_id: str, feedback: Dict):
		"""End session and save feedback."""
		try:
			self.client.table('interview_sessions').update({'feedback': feedback}).eq(
				'id', session_id
			).execute()
		except Exception as e:
			logger.error(f'Failed to end session: {e}')


interview_service = InterviewService()
