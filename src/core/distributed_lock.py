"""
Distributed lock helper.

Uses Redis SET NX EX when available and falls back to per-process in-memory locks.
"""

import time
import uuid
from typing import Dict, Optional, Tuple

from src.core.logger import logger
from src.core.config import settings

try:
	from src.core.redis_client import get_redis_client

	REDIS_AVAILABLE = True
except Exception:
	REDIS_AVAILABLE = False


class DistributedLockManager:
	def __init__(self):
		self._memory_locks: Dict[str, Tuple[str, float]] = {}
		self._redis_unavailable_until: float = 0.0
		self._redis_retry_seconds: float = 30.0

	async def acquire(self, key: str, ttl_seconds: int = 60) -> Optional[str]:
		token = str(uuid.uuid4())

		if REDIS_AVAILABLE and self._redis_unavailable_until <= time.time():
			try:
				redis = get_redis_client()
				if redis is None:
					raise RuntimeError('Redis client unavailable')
				ok = await redis.set(f'lock:{key}', token, nx=True, ex=ttl_seconds)
				return token if ok else None
			except Exception as e:
				self._redis_unavailable_until = time.time() + self._redis_retry_seconds
				logger.warning(
					f'Redis lock acquire failed, using memory fallback for {self._redis_retry_seconds:.0f}s: {e}'
				)

		now = time.time()
		if settings.is_production:
			raise RuntimeError('Distributed lock backend unavailable in production')
		existing = self._memory_locks.get(key)
		if existing and existing[1] > now:
			return None
		self._memory_locks[key] = (token, now + ttl_seconds)
		return token

	async def release(self, key: str, token: str) -> bool:
		if REDIS_AVAILABLE and self._redis_unavailable_until <= time.time():
			try:
				redis = get_redis_client()
				if redis is None:
					raise RuntimeError('Redis client unavailable')
				lock_key = f'lock:{key}'
				# Atomic compare-and-delete to avoid race conditions.
				release_script = (
					"if redis.call('GET', KEYS[1]) == ARGV[1] then "
					"return redis.call('DEL', KEYS[1]) "
					"else return 0 end"
				)
				deleted = await redis.eval(release_script, 1, lock_key, token)
				return bool(deleted)
			except Exception as e:
				self._redis_unavailable_until = time.time() + self._redis_retry_seconds
				logger.warning(
					f'Redis lock release failed, using memory fallback for {self._redis_retry_seconds:.0f}s: {e}'
				)

		existing = self._memory_locks.get(key)
		if settings.is_production and existing is None:
			raise RuntimeError('Distributed lock backend unavailable in production')
		if not existing:
			return False
		if existing[0] != token:
			return False
		self._memory_locks.pop(key, None)
		return True


distributed_lock_manager = DistributedLockManager()
