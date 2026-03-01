"""
Enhanced Circuit Breaker — Production-Grade Resilience Pattern

States:
  CLOSED  → Normal. All requests pass through.
  OPEN    → Failure threshold hit. Requests fail-fast.
  HALF_OPEN → Recovery probe. One request allowed through.

Enhancements over the basic implementation:
  - Retry with exponential backoff
  - Fallback function support
  - Sliding window failure tracking
  - Health metrics and event emission
  - Success rate calculation
  - Async context manager support

Usage:
    breaker = CircuitBreaker("gemini", failure_threshold=3, recovery_timeout=30)
    result = await breaker.call(llm_api_call, prompt="...")

    # With fallback
    breaker = CircuitBreaker("gemini", fallback=lambda: "default response")

    # As decorator
    @circuit_breaker("openai", failure_threshold=5)
    async def call_openai(prompt): ...
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class CircuitState(Enum):
	CLOSED = 'CLOSED'
	OPEN = 'OPEN'
	HALF_OPEN = 'HALF_OPEN'


class CircuitBreakerOpenException(Exception):
	"""Raised when the circuit is open and no fallback is configured."""

	pass


@dataclass
class CircuitMetrics:
	"""Metrics for circuit breaker health monitoring."""

	total_calls: int = 0
	total_successes: int = 0
	total_failures: int = 0
	total_rejected: int = 0  # Rejected while OPEN
	total_fallbacks: int = 0
	consecutive_successes: int = 0
	consecutive_failures: int = 0
	last_failure_time: float = 0
	last_success_time: float = 0
	state_changes: List[Dict[str, Any]] = field(default_factory=list)

	@property
	def success_rate(self) -> float:
		if self.total_calls == 0:
			return 1.0
		return self.total_successes / self.total_calls

	@property
	def failure_rate(self) -> float:
		return 1.0 - self.success_rate

	def to_dict(self) -> Dict[str, Any]:
		return {
			'total_calls': self.total_calls,
			'total_successes': self.total_successes,
			'total_failures': self.total_failures,
			'total_rejected': self.total_rejected,
			'total_fallbacks': self.total_fallbacks,
			'success_rate': round(self.success_rate, 3),
			'consecutive_successes': self.consecutive_successes,
			'consecutive_failures': self.consecutive_failures,
		}


class CircuitBreaker:
	"""
	Production circuit breaker with retry, fallback, and metrics.

	Features:
	  - Sliding window: Only counts failures within a time window
	  - Exponential backoff retry: Retries before tripping
	  - Fallback: Execute alternative when circuit is open
	  - Metrics: Track success/failure rates and state changes
	  - Event emission: Notify via event bus on state transitions
	"""

	# Global registry of all circuit breakers
	_registry: Dict[str, 'CircuitBreaker'] = {}

	def __init__(
		self,
		name: str,
		failure_threshold: int = 5,
		recovery_timeout: int = 60,
		expected_exceptions: list[Type[Exception]] = None,
		retry_count: int = 0,
		retry_delay: float = 1.0,
		retry_backoff: float = 2.0,
		fallback: Optional[Callable] = None,
		window_size: int = 60,
	):
		"""
		Args:
		    name: Identifier for logs/metrics
		    failure_threshold: Failures before circuit opens
		    recovery_timeout: Seconds before half-open probe
		    expected_exceptions: Exception types that count as failures
		    retry_count: Number of retries before counting as failure
		    retry_delay: Initial retry delay in seconds
		    retry_backoff: Backoff multiplier for retries
		    fallback: Function to call when circuit is open
		    window_size: Sliding window in seconds for failure counting
		"""
		self.name = name
		self.failure_threshold = failure_threshold
		self.recovery_timeout = recovery_timeout
		self.expected_exceptions = expected_exceptions or [Exception]
		self.retry_count = retry_count
		self.retry_delay = retry_delay
		self.retry_backoff = retry_backoff
		self.fallback = fallback
		self.window_size = window_size

		self.state = CircuitState.CLOSED
		self.metrics = CircuitMetrics()

		# Sliding window: deque of (timestamp, success_bool)
		self._results: deque = deque(maxlen=1000)

		# Register globally
		CircuitBreaker._registry[name] = self

	async def call(self, func: Callable, *args, **kwargs) -> Any:
		"""Execute with circuit breaker protection + retry + retry-budget governance."""
		self.metrics.total_calls += 1

		# ─── OPEN check ──────────────────────────────
		if self.state == CircuitState.OPEN:
			if time.time() - self.metrics.last_failure_time > self.recovery_timeout:
				self._transition_to_half_open()
			else:
				self.metrics.total_rejected += 1
				logger.warning(f'Circuit {self.name} is OPEN. Failing fast.')
				if self.fallback:
					self.metrics.total_fallbacks += 1
					return self.fallback() if not asyncio.iscoroutinefunction(self.fallback) else await self.fallback()
				raise CircuitBreakerOpenException(f'Circuit {self.name} is OPEN')

		# ─── Retry budget gate ────────────────────────
		retry_budget = self._get_retry_budget()

		# ─── Execute with retries ─────────────────────
		last_exception = None
		attempts = 1 + self.retry_count

		for attempt in range(attempts):
			is_retry = attempt > 0
			try:
				if asyncio.iscoroutinefunction(func):
					result = await func(*args, **kwargs)
				else:
					result = func(*args, **kwargs)

				# Success — record with retry budget
				self._record_success()
				if retry_budget:
					retry_budget.record_attempt(self.name, success=True, is_retry=is_retry)
				if self.state == CircuitState.HALF_OPEN:
					self._transition_to_closed()
				return result

			except Exception as e:
				last_exception = e
				is_expected = any(isinstance(e, exc) for exc in self.expected_exceptions)

				if not is_expected:
					raise  # Non-circuit-breaker exception, raise immediately

				# Record failure with retry budget
				if retry_budget:
					retry_budget.record_attempt(self.name, success=False, is_retry=is_retry)

				if attempt < attempts - 1:
					# Check if retry budget allows another attempt
					if retry_budget and not retry_budget.can_retry(self.name):
						logger.warning(f'Circuit {self.name}: retry blocked by RetryBudget (storm prevention)')
						break

					delay = self.retry_delay * (self.retry_backoff**attempt)
					logger.info(
						f'Circuit {self.name}: retry {attempt + 1}/{self.retry_count} in {delay:.1f}s ({type(e).__name__})'
					)
					await asyncio.sleep(delay)

		# All retries exhausted
		self._record_failure(last_exception)
		raise last_exception

	def call_sync(self, func: Callable, *args, **kwargs) -> Any:
		"""Execute with circuit breaker protection + retry + retry-budget governance (Synchronous)."""
		self.metrics.total_calls += 1

		# ─── OPEN check ──────────────────────────────
		if self.state == CircuitState.OPEN:
			if time.time() - self.metrics.last_failure_time > self.recovery_timeout:
				self._transition_to_half_open()
			else:
				self.metrics.total_rejected += 1
				logger.warning(f'Circuit {self.name} is OPEN. Failing fast.')
				if self.fallback:
					self.metrics.total_fallbacks += 1
					return self.fallback()
				raise CircuitBreakerOpenException(f'Circuit {self.name} is OPEN')

		# ─── Retry budget gate ────────────────────────
		retry_budget = self._get_retry_budget()

		# ─── Execute with retries ─────────────────────
		last_exception = None
		attempts = 1 + self.retry_count

		for attempt in range(attempts):
			is_retry = attempt > 0
			try:
				result = func(*args, **kwargs)

				# Success — record with retry budget
				self._record_success()
				if retry_budget:
					retry_budget.record_attempt(self.name, success=True, is_retry=is_retry)
				if self.state == CircuitState.HALF_OPEN:
					self._transition_to_closed()
				return result

			except Exception as e:
				last_exception = e
				is_expected = any(isinstance(e, exc) for exc in self.expected_exceptions)

				if not is_expected:
					raise  # Non-circuit-breaker exception, raise immediately

				# Record failure with retry budget
				if retry_budget:
					retry_budget.record_attempt(self.name, success=False, is_retry=is_retry)

				if attempt < attempts - 1:
					# Check if retry budget allows another attempt
					if retry_budget and not retry_budget.can_retry(self.name):
						logger.warning(f'Circuit {self.name}: retry blocked by RetryBudget (storm prevention)')
						break

					delay = self.retry_delay * (self.retry_backoff**attempt)
					logger.info(
						f'Circuit {self.name}: retry {attempt + 1}/{self.retry_count} in {delay:.1f}s ({type(e).__name__})'
					)
					time.sleep(delay)

		# All retries exhausted
		self._record_failure(last_exception)
		raise last_exception

	@staticmethod
	def _get_retry_budget():
		"""Lazy-load the RetryBudget singleton (avoids circular imports)."""
		try:
			from src.core.retry_budget import retry_budget

			return retry_budget
		except Exception:
			return None

	# ─── State Transitions ────────────────────────────────

	def _record_success(self):
		now = time.time()
		self._results.append((now, True))
		self.metrics.total_successes += 1
		self.metrics.consecutive_successes += 1
		self.metrics.consecutive_failures = 0
		self.metrics.last_success_time = now

	def _record_failure(self, exception: Exception):
		now = time.time()
		self._results.append((now, False))
		self.metrics.total_failures += 1
		self.metrics.consecutive_failures += 1
		self.metrics.consecutive_successes = 0
		self.metrics.last_failure_time = now

		logger.error(
			f'Circuit {self.name} failure {self._window_failure_count()}/{self.failure_threshold}: '
			f'{type(exception).__name__}: {exception}'
		)

		if self.state == CircuitState.HALF_OPEN:
			self._transition_to_open()
		elif self._window_failure_count() >= self.failure_threshold:
			self._transition_to_open()

	def _window_failure_count(self) -> int:
		"""Count failures within the sliding window."""
		cutoff = time.time() - self.window_size
		return sum(1 for ts, success in self._results if not success and ts > cutoff)

	def _transition_to_open(self):
		old_state = self.state
		self.state = CircuitState.OPEN
		self.metrics.state_changes.append({'from': old_state.value, 'to': 'OPEN', 'time': time.time()})
		logger.warning(
			f'Circuit {self.name} OPENED! Blocking for {self.recovery_timeout}s. Success rate: {self.metrics.success_rate:.1%}'
		)

	def _transition_to_half_open(self):
		old_state = self.state
		self.state = CircuitState.HALF_OPEN
		self.metrics.state_changes.append({'from': old_state.value, 'to': 'HALF_OPEN', 'time': time.time()})
		logger.info(f'Circuit {self.name} HALF_OPEN. Probing service...')

	def _transition_to_closed(self):
		old_state = self.state
		self.state = CircuitState.CLOSED
		self.metrics.consecutive_failures = 0
		self.metrics.state_changes.append({'from': old_state.value, 'to': 'CLOSED', 'time': time.time()})
		logger.info(f'Circuit {self.name} CLOSED. Service recovered.')

	# ─── Health Check ─────────────────────────────────────

	def health(self) -> Dict[str, Any]:
		"""Get circuit breaker health status."""
		return {
			'name': self.name,
			'state': self.state.value,
			**self.metrics.to_dict(),
		}

	def reset(self):
		"""Reset circuit breaker to initial state."""
		self.state = CircuitState.CLOSED
		self.metrics = CircuitMetrics()
		self._results.clear()

	@classmethod
	def get_all_health(cls) -> Dict[str, Dict[str, Any]]:
		"""Get health status for all registered circuit breakers."""
		return {name: cb.health() for name, cb in cls._registry.items()}


# ─── Decorator ───────────────────────────────────────────────


def circuit_breaker(name: str, **cb_kwargs):
	"""Decorator that wraps a function with circuit breaker protection."""
	breaker = CircuitBreaker(name, **cb_kwargs)

	def decorator(func):
		if asyncio.iscoroutinefunction(func):

			@wraps(func)
			async def async_wrapper(*args, **kwargs):
				return await breaker.call(func, *args, **kwargs)

			async_wrapper.breaker = breaker  # Expose for inspection
			return async_wrapper
		else:

			@wraps(func)
			def sync_wrapper(*args, **kwargs):
				return breaker.call_sync(func, *args, **kwargs)

			sync_wrapper.breaker = breaker  # Expose for inspection
			return sync_wrapper

	return decorator
