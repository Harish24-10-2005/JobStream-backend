"""
Network Service - Manages persistence of networking leads.
"""

import logging
from typing import Dict, List

from src.models.profile import NetworkMatch
from src.services.supabase_client import supabase_client

logger = logging.getLogger(__name__)


class NetworkService:
	"""Service for managing network leads in Supabase interactively."""

	def __init__(self):
		self.client = supabase_client

	async def save_lead(self, user_id: str, lead: NetworkMatch):
		"""Save a new network lead to the database."""
		try:
			# Check if already exists to avoid duplicates
			existing = (
				self.client.table('user_network_leads')
				.select('id')
				.eq('user_id', user_id)
				.eq('profile_url', lead.profile_url)
				.execute()
			)

			if existing.data:
				logger.debug(f'Lead already exists: {lead.name}')
				return existing.data[0]['id']

			data = {
				'user_id': user_id,
				'name': lead.name,
				'headline': lead.headline,
				'company': lead.company_match or 'Unknown',  # Fallback
				'profile_url': lead.profile_url,
				'connection_type': lead.connection_type,
				'match_detail': lead.college_match or lead.location_match or lead.company_match,
				'confidence_score': lead.confidence_score,
				'outreach_draft': lead.outreach_draft,
			}

			response = self.client.table('user_network_leads').insert(data).execute()
			if response.data:
				logger.info(f'Saved lead: {lead.name}')
				return response.data[0]['id']

		except Exception as e:
			logger.error(f'Failed to save network lead: {e}')
			return None

	async def get_saved_leads(self, user_id: str, limit: int = 50) -> List[Dict]:
		"""Get all saved leads for a user."""
		try:
			response = (
				self.client.table('user_network_leads')
				.select('*')
				.eq('user_id', user_id)
				.order('created_at', desc=True)
				.limit(limit)
				.execute()
			)
			return response.data or []
		except Exception as e:
			logger.error(f'Failed to fetch leads for user {user_id}: {e}')
			return []

	async def update_outreach(self, lead_id: str, new_text: str, user_id: str):
		"""Update the outreach message draft."""
		try:
			self.client.table('user_network_leads').update({'outreach_draft': new_text}).eq('id', lead_id).eq(
				'user_id', user_id
			).execute()
		except Exception as e:
			logger.error(f'Failed to update outreach for lead {lead_id}: {e}')


network_service = NetworkService()
