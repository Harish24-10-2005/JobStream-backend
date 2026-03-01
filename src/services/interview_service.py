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
		"""Start a new interview session."""
		try:
			data = {'user_id': user_id, 'role': role, 'company': company, 'persona': persona, 'status': 'active'}
			response = self.client.table('user_interview_sessions').insert(data).execute()
			if response.data:
				return response.data[0]['id']
		except Exception as e:
			logger.error(f'Failed to create interview session: {e}')
			return None

	async def log_message(self, session_id: str, role: str, content: str):
		"""Log a chat message (user or ai)."""
		try:
			self.client.table('user_interview_messages').insert(
				{'session_id': session_id, 'role': role, 'content': content}
			).execute()
		except Exception as e:
			logger.error(f'Failed to log message: {e}')

	async def get_session_history(self, session_id: str) -> List[Dict]:
		"""Get full chat history for a session."""
		try:
			response = (
				self.client.table('user_interview_messages')
				.select('*')
				.eq('session_id', session_id)
				.order('created_at')
				.execute()
			)
			return response.data or []
		except Exception as e:
			logger.error(f'Failed to get history: {e}')
			return []

	async def end_session(self, session_id: str, feedback: Dict):
		"""End session and save feedback."""
		try:
			self.client.table('user_interview_sessions').update({'status': 'completed', 'feedback_summary': feedback}).eq(
				'id', session_id
			).execute()
		except Exception as e:
			logger.error(f'Failed to end session: {e}')


interview_service = InterviewService()
