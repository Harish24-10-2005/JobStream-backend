"""
Rate Limitation Module

Provides flexible rate limiting strategies:
1. Redis-based (Distributed, Production-ready)
2. Memory-based (Local, Development/Fallback)

Automatically selects Redis if REDIS_URL is configured.
"""
import time
import logging
import redis.asyncio as redis
from collections import defaultdict
from typing import Optional
from fastapi import HTTPException
from src.core.config import settings

logger = logging.getLogger(__name__)

class BaseRateLimiter:
    async def is_allowed(self, key: str, limit: int, window: int) -> bool:
        raise NotImplementedError

class MemoryRateLimiter(BaseRateLimiter):
    """Simple in-memory rate limiter using sliding window."""
    def __init__(self):
        self.requests = defaultdict(list)
        logger.warning("Using In-Memory Rate Limiter (Not suitable for multiple workers)")

    async def is_allowed(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        window_start = now - window
        
        # Filter requests within window
        self.requests[key] = [t for t in self.requests[key] if t > window_start]
        
        if len(self.requests[key]) >= limit:
            return False
            
        self.requests[key].append(now)
        return True

class RedisRateLimiter(BaseRateLimiter):
    """Distributed rate limiter using Redis."""
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        logger.info(f"Using Redis Rate Limiter connected to {redis_url}")

    async def is_allowed(self, key: str, limit: int, window: int) -> bool:
        try:
            current_window = int(time.time() // window)
            redis_key = f"rate_limit:{key}:{current_window}"
            
            # Increment count for current window
            # Using pipelines for atomicity
            async with self.redis.pipeline() as pipe:
                pipe.incr(redis_key)
                pipe.expire(redis_key, window + 1) # Set expiry slightly longer than window
                results = await pipe.execute()
                
            count = results[0]
            return count <= limit
        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            # Fail open if Redis is down, or fallback?
            # For now, allow request but log error to prevent outage
            return True

def get_rate_limiter() -> BaseRateLimiter:
    """Factory to get appropriate rate limiter."""
    if settings.redis_url:
        try:
            return RedisRateLimiter(settings.redis_url)
        except Exception as e:
            logger.error(f"Failed to initialize Redis limiter: {e}")
            return MemoryRateLimiter()
    return MemoryRateLimiter()

# Global instance
limiter = get_rate_limiter()
