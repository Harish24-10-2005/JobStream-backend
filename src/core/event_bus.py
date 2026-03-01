"""
Event Bus — Async Pub/Sub for Decoupled Service Communication

In-process event bus with typed events, async handlers, and middleware.
Enables loose coupling between agents, services, and API layer.

Architecture:
  Producer → EventBus.emit() → [middleware] → handlers

Patterns:
  - Publish/Subscribe (fan-out to all handlers)
  - Event sourcing compatible (events are typed + timestamped)
  - Middleware pipeline (logging, PII redaction, metrics)

Usage:
    from src.core.event_bus import event_bus, Event

    # Subscribe
    @event_bus.on("job:analyzed")
    async def handle_analysis(event: Event):
        print(event.data)

    # Publish
    await event_bus.emit("job:analyzed", {"match_score": 85})
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Event:
	"""Typed event with metadata."""

	topic: str
	data: Dict[str, Any] = field(default_factory=dict)
	source: str = 'system'
	timestamp: float = field(default_factory=time.time)
	event_id: str = ''
	metadata: Dict[str, Any] = field(default_factory=dict)

	def __post_init__(self):
		if not self.event_id:
			self.event_id = f'{self.topic}_{int(self.timestamp * 1000)}'

	@property
	def age_ms(self) -> float:
		return (time.time() - self.timestamp) * 1000


# Type for event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]
EventMiddleware = Callable[[Event, Callable], Coroutine[Any, Any, Optional[Event]]]


class EventBus:
	"""
	Async event bus with pub/sub, wildcard topics, and middleware.

	Features:
	  - Exact topic matching ("job:analyzed")
	  - Wildcard matching ("job:*" matches "job:analyzed", "job:scouted")
	  - Middleware pipeline for cross-cutting concerns
	  - Error isolation (one handler error doesn't affect others)
	  - Event history for debugging
	"""

	def __init__(self, max_history: int = 100):
		self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
		self._middleware: List[EventMiddleware] = []
		self._history: List[Event] = []
		self._max_history = max_history
		self._stats: Dict[str, int] = defaultdict(int)

	# ─── Subscribe ───────────────────────────────────────────

	def on(self, topic: str) -> Callable:
		"""
		Decorator to subscribe a handler to a topic.

		@event_bus.on("job:analyzed")
		async def handler(event: Event):
		    ...
		"""

		def decorator(func: EventHandler):
			self._handlers[topic].append(func)
			logger.debug(f"[EventBus] Subscribed {func.__name__} to '{topic}'")
			return func

		return decorator

	def subscribe(self, topic: str, handler: EventHandler):
		"""Programmatic subscription."""
		self._handlers[topic].append(handler)

	def unsubscribe(self, topic: str, handler: EventHandler):
		"""Remove a handler from a topic."""
		if topic in self._handlers:
			self._handlers[topic] = [h for h in self._handlers[topic] if h != handler]

	# ─── Publish ─────────────────────────────────────────────

	async def emit(
		self,
		topic: str,
		data: Dict[str, Any] = None,
		source: str = 'system',
		metadata: Dict[str, Any] = None,
	) -> Event:
		"""
		Emit an event to all matching handlers.

		Returns the (potentially middleware-modified) event.
		"""
		event = Event(
			topic=topic,
			data=data or {},
			source=source,
			metadata=metadata or {},
		)

		# Run middleware
		for mw in self._middleware:
			try:
				result = await mw(event, lambda e: e)
				if result is None:
					# Middleware filtered the event
					logger.debug(f"[EventBus] Event '{topic}' filtered by middleware")
					return event
				event = result
			except Exception as e:
				logger.error(f'[EventBus] Middleware error: {e}')

		# Find matching handlers
		handlers = self._get_matching_handlers(topic)

		# Run handlers concurrently (isolated from each other)
		if handlers:
			results = await asyncio.gather(
				*[self._safe_call(h, event) for h in handlers],
				return_exceptions=True,
			)
			errors = [r for r in results if isinstance(r, Exception)]
			if errors:
				logger.warning(f"[EventBus] {len(errors)}/{len(handlers)} handlers failed for '{topic}'")

		# Track stats & history
		self._stats[topic] += 1
		self._history.append(event)
		if len(self._history) > self._max_history:
			self._history = self._history[-self._max_history :]

		return event

	# ─── Middleware ───────────────────────────────────────────

	def use(self, middleware: EventMiddleware):
		"""Add middleware to the pipeline."""
		self._middleware.append(middleware)

	# ─── Query ───────────────────────────────────────────────

	@property
	def topics(self) -> List[str]:
		"""List all subscribed topics."""
		return list(self._handlers.keys())

	@property
	def stats(self) -> Dict[str, int]:
		"""Event emission counts by topic."""
		return dict(self._stats)

	def history(self, topic: str = None, limit: int = 10) -> List[Event]:
		"""Get recent events, optionally filtered by topic."""
		events = self._history
		if topic:
			events = [e for e in events if e.topic == topic]
		return events[-limit:]

	# ─── Internals ───────────────────────────────────────────

	def _get_matching_handlers(self, topic: str) -> List[EventHandler]:
		"""Get all handlers matching a topic (exact + wildcard)."""
		handlers = list(self._handlers.get(topic, []))

		# Wildcard matching
		for pattern, pattern_handlers in self._handlers.items():
			if '*' in pattern:
				prefix = pattern.replace('*', '')
				if topic.startswith(prefix):
					handlers.extend(pattern_handlers)

		return handlers

	@staticmethod
	async def _safe_call(handler: EventHandler, event: Event):
		"""Call a handler with error isolation."""
		try:
			await handler(event)
		except Exception as e:
			logger.error(
				f'[EventBus] Handler {handler.__name__} error: {e}',
				exc_info=True,
			)
			raise

	def reset(self):
		"""Clear all handlers, middleware, and history (for testing)."""
		self._handlers.clear()
		self._middleware.clear()
		self._history.clear()
		self._stats.clear()


# ─── Singleton Instance ──────────────────────────────────────

event_bus = EventBus()


# ─── Built-in Middleware ─────────────────────────────────────


async def logging_middleware(event: Event, next_fn: Callable) -> Event:
	"""Log all events passing through the bus."""
	logger.info(f'[EventBus] {event.topic} from={event.source} age={event.age_ms:.1f}ms')
	return event


async def metrics_middleware(event: Event, next_fn: Callable) -> Event:
	"""Track event timing metrics."""
	event.metadata['bus_received_at'] = time.time()
	return event
