"""
Idempotency support for write endpoints.

Uses Redis when available and falls back to in-memory storage for local/dev.
"""

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.core.logger import logger

try:
	from src.core.redis_client import get_redis_client

	REDIS_AVAILABLE = True
except Exception:
	REDIS_AVAILABLE = False


@dataclass
class IdempotencyRecord:
	status_code: int
	response: Dict[str, Any]
	created_at: float


class IdempotencyStore:
	def __init__(self):
		self._memory: Dict[str, IdempotencyRecord] = {}

	async def get(self, key: str) -> Optional[IdempotencyRecord]:
		if REDIS_AVAILABLE:
			try:
				redis = get_redis_client()
				raw = await redis.get(f'idempotency:{key}')
				if not raw:
					return None
				payload = json.loads(raw)
				return IdempotencyRecord(
					status_code=int(payload.get('status_code', 200)),
					response=payload.get('response', {}),
					created_at=float(payload.get('created_at', time.time())),
				)
			except Exception as e:
				logger.warning(f'Idempotency redis get failed, using memory fallback: {e}')

		record = self._memory.get(key)
		return record

	async def set(self, key: str, status_code: int, response: Dict[str, Any], ttl_seconds: int = 900) -> None:
		record = IdempotencyRecord(status_code=status_code, response=response, created_at=time.time())

		if REDIS_AVAILABLE:
			try:
				redis = get_redis_client()
				payload = json.dumps(
					{
						'status_code': status_code,
						'response': response,
						'created_at': record.created_at,
					}
				)
				await redis.setex(f'idempotency:{key}', ttl_seconds, payload)
				return
			except Exception as e:
				logger.warning(f'Idempotency redis set failed, using memory fallback: {e}')

		self._memory[key] = record


idempotency_store = IdempotencyStore()
