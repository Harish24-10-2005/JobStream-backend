
import redis.asyncio as redis
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class RedisClient:
    _instance: Optional[redis.Redis] = None

    @classmethod
    def get_instance(cls) -> redis.Redis:
        if cls._instance is None:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            cls._instance = redis.from_url(redis_url, decode_responses=True)
        return cls._instance

    @classmethod
    async def close(cls):
        if cls._instance:
            await cls._instance.close()
            cls._instance = None

def get_redis_client() -> redis.Redis:
    return RedisClient.get_instance()
