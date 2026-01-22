"""
Redis-based Rate Limiting for Production
Replaces in-memory rate limiting for multi-worker deployments
"""
import time
import logging
from typing import Callable, Optional, Any
from collections import defaultdict
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Try to import redis, fallback to in-memory if not available
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    aioredis = None  # type: ignore
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, falling back to in-memory rate limiting")


class RedisRateLimiter:
    """Redis-based rate limiter using sliding window algorithm."""
    
    def __init__(self, redis_url: str, requests_per_minute: int = 100, window_seconds: int = 60):
        self.redis_url = redis_url
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self._redis: Optional[Any] = None
    
    async def get_redis(self) -> Any:
        """Get or create Redis connection."""
        if self._redis is None and aioredis is not None:
            self._redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return self._redis
    
    async def is_rate_limited(self, key: str) -> tuple[bool, int]:
        """
        Check if a key is rate limited.
        Returns (is_limited, remaining_requests)
        """
        try:
            r = await self.get_redis()
            now = time.time()
            window_start = now - self.window_seconds
            
            # Use Redis pipeline for atomic operations
            pipe = r.pipeline()
            
            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(now): now})
            
            # Set expiry
            pipe.expire(key, self.window_seconds)
            
            results = await pipe.execute()
            current_requests = results[1]
            
            remaining = max(0, self.requests_per_minute - current_requests - 1)
            is_limited = current_requests >= self.requests_per_minute
            
            return is_limited, remaining
            
        except Exception as e:
            logger.error(f"Redis rate limit error: {e}")
            # Fail open - don't block requests if Redis fails
            return False, self.requests_per_minute
    
    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()


class ProductionRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Production-ready rate limiting middleware.
    Uses Redis when available, falls back to in-memory.
    """
    
    def __init__(
        self, 
        app, 
        redis_url: Optional[str] = None,
        requests_per_minute: int = 100, 
        window_seconds: int = 60
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        
        # Use Redis if available and URL provided
        if REDIS_AVAILABLE and redis_url:
            self.limiter = RedisRateLimiter(redis_url, requests_per_minute, window_seconds)
            self.use_redis = True
            logger.info("Using Redis-based rate limiting")
        else:
            # Fallback to in-memory
            from collections import defaultdict
            self.requests = defaultdict(list)
            self.use_redis = False
            logger.info("Using in-memory rate limiting")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ["/api/health", "/api/ready", "/api/live", "/health", "/"]:
            return await call_next(request)
        
        client_ip = self._get_client_ip(request)
        key = f"rate_limit:{client_ip}"
        
        if self.use_redis:
            is_limited, remaining = await self.limiter.is_rate_limited(key)
        else:
            is_limited, remaining = self._check_memory_limit(client_ip)
        
        if is_limited:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={
                    "Retry-After": str(self.window_seconds),
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                }
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response
    
    def _check_memory_limit(self, client_ip: str) -> tuple[bool, int]:
        """In-memory rate limit check (fallback)."""
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old requests
        self.requests[client_ip] = [t for t in self.requests[client_ip] if t > window_start]
        
        current = len(self.requests[client_ip])
        
        if current >= self.requests_per_minute:
            return True, 0
        
        self.requests[client_ip].append(now)
        return False, self.requests_per_minute - current - 1
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP, considering proxies."""
        # Check for forwarded headers (from nginx/load balancer)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
