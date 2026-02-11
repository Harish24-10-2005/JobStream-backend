"""
Production middleware for rate limiting, security, logging, and correlation IDs.
"""
import time
import uuid
import logging
from collections import defaultdict
from typing import Callable, Dict
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

import structlog

logger = structlog.get_logger()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiting middleware.
    For production with multiple workers, use Redis-based rate limiting.
    """
    
    def __init__(self, app, requests_per_minute: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/health/ready", "/health/live", "/"]:
            return await call_next(request)
        
        client_ip = self._get_client_ip(request)
        
        # Use simple global rate limiter (Redis or Memory)
        from src.core.rate_limiter import limiter
        
        allowed, remaining = await limiter.is_allowed(client_ip, self.requests_per_minute, self.window_seconds)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": "60"}
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP, considering proxies."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests with timing and correlation ID propagation using structlog."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        import structlog
        
        start_time = time.time()
        
        # Generate or propagate correlation / request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        
        # Store on request state so downstream handlers can access it
        request.state.request_id = request_id
        
        # Bind context vars for structured logging across the full request lifecycle
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )
        
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = (time.time() - start_time) * 1000
        
        # Log request (skip health checks to reduce noise)
        if not request.url.path.startswith("/health"):
            status_code = response.status_code
            log = logger.error if status_code >= 500 else (logger.warning if status_code >= 400 else logger.info)
            
            log(
                "request_processed",
                status_code=status_code,
                process_time_ms=round(process_time, 2),
            )
        
        # Add response headers for correlation and timing
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Limit request body size to prevent memory exhaustion."""
    
    def __init__(self, app, max_size: int = 10 * 1024 * 1024):
        super().__init__(app)
        self.max_size = max_size  # Size in bytes
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        
        if content_length and int(content_length) > self.max_size:
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=413,
                content={"detail": f"Request body too large. Maximum size is {self.max_size // (1024*1024)}MB"},
            )
        
        return await call_next(request)
