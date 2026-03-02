"""
Pipeline Orchestrator with LangGraph State Machine + Event Streaming

Uses LangGraph StateGraph for the pipeline flow while preserving
the original WebSocket event emission pattern.

Architecture:
  - LangGraph handles node orchestration, conditional edges, and state management
  - Events are emitted to WebSocket via event_callback bridge
  - Event Bus publishes pipeline lifecycle events for decoupled consumers
  - Guardrails validate user inputs before pipeline execution
"""

import logging
import inspect
from datetime import datetime
from typing import Awaitable, Callable, Optional

from src.api.websocket import AgentEvent, EventType, manager

logger = logging.getLogger(__name__)


class StreamingPipelineOrchestrator:
	"""
	Orchestrates the job application pipeline using LangGraph StateGraph.
	Events are streamed to WebSocket clients in real-time.
	Event Bus emits lifecycle events for decoupled consumers.
	Supports multi-user via user_id for per-user profile loading.

	The `is_running` flag is stored in Redis (with in-memory fallback)
	so that horizontal scaling and process restarts see a consistent view.
	"""

	# Redis key prefix for orchestrator running flag
	_REDIS_KEY_PREFIX = 'orchestrator:running'

	def __init__(self, session_id: str = 'default', user_id: Optional[str] = None):
		self.session_id = session_id
		self.user_id = user_id
		self._manager = manager
		self._status_callback: Optional[Callable[[dict], Awaitable[None] | None]] = None

		# In-memory fallback (only used when Redis is unavailable)
		self._is_running_local = True

		# Redis handle (optional)
		self._redis = None
		try:
			from src.core.redis_client import get_redis_client
			self._redis = get_redis_client()
		except Exception:
			pass

		# Lazy-load event bus (optional dependency)
		self._event_bus = None
		try:
			from src.core.event_bus import event_bus
			self._event_bus = event_bus
		except ImportError:
			pass

	# ── Running-flag helpers (Redis-first, memory fallback) ────────

	def _redis_key(self) -> str:
		return f'{self._REDIS_KEY_PREFIX}:{self.session_id}'

	async def _set_running(self, value: bool) -> None:
		self._is_running_local = value
		if self._redis:
			try:
				if value:
					await self._redis.setex(self._redis_key(), 3600, '1')
				else:
					await self._redis.delete(self._redis_key())
			except Exception as e:
				logger.debug(f'Redis running-flag write failed (non-fatal): {e}')

	async def _get_running(self) -> bool:
		if self._redis:
			try:
				val = await self._redis.get(self._redis_key())
				if val is not None:
					return val == '1'
			except Exception:
				pass
		return self._is_running_local

	@property
	def is_running(self) -> bool:
		"""Sync accessor for backward compatibility (uses local cache)."""
		return self._is_running_local

	async def emit(self, event_type: EventType, agent: str, message: str, data: dict = None):
		"""Emit an event to connected clients AND event bus."""
		event = AgentEvent(type=event_type, agent=agent, message=message, data=data or {})
		await self._manager.send_event(self.session_id, event)

		# Also publish to event bus for decoupled consumers
		if self._event_bus:
			try:
				await self._event_bus.emit(
					f'pipeline:{event_type.value}',
					{
						'session_id': self.session_id,
						'user_id': self.user_id,
						'agent': agent,
						'message': message,
						'data': data or {},
						'timestamp': datetime.now().isoformat(),
					},
				)
			except Exception as e:
				logger.debug(f'Event bus publish error (non-fatal): {e}')

	def stop(self):
		"""Stop the pipeline (marks local flag; Redis cleanup happens in run() finally)."""
		self._is_running_local = False

	def set_status_callback(self, callback: Callable[[dict], Awaitable[None] | None]) -> None:
		"""Attach callback for status synchronization (e.g. pipeline status endpoint)."""
		self._status_callback = callback

	async def _event_bridge(self, event_dict: dict):
		"""
		Bridge LangGraph events to WebSocket.
		Converts graph event dicts to AgentEvent and sends via WebSocket.
		"""
		try:
			event_type_str = event_dict.get('type', '')
			# Map string event types to EventType enum
			try:
				event_type = EventType(event_type_str)
			except ValueError:
				event_type = EventType.PIPELINE_ERROR

			await self.emit(
				event_type, event_dict.get('agent', 'system'), event_dict.get('message', ''), event_dict.get('data', {})
			)
			if self._status_callback:
				maybe_result = self._status_callback(event_dict)
				if inspect.isawaitable(maybe_result):
					await maybe_result
		except Exception as e:
			logger.warning(f'Event bridge error: {e}')

	async def run(
		self,
		query: str,
		location: str,
		min_match_score: int = 70,
		max_jobs: int = 10,
		auto_apply: bool = False,
		use_company_research: Optional[bool] = None,
		use_resume_tailoring: Optional[bool] = None,
		use_cover_letter: Optional[bool] = None,
	):
		"""
		Run the full pipeline using LangGraph StateGraph.

		The graph handles:
		  - Profile loading (DB → YAML fallback)
		  - Job scouting via search engines
		  - Per-job analysis with match scoring
		  - Conditional enrichment (company research, resume tailoring, cover letter)
		  - Optional auto-apply with browser automation
		  - Result collection and loop control

		Step overrides:
		  - None  → let the intelligent planner decide (default)
		  - True  → force-enable the step
		  - False → force-disable the step

		Events are streamed via WebSocket in real-time.
		"""
		await self._set_running(True)

		# Validate input with guardrails (BLOCKING on failure)
		try:
			from src.core.guardrails import GuardrailAction, create_input_pipeline

			pipeline = create_input_pipeline()
			result = await pipeline.check(query)
			if result.action == GuardrailAction.BLOCK:
				await self.emit(
					EventType.PIPELINE_ERROR,
					'guardrails',
					f'Input blocked by safety guardrails: {result.blocked_reason}',
					{'blocked': True, 'reason': result.blocked_reason},
				)
				return {'success': False, 'error': f'Input blocked: {result.blocked_reason}'}
			# Use sanitized query if modified
			if result.processed_text and result.processed_text != query:
				query = result.processed_text
		except ImportError:
			logger.error('Guardrails module not importable — refusing to run with un-sanitized input')
			await self.emit(
				EventType.PIPELINE_ERROR,
				'guardrails',
				'Guardrails unavailable — pipeline cannot proceed safely.',
				{'blocked': True, 'reason': 'guardrails_import_error'},
			)
			return {'success': False, 'error': 'Guardrails module not available'}
		except Exception as e:
			logger.warning(f'Guardrail check failed (non-blocking): {e}')

		# ── Intelligent step planning ─────────────────────────────────
		# If the caller left step flags as None, ask the planner LLM
		# to decide which steps are actually needed for this query.
		needs_planning = any(v is None for v in [use_resume_tailoring, use_cover_letter, use_company_research])
		if needs_planning:
			try:
				from src.services.step_planner import StepPlanner

				planner = StepPlanner()
				plan = await planner.plan(query=query, location=location, user_id=self.user_id)

				if use_resume_tailoring is None:
					use_resume_tailoring = plan.use_resume_tailoring
				if use_cover_letter is None:
					use_cover_letter = plan.use_cover_letter
				if use_company_research is None:
					use_company_research = plan.use_company_research

				await self.emit(
					EventType.PIPELINE_START,
					'planner',
					f'Step plan: {plan.reasoning}',
					{
						'resume_tailoring': use_resume_tailoring,
						'cover_letter': use_cover_letter,
						'company_research': use_company_research,
						'reasoning': plan.reasoning,
					},
				)
			except Exception as e:
				logger.warning(f'Step planner failed, defaulting all steps ON: {e}')
				use_resume_tailoring = use_resume_tailoring if use_resume_tailoring is not None else True
				use_cover_letter = use_cover_letter if use_cover_letter is not None else True
				use_company_research = use_company_research if use_company_research is not None else False

		# Final fallback: if still None after planning, default ON
		use_resume_tailoring = use_resume_tailoring if use_resume_tailoring is not None else True
		use_cover_letter = use_cover_letter if use_cover_letter is not None else True
		use_company_research = use_company_research if use_company_research is not None else False

		await self.emit(
			EventType.PIPELINE_START,
			'system',
			f"Starting LangGraph pipeline for '{query}' in '{location}'",
			{
				'query': query,
				'location': location,
				'max_jobs': max_jobs,
				'auto_apply': auto_apply,
				'user_id': self.user_id,
				'engine': 'langgraph',
				'options': {'research': use_company_research, 'tailor': use_resume_tailoring, 'cover_letter': use_cover_letter},
			},
		)

		try:
			from src.graphs.pipeline_graph import run_pipeline_graph

			result = await run_pipeline_graph(
				query=query,
				location=location,
				session_id=self.session_id,
				user_id=self.user_id,
				min_match_score=min_match_score,
				max_jobs=max_jobs,
				auto_apply=auto_apply,
				use_company_research=use_company_research,
				use_resume_tailoring=use_resume_tailoring,
				use_cover_letter=use_cover_letter,
				event_callback=self._event_bridge,
				should_stop=lambda: not self._is_running_local,
				resume_from_checkpoint=False,
			)

			await self.emit(
				EventType.PIPELINE_COMPLETE,
				'system',
				f'LangGraph pipeline finished. Applied to {result.get("applied", 0)} jobs.',
				{
					'analyzed': result.get('analyzed', 0),
					'applied': result.get('applied', 0),
					'engine': 'langgraph',
				},
			)

			return result

		except Exception as e:
			logger.error(f'LangGraph pipeline failed: {e}', exc_info=True)
			await self.emit(EventType.PIPELINE_ERROR, 'system', f'Pipeline failed: {str(e)}', {'error': str(e)})
			return {'success': False, 'error': str(e)}
		finally:
			await self._set_running(False)
