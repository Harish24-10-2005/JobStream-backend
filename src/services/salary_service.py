import os
from typing import Dict, List, Optional

from supabase import Client, create_client

from src.core.console import console
from src.core import db_tables



class SalaryService:
	def __init__(self):
		self.url = os.getenv('SUPABASE_URL')
		self.key = os.getenv('SUPABASE_SERVICE_KEY')

		if not self.url or not self.key:
			console.warning('Supabase credentials missing. SalaryService disabled.')
			self.client = None
		else:
			self.client: Client = create_client(self.url, self.key)

	async def create_battle(self, user_id: str, data: Dict) -> str:
		"""Create a new negotiation battle session.
		Schema: user_salary_battles(id, user_id, job_id, initial_offer, target_salary,
		         current_offer, difficulty, status, created_at)
		"""
		if not self.client:
			raise RuntimeError('SalaryService is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY.')

		try:
			payload = {
				'user_id': user_id,
				'job_id': data.get('job_id'),
				'initial_offer': data.get('initial_offer'),
				'target_salary': data.get('target_salary'),
				'current_offer': data.get('initial_offer'),
				'difficulty': data.get('difficulty', 'medium'),
				'status': 'active',
			}

			response = self.client.table(db_tables.SALARY_BATTLES).insert(payload).execute()
			if response.data:
				return response.data[0]['id']
			return None
		except Exception as e:
			console.error(f'Error creating battle: {e}')
			return None

	async def log_message(self, battle_id: str, role: str, content: str, offer_amount: Optional[int] = None):
		"""Log a message in the battle by inserting into user_salary_messages table."""
		if not self.client:
			return

		try:
			data = {'battle_id': battle_id, 'role': role, 'content': content, 'offer_amount': offer_amount}
			self.client.table(db_tables.SALARY_MESSAGES).insert(data).execute()
		except Exception as e:
			console.error(f'Error logging salary message: {e}')

	async def update_battle_status(self, battle_id: str, status: str, current_offer: int = None):
		"""Update the battle state (e.g. game over, new offer)."""
		if not self.client:
			return

		try:
			payload: Dict = {'status': status}
			if current_offer:
				payload['current_offer'] = current_offer

			self.client.table(db_tables.SALARY_BATTLES).update(payload).eq('id', battle_id).execute()
		except Exception as e:
			console.error(f'Error updating battle: {e}')

	async def get_battle_history(self, battle_id: str) -> List[Dict]:
		"""Get chat history from user_salary_messages table."""
		if not self.client:
			return []

		try:
			response = (
				self.client.table(db_tables.SALARY_MESSAGES)
				.select('role, content, offer_amount')
				.eq('battle_id', battle_id)
				.order('created_at', desc=False)
				.execute()
			)
			return response.data or []
		except Exception as e:
			console.error(f'Error fetching history: {e}')
			return []


salary_service = SalaryService()
