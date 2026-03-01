"""
LLM Token & Cost Tracker
Tracks token usage, latency, and estimated cost per LLM invocation.
Designed for observability dashboards and budget alerting.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class Provider(str, Enum):
	GROQ = 'groq'
	OPENROUTER = 'openrouter'
	GEMINI = 'gemini'


# Approximate pricing per 1M tokens (input / output)
# Updated periodically; override via COST_TABLE env var if needed
COST_PER_MILLION: Dict[str, Dict[str, float]] = {
	'groq': {'input': 0.05, 'output': 0.08},
	'openrouter': {'input': 0.0, 'output': 0.0},  # free tier
	'gemini': {'input': 0.075, 'output': 0.30},
}


@dataclass
class TokenUsage:
	"""Single invocation record."""

	provider: str
	model: str
	input_tokens: int = 0
	output_tokens: int = 0
	total_tokens: int = 0
	latency_ms: float = 0.0
	cost_usd: float = 0.0
	agent: str = ''
	timestamp: float = field(default_factory=time.time)
	success: bool = True
	error: Optional[str] = None


class LLMUsageTracker:
	"""
	Thread-safe singleton that accumulates token usage across agents.

	Usage:
	    tracker = get_usage_tracker()
	    with tracker.track("resume_agent", "groq", "llama-3.1-8b") as t:
	        result = llm.invoke(messages)
	        t.record(result)  # extracts token counts from LangChain response
	"""

	def __init__(self):
		self._lock = threading.Lock()
		self._records: List[TokenUsage] = []
		self._totals: Dict[str, int] = {
			'input_tokens': 0,
			'output_tokens': 0,
			'total_tokens': 0,
			'invocations': 0,
			'errors': 0,
		}
		self._cost_usd: float = 0.0

	def _estimate_cost(self, provider: str, input_tokens: int, output_tokens: int) -> float:
		rates = COST_PER_MILLION.get(provider, {'input': 0, 'output': 0})
		return (input_tokens * rates['input'] + output_tokens * rates['output']) / 1_000_000

	def record(self, usage: TokenUsage):
		"""Record a single invocation and persist via CostTracker."""
		usage.cost_usd = self._estimate_cost(usage.provider, usage.input_tokens, usage.output_tokens)

		with self._lock:
			self._records.append(usage)
			self._totals['input_tokens'] += usage.input_tokens
			self._totals['output_tokens'] += usage.output_tokens
			self._totals['total_tokens'] += usage.total_tokens
			self._totals['invocations'] += 1
			if not usage.success:
				self._totals['errors'] += 1
			self._cost_usd += usage.cost_usd

		logger.info(
			'llm_invocation',
			extra={
				'provider': usage.provider,
				'model': usage.model,
				'agent': usage.agent,
				'input_tokens': usage.input_tokens,
				'output_tokens': usage.output_tokens,
				'latency_ms': round(usage.latency_ms, 1),
				'cost_usd': round(usage.cost_usd, 6),
				'success': usage.success,
			},
		)

		# ─── Durable persistence via CostTracker ───
		try:
			from src.core.cost_tracker import cost_tracker

			cost_tracker.record(
				agent_name=usage.agent or 'unknown',
				provider=usage.provider,
				model=usage.model,
				input_tokens=usage.input_tokens,
				output_tokens=usage.output_tokens,
			)
		except Exception as e:
			logger.debug(f'CostTracker persistence skipped: {e}')

	def track(self, agent: str, provider: str, model: str) -> 'InvocationContext':
		"""Context manager for tracking a single LLM call."""
		return InvocationContext(self, agent, provider, model)

	def get_summary(self) -> Dict:
		"""Return aggregated usage summary."""
		with self._lock:
			return {
				**self._totals,
				'total_cost_usd': round(self._cost_usd, 4),
				'recent_records': len(self._records),
			}

	def get_per_agent_summary(self) -> Dict[str, Dict]:
		"""Return usage broken down by agent."""
		by_agent: Dict[str, Dict] = {}
		with self._lock:
			for r in self._records:
				key = r.agent or 'unknown'
				if key not in by_agent:
					by_agent[key] = {'invocations': 0, 'total_tokens': 0, 'cost_usd': 0.0, 'errors': 0}
				by_agent[key]['invocations'] += 1
				by_agent[key]['total_tokens'] += r.total_tokens
				by_agent[key]['cost_usd'] = round(by_agent[key]['cost_usd'] + r.cost_usd, 6)
				if not r.success:
					by_agent[key]['errors'] += 1
		return by_agent

	def reset(self):
		"""Reset all counters (for testing)."""
		with self._lock:
			self._records.clear()
			self._totals = {k: 0 for k in self._totals}
			self._cost_usd = 0.0


class InvocationContext:
	"""Context manager that auto-tracks latency and token usage."""

	def __init__(self, tracker: LLMUsageTracker, agent: str, provider: str, model: str):
		self._tracker = tracker
		self._usage = TokenUsage(provider=provider, model=model, agent=agent)
		self._start: float = 0

	def __enter__(self) -> 'InvocationContext':
		self._start = time.perf_counter()
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self._usage.latency_ms = (time.perf_counter() - self._start) * 1000
		if exc_type is not None:
			self._usage.success = False
			self._usage.error = str(exc_val)
		self._tracker.record(self._usage)
		return False  # Don't suppress exceptions

	def record(self, result):
		"""Extract token counts from a LangChain AIMessage or dict."""
		if hasattr(result, 'usage_metadata') and result.usage_metadata:
			meta = result.usage_metadata
			self._usage.input_tokens = (
				getattr(meta, 'input_tokens', 0) or meta.get('input_tokens', 0)
				if isinstance(meta, dict)
				else getattr(meta, 'input_tokens', 0)
			)
			self._usage.output_tokens = (
				getattr(meta, 'output_tokens', 0) or meta.get('output_tokens', 0)
				if isinstance(meta, dict)
				else getattr(meta, 'output_tokens', 0)
			)
			self._usage.total_tokens = self._usage.input_tokens + self._usage.output_tokens
		elif hasattr(result, 'response_metadata'):
			meta = result.response_metadata or {}
			usage = meta.get('token_usage') or meta.get('usage') or {}
			self._usage.input_tokens = usage.get('prompt_tokens', 0) or usage.get('input_tokens', 0)
			self._usage.output_tokens = usage.get('completion_tokens', 0) or usage.get('output_tokens', 0)
			self._usage.total_tokens = usage.get('total_tokens', 0) or (self._usage.input_tokens + self._usage.output_tokens)


# ── Singleton ──
_tracker_instance: Optional[LLMUsageTracker] = None


def get_usage_tracker() -> LLMUsageTracker:
	global _tracker_instance
	if _tracker_instance is None:
		_tracker_instance = LLMUsageTracker()
	return _tracker_instance
