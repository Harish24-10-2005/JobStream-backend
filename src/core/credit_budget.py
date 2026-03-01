"""
Credit and budget controls for production API usage governance.

Supports:
- per-user daily query credits
- per-user daily token budget (estimated/request-based)
- Redis-backed shared state with in-memory fallback
"""

import json
from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional

from src.core.logger import logger
from src.core.config import settings

try:
	from src.core.redis_client import get_redis_client

	REDIS_AVAILABLE = True
except Exception:
	REDIS_AVAILABLE = False


@dataclass
class CreditBalance:
	query_remaining: int
	token_remaining: int
	day: str


class CreditBudgetManager:
	def __init__(self, default_daily_queries: int = 200, default_daily_tokens: int = 150000):
		self.default_daily_queries = default_daily_queries
		self.default_daily_tokens = default_daily_tokens
		self._memory: Dict[str, Dict[str, int]] = {}

	def _key(self, user_key: str, day: str) -> str:
		return f'credits:{user_key}:{day}'

	async def _get_redis_bucket(self, user_key: str, day: str) -> Optional[Dict[str, int]]:
		if not REDIS_AVAILABLE:
			return None
		try:
			redis = get_redis_client()
			raw = await redis.get(self._key(user_key, day))
			if not raw:
				return None
			parsed = json.loads(raw)
			return {
				'queries': int(parsed.get('queries', self.default_daily_queries)),
				'tokens': int(parsed.get('tokens', self.default_daily_tokens)),
			}
		except Exception as e:
			logger.warning(f'Credit redis read failed, fallback memory: {e}')
			return None

	async def _set_redis_bucket(self, user_key: str, day: str, bucket: Dict[str, int]) -> bool:
		if not REDIS_AVAILABLE:
			return False
		try:
			redis = get_redis_client()
			key = self._key(user_key, day)
			await redis.set(key, json.dumps(bucket))
			await redis.expire(key, 172800)
			return True
		except Exception as e:
			logger.warning(f'Credit redis write failed, fallback memory: {e}')
			return False

	async def get_balance(self, user_key: str) -> CreditBalance:
		day = date.today().isoformat()
		bucket = await self._get_redis_bucket(user_key, day)
		if bucket is None:
			mem_key = self._key(user_key, day)
			if mem_key not in self._memory:
				self._memory[mem_key] = {'queries': self.default_daily_queries, 'tokens': self.default_daily_tokens}
			bucket = self._memory[mem_key]
		return CreditBalance(query_remaining=bucket['queries'], token_remaining=bucket['tokens'], day=day)

	async def consume(self, user_key: str, query_cost: int = 1, token_cost: int = 0) -> CreditBalance:
		day = date.today().isoformat()
		balance = await self.get_balance(user_key)

		new_queries = max(0, balance.query_remaining - max(0, query_cost))
		new_tokens = max(0, balance.token_remaining - max(0, token_cost))
		bucket = {'queries': new_queries, 'tokens': new_tokens}

		saved = await self._set_redis_bucket(user_key, day, bucket)
		if not saved:
			self._memory[self._key(user_key, day)] = bucket

		return CreditBalance(query_remaining=new_queries, token_remaining=new_tokens, day=day)

	async def can_consume(self, user_key: str, query_cost: int = 1, token_cost: int = 0) -> bool:
		balance = await self.get_balance(user_key)
		return balance.query_remaining >= max(0, query_cost) and balance.token_remaining >= max(0, token_cost)


credit_budget_manager = CreditBudgetManager()
credit_budget_manager.default_daily_queries = settings.credit_daily_query_limit
credit_budget_manager.default_daily_tokens = settings.credit_daily_token_limit
