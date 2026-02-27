"""
Retry Budget — Global Retry Storm Prevention

Prevents cascading retry storms where multiple agents all retry
simultaneously, overwhelming external APIs. Enforces:
  - Per-service retry rate limits
  - Global retry-to-success ratio cap
  - Cooldown periods after excessive retries

Works alongside the CircuitBreaker — the circuit breaker handles
individual service health, while RetryBudget handles system-wide
retry pressure.

Usage:
    from src.core.retry_budget import retry_budget
    
    if retry_budget.can_retry("groq"):
        # proceed with retry
        retry_budget.record_attempt("groq", success=False)
    else:
        # back off, budget exhausted
        raise RetryBudgetExhausted("groq")
"""

import logging
import time
from collections import defaultdict, deque
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class RetryBudgetExhausted(Exception):
    """Raised when retry budget for a service is exhausted."""
    def __init__(self, service: str, msg: str = ""):
        self.service = service
        super().__init__(msg or f"Retry budget exhausted for {service}")


@dataclass
class ServiceStats:
    """Tracks attempt history for a single service."""
    attempts: deque = field(default_factory=lambda: deque(maxlen=200))
    successes: int = 0
    failures: int = 0
    retries: int = 0
    last_retry: float = 0.0
    cooldown_until: float = 0.0


class RetryBudget:
    """
    System-wide retry budget manager.
    
    Prevents retry storms by enforcing:
    1. Max retries per minute per service
    2. Max retry-to-total ratio (prevent > 20% retries)
    3. Cooldown periods when limits are hit
    
    Thread-safe for asyncio (single-threaded event loop).
    """

    def __init__(
        self,
        max_retries_per_minute: int = 20,
        max_retry_ratio: float = 0.2,
        cooldown_seconds: float = 30.0,
        window_seconds: float = 60.0,
    ):
        self.max_retries_per_minute = max_retries_per_minute
        self.max_retry_ratio = max_retry_ratio
        self.cooldown_seconds = cooldown_seconds
        self.window_seconds = window_seconds
        self._services: Dict[str, ServiceStats] = defaultdict(ServiceStats)

    def _prune_old_attempts(self, stats: ServiceStats):
        """Remove attempts outside the sliding window."""
        cutoff = time.time() - self.window_seconds
        while stats.attempts and stats.attempts[0][0] < cutoff:
            stats.attempts.popleft()

    def can_retry(self, service: str) -> bool:
        """
        Check if a retry is allowed for this service.
        
        Returns False if:
          - Service is in cooldown period
          - Retries per minute exceeded
          - Retry ratio too high
        """
        stats = self._services[service]
        now = time.time()

        # Check cooldown
        if now < stats.cooldown_until:
            remaining = stats.cooldown_until - now
            logger.debug(f"[RetryBudget] {service} in cooldown for {remaining:.1f}s more")
            return False

        # Prune old entries
        self._prune_old_attempts(stats)

        # Count recent retries
        recent_retries = sum(1 for ts, is_retry in stats.attempts if is_retry)
        if recent_retries >= self.max_retries_per_minute:
            # Enter cooldown
            stats.cooldown_until = now + self.cooldown_seconds
            logger.warning(
                f"[RetryBudget] {service}: {recent_retries} retries in window, "
                f"entering {self.cooldown_seconds}s cooldown"
            )
            return False

        # Check ratio
        total = len(stats.attempts)
        if total >= 10:  # need enough data for ratio to be meaningful
            ratio = recent_retries / total
            if ratio > self.max_retry_ratio:
                stats.cooldown_until = now + self.cooldown_seconds
                logger.warning(
                    f"[RetryBudget] {service}: retry ratio {ratio:.2%} exceeds "
                    f"{self.max_retry_ratio:.0%}, entering cooldown"
                )
                return False

        return True

    def record_attempt(self, service: str, success: bool, is_retry: bool = False):
        """
        Record an attempt (success or failure).
        
        Args:
            service: Service identifier (e.g. 'groq', 'openrouter')
            success: Whether the attempt succeeded
            is_retry: Whether this was a retry of a previous failure
        """
        stats = self._services[service]
        stats.attempts.append((time.time(), is_retry))

        if success:
            stats.successes += 1
        else:
            stats.failures += 1

        if is_retry:
            stats.retries += 1
            stats.last_retry = time.time()

    # ── Health & Diagnostics ────────────────────────────────────

    def get_health(self, service: str) -> Dict[str, Any]:
        """Get retry health status for a service."""
        stats = self._services[service]
        self._prune_old_attempts(stats)

        now = time.time()
        recent_retries = sum(1 for ts, is_retry in stats.attempts if is_retry)
        total = len(stats.attempts)

        return {
            "service": service,
            "can_retry": self.can_retry(service),
            "recent_retries": recent_retries,
            "recent_total": total,
            "retry_ratio": round(recent_retries / total, 3) if total > 0 else 0,
            "in_cooldown": now < stats.cooldown_until,
            "cooldown_remaining_s": max(0, round(stats.cooldown_until - now, 1)),
            "lifetime_successes": stats.successes,
            "lifetime_failures": stats.failures,
            "lifetime_retries": stats.retries,
        }

    def get_all_health(self) -> Dict[str, Any]:
        """Get retry health for all tracked services."""
        return {
            service: self.get_health(service)
            for service in self._services
        }

    def reset(self, service: Optional[str] = None):
        """Reset stats for a service, or all services if None."""
        if service:
            self._services.pop(service, None)
        else:
            self._services.clear()

    def stats(self) -> Dict[str, Any]:
        """Summary stats for health checks."""
        return {
            "tracked_services": list(self._services.keys()),
            "services_in_cooldown": [
                s for s, stats in self._services.items()
                if time.time() < stats.cooldown_until
            ],
        }


# ── Singleton ───────────────────────────────────────────────────

retry_budget = RetryBudget()
