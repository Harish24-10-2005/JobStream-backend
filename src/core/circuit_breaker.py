"""
Circuit Breaker Pattern for JobAI
Prevents cascading failures when external services (LLMs, APIs) are down.

States:
- CLOSED: Normal operation. Requests pass through.
- OPEN: Failure threshold reached. Request fail immediately.
- HALF-OPEN: Recovery timeout passed. Allow one request to check stability.
"""

import asyncio
import time
import logging
from enum import Enum
from functools import wraps
from typing import Callable, Any, Optional, Type

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreakerOpenException(Exception):
    """Raised when the circuit is open."""
    pass

class CircuitBreaker:
    def __init__(
        self, 
        name: str, 
        failure_threshold: int = 5, 
        recovery_timeout: int = 60,
        expected_exceptions: list[Type[Exception]] = None
    ):
        """
        Args:
            name: Identifier for logs/metrics
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before checking service again
            expected_exceptions: List of exception types that count as failures
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions or [Exception]
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute the function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self._transition_to_half_open()
            else:
                logger.warning(f"Circuit {self.name} is OPEN. Failing fast.")
                raise CircuitBreakerOpenException(f"Circuit {self.name} is OPEN")
                
        try:
            result = await func(*args, **kwargs)
            
            if self.state == CircuitState.HALF_OPEN:
                self._transition_to_closed()
                
            return result
            
        except Exception as e:
            # Check if exception should trigger failure
            if any(isinstance(e, exc) for exc in self.expected_exceptions):
                self._handle_failure(e)
            raise e

    def _handle_failure(self, exception: Exception):
        self.failure_count += 1
        self.last_failure_time = time.time()
        logger.error(f"Circuit {self.name} failure {self.failure_count}/{self.failure_threshold}: {exception}")
        
        if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
            self._transition_to_open()

    def _transition_to_open(self):
        self.state = CircuitState.OPEN
        logger.warning(f"Circuit {self.name} opened! Blocking requests for {self.recovery_timeout}s.")

    def _transition_to_half_open(self):
        self.state = CircuitState.HALF_OPEN
        logger.info(f"Circuit {self.name} half-open. Probing service...")

    def _transition_to_closed(self):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        logger.info(f"Circuit {self.name} closed. Service recovered.")

# Decorator for easy usage
def circuit_breaker(name: str, **cb_kwargs):
    breaker = CircuitBreaker(name, **cb_kwargs)
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        # Attach breaker to wrapper for inspection if needed
        wrapper.breaker = breaker
        return wrapper
    return decorator
