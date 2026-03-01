"""
Redis Caching Module
Provides a standardized Redis cache wrapper for Pydantic models and raw data.
"""

import logging
from typing import Optional, Type, TypeVar

import redis.asyncio as redis
from pydantic import BaseModel

from src.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class RedisCache:
	"""
	Redis Cache wrapper with Pydantic model support.
	Falls back to in-memory dictionary if Redis is unavailable.
	"""

	def __init__(self, redis_url: Optional[str] = None):
		self.redis: Optional[redis.Redis] = None
		self._memory_cache = {}

		url = redis_url or settings.redis_url
		if url:
			try:
				self.redis = redis.from_url(
					url,
					encoding='utf-8',
					decode_responses=True,
					socket_connect_timeout=5,
					socket_timeout=5,
				)
				logger.info(f'Redis Cache connected to {url}')
			except Exception as e:
				logger.error(f'Failed to connect to Redis for caching: {e}')

	async def get(self, key: str) -> Optional[str]:
		"""Get raw string value."""
		if self.redis:
			try:
				return await self.redis.get(key)
			except Exception as e:
				logger.error(f'Redis get error: {e}')
				return None
		return self._memory_cache.get(key)

	async def set(self, key: str, value: str, ttl_seconds: int = 3600):
		"""Set raw string value with TTL."""
		if self.redis:
			try:
				await self.redis.set(key, value, ex=ttl_seconds)
			except Exception as e:
				logger.error(f'Redis set error: {e}')
		else:
			self._memory_cache[key] = value

	async def get_model(self, key: str, model_cls: Type[T]) -> Optional[T]:
		"""Get and deserialize a Pydantic model."""
		data = await self.get(key)
		if data:
			try:
				return model_cls.model_validate_json(data)
			except Exception as e:
				logger.error(f'Cache deserialization error for {key}: {e}')
				return None
		return None

	async def set_model(self, key: str, model: BaseModel, ttl_seconds: int = 3600):
		"""Serialize and set a Pydantic model."""
		try:
			json_data = model.model_dump_json()
			await self.set(key, json_data, ttl_seconds)
		except Exception as e:
			logger.error(f'Cache serialization error for {key}: {e}')

	async def delete(self, key: str):
		"""Delete a key."""
		if self.redis:
			try:
				await self.redis.delete(key)
			except Exception as e:
				logger.error(f'Redis delete error: {e}')
		else:
			self._memory_cache.pop(key, None)


# Global instance
cache = RedisCache()
