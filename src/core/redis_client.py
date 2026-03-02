import os
from typing import Optional

import redis.asyncio as redis
from dotenv import load_dotenv
from src.core.config import settings

load_dotenv()


class RedisClient:
	_instance: Optional[redis.Redis] = None
	_unavailable: bool = False

	@classmethod
	def get_instance(cls) -> Optional[redis.Redis]:
		"""Return a Redis client or None when Redis is not configured / reachable."""
		if cls._unavailable:
			return None
		if cls._instance is None:
			redis_url = settings.redis_url or os.getenv('REDIS_URL', '')
			if not redis_url:
				cls._unavailable = True
				return None
			try:
				cls._instance = redis.from_url(
					redis_url,
					decode_responses=True,
					socket_connect_timeout=1,
					socket_timeout=1,
				)
			except Exception:
				cls._unavailable = True
				return None
		return cls._instance

	@classmethod
	async def close(cls):
		if cls._instance:
			await cls._instance.close()
			cls._instance = None


def get_redis_client() -> Optional[redis.Redis]:
	"""Return a Redis client or None if Redis is not available."""
	return RedisClient.get_instance()
