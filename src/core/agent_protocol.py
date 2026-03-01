"""
Agent Communication Protocol — Inter-Agent Messaging

Enables agents to share discoveries, request information, and
coordinate actions without direct coupling. Built on top of the
existing EventBus for zero new infrastructure.

Message types:
  - INFORM: Share a fact (e.g., Company Agent found a red flag)
  - REQUEST: Ask another agent for data
  - DELEGATE: Hand off a sub-task
  - FEEDBACK: Share feedback about output quality

Usage:
    from src.core.agent_protocol import agent_protocol, MessageIntent

    # Broadcasting a discovery
    await agent_protocol.broadcast(
        from_agent="company_agent",
        intent=MessageIntent.INFORM,
        payload={"red_flag": "High turnover rate", "company": "Acme Corp"}
    )

    # Requesting data from a specific agent
    response = await agent_protocol.request(
        from_agent="cover_letter_agent",
        to_agent="company_agent",
        task="get_company_culture",
        payload={"company": "Google"}
    )
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MessageIntent(str, Enum):
	INFORM = 'inform'
	REQUEST = 'request'
	DELEGATE = 'delegate'
	FEEDBACK = 'feedback'


class Priority(str, Enum):
	LOW = 'low'
	NORMAL = 'normal'
	HIGH = 'high'
	CRITICAL = 'critical'


@dataclass
class AgentMessage:
	"""A message between agents."""

	from_agent: str
	to_agent: str  # "*" for broadcast
	intent: MessageIntent
	payload: Dict[str, Any]
	priority: Priority = Priority.NORMAL
	correlation_id: str = ''
	timestamp: float = field(default_factory=time.time)
	reply_to: str = ''  # for request-response pattern


@dataclass
class MessageLog:
	"""Logged message for audit trail."""

	message: AgentMessage
	delivered: bool = True
	response: Any = None
	error: str = ''


class AgentProtocol:
	"""
	Inter-agent communication protocol.

	Uses the EventBus under the hood, so messages flow through
	the same infrastructure as pipeline events. Agents register
	handlers for messages directed at them, and can broadcast
	or request data from other agents.
	"""

	def __init__(self):
		self._handlers: Dict[str, List[Callable]] = {}
		self._request_handlers: Dict[str, Callable] = {}
		self._message_log: List[MessageLog] = []
		self._event_bus = None
		self._max_log_size = 500

	def _get_event_bus(self):
		"""Lazy-load event bus."""
		if self._event_bus is None:
			try:
				from src.core.event_bus import event_bus

				self._event_bus = event_bus
			except ImportError:
				logger.warning('[AgentProtocol] EventBus not available')
		return self._event_bus

	# ── Handler Registration ────────────────────────────────────

	def on_message(self, agent_name: str):
		"""
		Decorator to register a handler for messages to a specific agent.

		Usage:
		    @agent_protocol.on_message("company_agent")
		    async def handle(msg: AgentMessage):
		        if msg.intent == MessageIntent.REQUEST:
		            return {"culture": "innovative"}
		"""

		def decorator(fn):
			if agent_name not in self._handlers:
				self._handlers[agent_name] = []
			self._handlers[agent_name].append(fn)
			logger.debug(f'[AgentProtocol] Registered handler for {agent_name}')
			return fn

		return decorator

	def register_handler(self, agent_name: str, handler: Callable):
		"""Register a message handler programmatically."""
		if agent_name not in self._handlers:
			self._handlers[agent_name] = []
		self._handlers[agent_name].append(handler)

	def register_request_handler(self, agent_name: str, task: str, handler: Callable):
		"""
		Register a handler for a specific request task.

		The handler receives the payload dict and should return a response.
		"""
		key = f'{agent_name}:{task}'
		self._request_handlers[key] = handler
		logger.debug(f'[AgentProtocol] Registered request handler: {key}')

	# ── Messaging ───────────────────────────────────────────────

	async def send(self, msg: AgentMessage) -> bool:
		"""
		Send a message to a specific agent or broadcast to all.

		Returns True if at least one handler received it.
		"""
		self._log_message(msg)

		delivered = False

		if msg.to_agent == '*':
			# Broadcast to all registered handlers
			for agent, handlers in self._handlers.items():
				if agent != msg.from_agent:
					for handler in handlers:
						try:
							await handler(msg)
							delivered = True
						except Exception as e:
							logger.error(f'[AgentProtocol] Handler error in {agent}: {e}')
		else:
			# Direct message
			handlers = self._handlers.get(msg.to_agent, [])
			for handler in handlers:
				try:
					await handler(msg)
					delivered = True
				except Exception as e:
					logger.error(f'[AgentProtocol] Handler error in {msg.to_agent}: {e}')

		# Also publish to event bus for logging/monitoring
		bus = self._get_event_bus()
		if bus:
			try:
				await bus.emit(
					f'agent_protocol:{msg.intent.value}',
					data={
						'from': msg.from_agent,
						'to': msg.to_agent,
						'intent': msg.intent.value,
						'payload_keys': list(msg.payload.keys()),
					},
					source=msg.from_agent,
				)
			except Exception:
				pass

		if not delivered:
			logger.debug(f'[AgentProtocol] No handlers for {msg.to_agent}')

		return delivered

	async def broadcast(
		self,
		from_agent: str,
		intent: MessageIntent,
		payload: Dict[str, Any],
		priority: Priority = Priority.NORMAL,
	) -> bool:
		"""Broadcast a message to all agents."""
		msg = AgentMessage(
			from_agent=from_agent,
			to_agent='*',
			intent=intent,
			payload=payload,
			priority=priority,
		)
		return await self.send(msg)

	async def inform(
		self,
		from_agent: str,
		to_agent: str,
		payload: Dict[str, Any],
	) -> bool:
		"""Send an informational message to a specific agent."""
		msg = AgentMessage(
			from_agent=from_agent,
			to_agent=to_agent,
			intent=MessageIntent.INFORM,
			payload=payload,
		)
		return await self.send(msg)

	async def request(
		self,
		from_agent: str,
		to_agent: str,
		task: str,
		payload: Optional[Dict[str, Any]] = None,
		timeout: float = 10.0,
	) -> Any:
		"""
		Request data from another agent.

		Looks for a registered request handler for the (agent, task) pair.
		Returns the handler's response, or None if no handler found.
		"""
		key = f'{to_agent}:{task}'
		handler = self._request_handlers.get(key)

		if not handler:
			logger.debug(f'[AgentProtocol] No request handler for {key}')
			return None

		msg = AgentMessage(
			from_agent=from_agent,
			to_agent=to_agent,
			intent=MessageIntent.REQUEST,
			payload=payload or {},
		)
		self._log_message(msg)

		try:
			result = await asyncio.wait_for(
				handler(payload or {}),
				timeout=timeout,
			)
			return result
		except asyncio.TimeoutError:
			logger.warning(f'[AgentProtocol] Request timeout: {key}')
			return None
		except Exception as e:
			logger.error(f'[AgentProtocol] Request failed: {key} — {e}')
			return None

	# ── Logging & Diagnostics ───────────────────────────────────

	def _log_message(self, msg: AgentMessage):
		"""Add message to audit log."""
		self._message_log.append(MessageLog(message=msg))
		# Trim log if too large
		if len(self._message_log) > self._max_log_size:
			self._message_log = self._message_log[-self._max_log_size :]

	def get_message_history(self, agent_name: Optional[str] = None, limit: int = 20) -> List[Dict]:
		"""Get recent message history, optionally filtered by agent."""
		entries = self._message_log
		if agent_name:
			entries = [e for e in entries if e.message.from_agent == agent_name or e.message.to_agent == agent_name]

		return [
			{
				'from': e.message.from_agent,
				'to': e.message.to_agent,
				'intent': e.message.intent.value,
				'payload_keys': list(e.message.payload.keys()),
				'timestamp': e.message.timestamp,
				'delivered': e.delivered,
			}
			for e in entries[-limit:]
		]

	def stats(self) -> Dict[str, Any]:
		"""Return protocol stats for health checks."""
		return {
			'registered_agents': list(self._handlers.keys()),
			'registered_request_handlers': list(self._request_handlers.keys()),
			'total_messages_logged': len(self._message_log),
			'event_bus_connected': self._event_bus is not None,
		}


# ── Singleton ───────────────────────────────────────────────────

agent_protocol = AgentProtocol()
