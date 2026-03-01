"""
Structured Logger — JSON-formatted logging with correlation IDs

Replaces scattered logger.info() calls with structured, queryable logs
compatible with ELK, Loki, CloudWatch, or any JSON log aggregator.

Features:
  - Correlation IDs linking all logs in a pipeline run
  - Automatic PII redaction in log payloads
  - Typed log categories (agent, llm, pipeline, security)
  - Performance timing helpers

Usage:
    from src.core.structured_logger import slog

    slog.agent("resume_agent", "tailor_started", job_title="SWE at Google")
    slog.llm("groq", "llama-3.1-8b", latency_ms=245, tokens=500)
    slog.pipeline("enrichment", "completed", duration_ms=1200)
"""

import json
import logging
import time
import uuid
from contextvars import ContextVar
from functools import wraps
from typing import Any, Dict

logger = logging.getLogger('jobstream.structured')

# Context variable for request/session correlation
_correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')
_session_id: ContextVar[str] = ContextVar('session_id', default='')
_user_id: ContextVar[str] = ContextVar('user_id', default='')


def set_correlation_context(
	correlation_id: str = '',
	session_id: str = '',
	user_id: str = '',
):
	"""Set correlation context for the current async task."""
	if correlation_id:
		_correlation_id.set(correlation_id)
	if session_id:
		_session_id.set(session_id)
	if user_id:
		_user_id.set(user_id)


def new_correlation_id() -> str:
	"""Generate and set a new correlation ID."""
	cid = uuid.uuid4().hex[:12]
	_correlation_id.set(cid)
	return cid


class StructuredLogger:
	"""
	Structured JSON logger with automatic context injection.

	Every log entry includes:
	  - timestamp, level, category, action
	  - correlation_id, session_id (from context)
	  - Arbitrary key-value pairs

	PII is automatically redacted from values when the PII
	detector is available.
	"""

	def __init__(self, redact_pii: bool = True):
		self._redact_pii = redact_pii
		self._pii_detector = None

	def _get_pii_detector(self):
		if self._pii_detector is None and self._redact_pii:
			try:
				from src.core.pii_detector import pii_detector

				self._pii_detector = pii_detector
			except ImportError:
				self._redact_pii = False
		return self._pii_detector

	def _redact(self, value: Any) -> Any:
		"""Redact PII from string values."""
		if not self._redact_pii or not isinstance(value, str):
			return value
		detector = self._get_pii_detector()
		if detector:
			return detector.redact(value)
		return value

	def _build_entry(
		self,
		level: str,
		category: str,
		action: str,
		**kwargs,
	) -> Dict[str, Any]:
		"""Build a structured log entry."""
		entry = {
			'ts': time.time(),
			'level': level,
			'category': category,
			'action': action,
			'correlation_id': _correlation_id.get(''),
			'session_id': _session_id.get(''),
		}

		# Add user_id if available (truncated for privacy)
		uid = _user_id.get('')
		if uid:
			entry['user_id'] = uid[:8] + '...'

		# Add extra fields, redacting PII from string values
		for k, v in kwargs.items():
			entry[k] = self._redact(v) if isinstance(v, str) else v

		return entry

	def _emit(self, level: str, entry: Dict[str, Any]):
		"""Write the log entry."""
		line = json.dumps(entry, default=str)
		log_fn = getattr(logger, level, logger.info)
		log_fn(line)

	# ── Category-Specific Methods ───────────────────────────────

	def agent(self, agent_name: str, action: str, **kwargs):
		"""Log an agent event."""
		entry = self._build_entry('info', 'agent', action, agent=agent_name, **kwargs)
		self._emit('info', entry)

	def agent_error(self, agent_name: str, action: str, error: str, **kwargs):
		"""Log an agent error."""
		entry = self._build_entry('error', 'agent', action, agent=agent_name, error=error, **kwargs)
		self._emit('error', entry)

	def llm(
		self,
		provider: str,
		model: str,
		latency_ms: float = 0,
		input_tokens: int = 0,
		output_tokens: int = 0,
		**kwargs,
	):
		"""Log an LLM invocation."""
		entry = self._build_entry(
			'info',
			'llm',
			'invoke',
			provider=provider,
			model=model,
			latency_ms=round(latency_ms, 1),
			input_tokens=input_tokens,
			output_tokens=output_tokens,
			**kwargs,
		)
		self._emit('info', entry)

	def llm_error(self, provider: str, model: str, error: str, **kwargs):
		"""Log an LLM failure."""
		entry = self._build_entry('error', 'llm', 'error', provider=provider, model=model, error=error, **kwargs)
		self._emit('error', entry)

	def pipeline(self, step: str, status: str, duration_ms: float = 0, **kwargs):
		"""Log a pipeline step event."""
		entry = self._build_entry('info', 'pipeline', step, status=status, duration_ms=round(duration_ms, 1), **kwargs)
		self._emit('info', entry)

	def security(self, event_type: str, **kwargs):
		"""Log a security event (auth, injection attempt, PII detected, etc.)."""
		entry = self._build_entry('warning', 'security', event_type, **kwargs)
		self._emit('warning', entry)

	def api(self, method: str, path: str, status_code: int, latency_ms: float = 0, **kwargs):
		"""Log an API request."""
		entry = self._build_entry(
			'info',
			'api',
			'request',
			method=method,
			path=path,
			status_code=status_code,
			latency_ms=round(latency_ms, 1),
			**kwargs,
		)
		self._emit('info', entry)

	def websocket(self, action: str, session_id: str = '', **kwargs):
		"""Log a WebSocket event."""
		entry = self._build_entry('info', 'websocket', action, ws_session=session_id, **kwargs)
		self._emit('info', entry)

	def custom(self, category: str, action: str, level: str = 'info', **kwargs):
		"""Log a custom event."""
		entry = self._build_entry(level, category, action, **kwargs)
		self._emit(level, entry)

	# ── Timing Helper ───────────────────────────────────────────

	def timed(self, category: str, action: str):
		"""
		Decorator/context manager for timing code blocks.

		Usage as decorator:
		    @slog.timed("agent", "resume_generation")
		    async def generate_resume(...):
		        ...
		"""
		slog = self

		class Timer:
			def __init__(self):
				self.start = None

			def __enter__(self):
				self.start = time.time()
				return self

			def __exit__(self, *args):
				elapsed = (time.time() - self.start) * 1000
				slog.custom(category, action, duration_ms=round(elapsed, 1))

			def __call__(self, func):
				@wraps(func)
				async def wrapper(*args, **kwargs):
					start = time.time()
					try:
						result = await func(*args, **kwargs)
						elapsed = (time.time() - start) * 1000
						slog.custom(
							category,
							action,
							status='success',
							duration_ms=round(elapsed, 1),
						)
						return result
					except Exception as e:
						elapsed = (time.time() - start) * 1000
						slog.custom(
							category,
							action,
							level='error',
							status='failed',
							error=str(e),
							duration_ms=round(elapsed, 1),
						)
						raise

				return wrapper

		return Timer()


# ── Singleton ───────────────────────────────────────────────────

slog = StructuredLogger()
