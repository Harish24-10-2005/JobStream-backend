"""
Distributed lock helper.

Uses Redis SET NX EX when available and falls back to per-process in-memory locks.
"""

import time
import uuid
from typing import Dict, Optional, Tuple

from src.core.logger import logger

try:
	from src.core.redis_client import get_redis_client

	REDIS_AVAILABLE = True
except Exception:
	REDIS_AVAILABLE = False


class DistributedLockManager:
	def __init__(self):
		self._memory_locks: Dict[str, Tuple[str, float]] = {}

	async def acquire(self, key: str, ttl_seconds: int = 60) -> Optional[str]:
		token = str(uuid.uuid4())

		if REDIS_AVAILABLE:
			try:
				redis = get_redis_client()
				ok = await redis.set(f'lock:{key}', token, nx=True, ex=ttl_seconds)
				return token if ok else None
			except Exception as e:
				logger.warning(f'Redis lock acquire failed, using memory fallback: {e}')

		now = time.time()
		existing = self._memory_locks.get(key)
		if existing and existing[1] > now:
			return None
		self._memory_locks[key] = (token, now + ttl_seconds)
		return token

	async def release(self, key: str, token: str) -> bool:
		if REDIS_AVAILABLE:
			try:
				redis = get_redis_client()
				current = await redis.get(f'lock:{key}')
				if current and str(current) == token:
					await redis.delete(f'lock:{key}')
					return True
				return False
			except Exception as e:
				logger.warning(f'Redis lock release failed, using memory fallback: {e}')

		existing = self._memory_locks.get(key)
		if not existing:
			return False
		if existing[0] != token:
			return False
		self._memory_locks.pop(key, None)
		return True


distributed_lock_manager = DistributedLockManager()
