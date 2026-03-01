"""
WebSocket Manager for Real-Time Agent Updates
Handles connections, broadcasts, and HITL prompts
Production-ready with bounded history, user isolation, and proper logging
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class EventType(str, Enum):
	# Connection events
	CONNECTED = 'connected'
	DISCONNECTED = 'disconnected'

	# Pipeline events
	PIPELINE_START = 'pipeline:start'
	PIPELINE_COMPLETE = 'pipeline:complete'
	PIPELINE_ERROR = 'pipeline:error'

	# Scout events
	SCOUT_START = 'scout:start'
	SCOUT_SEARCHING = 'scout:searching'
	SCOUT_FOUND = 'scout:found'
	SCOUT_COMPLETE = 'scout:complete'

	# Analyst events
	ANALYST_START = 'analyst:start'
	ANALYST_FETCHING = 'analyst:fetching'
	ANALYST_ANALYZING = 'analyst:analyzing'
	ANALYST_RESULT = 'analyst:result'

	# Company Researcher events
	COMPANY_START = 'company:start'
	COMPANY_RESEARCHING = 'company:researching'
	COMPANY_RESULT = 'company:result'

	# Resume Tailor events
	RESUME_START = 'resume:start'
	RESUME_TAILORING = 'resume:tailoring'
	RESUME_GENERATED = 'resume:generated'
	RESUME_COMPLETE = 'resume:complete'

	# Cover Letter events
	COVER_LETTER_START = 'cover_letter:start'
	COVER_LETTER_GENERATING = 'cover_letter:generating'
	COVER_LETTER_COMPLETE = 'cover_letter:complete'

	# Applier events
	APPLIER_START = 'applier:start'
	APPLIER_NAVIGATE = 'applier:navigate'
	APPLIER_CLICK = 'applier:click'
	APPLIER_TYPE = 'applier:type'
	APPLIER_UPLOAD = 'applier:upload'
	APPLIER_SCREENSHOT = 'applier:screenshot'
	APPLIER_COMPLETE = 'applier:complete'

	# Draft Mode events (Trust-building: show before submit)
	DRAFT_REVIEW = 'draft:review'  # Form filled, awaiting user confirmation
	DRAFT_CONFIRM = 'draft:confirm'  # User confirmed, proceed to submit
	DRAFT_EDIT = 'draft:edit'  # User wants to edit, return control

	# HITL events
	HITL_REQUEST = 'hitl:request'
	HITL_RESPONSE = 'hitl:response'

	# Browser events
	BROWSER_SCREENSHOT = 'browser:screenshot'

	# Chat events (for Live Applier)
	CHAT_MESSAGE = 'chat:message'

	# Async Task Queue events (Celery integration)
	TASK_QUEUED = 'task:queued'  # Task added to queue
	TASK_STARTED = 'task:started'  # Worker started processing
	TASK_PROGRESS = 'task:progress'  # Progress update from worker
	TASK_COMPLETE = 'task:complete'  # Task finished successfully
	TASK_FAILED = 'task:failed'  # Task failed with error

	# NetworkAI events
	NETWORK_SEARCH_START = 'network:search_start'
	NETWORK_MATCH_FOUND = 'network:match_found'
	NETWORK_SEARCH_COMPLETE = 'network:search_complete'


@dataclass
class AgentEvent:
	"""Represents an event from an agent."""

	type: EventType
	agent: str
	message: str
	data: Optional[Dict] = None
	timestamp: str = None

	def __post_init__(self):
		if self.timestamp is None:
			# Use ISO timestamp for consistent parsing on clients
			self.timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

	def to_dict(self) -> Dict:
		return {
			'type': self.type.value if isinstance(self.type, EventType) else self.type,
			'agent': self.agent,
			'message': self.message,
			'data': self.data or {},
			'timestamp': self.timestamp,
		}


class ConnectionManager:
	"""Manages WebSocket connections and broadcasts with multi-user support."""

	MAX_EVENT_HISTORY = 200  # Bounded history to prevent memory leaks

	def __init__(self):
		self.active_connections: Dict[str, WebSocket] = {}
		self.session_user_map: Dict[str, str] = {}  # session_id -> user_id
		self.event_history: Dict[str, deque] = {}  # session_id -> bounded deque
		self.hitl_callbacks: Dict[str, asyncio.Future] = {}

	async def connect(self, websocket: WebSocket, session_id: str, token: str = None, user_id: str = None):
		"""Register a new connection (websocket must be already accepted)."""
		# Close previous connection for same session gracefully
		if session_id in self.active_connections:
			old_ws = self.active_connections[session_id]
			try:
				await old_ws.close(code=4000, reason='Replaced by new connection')
			except Exception:
				pass

		self.active_connections[session_id] = websocket
		if user_id:
			self.session_user_map[session_id] = user_id

		# Initialize bounded event history per session
		if session_id not in self.event_history:
			self.event_history[session_id] = deque(maxlen=self.MAX_EVENT_HISTORY)

		# Send connection confirmation
		await self.send_event(
			session_id, AgentEvent(type=EventType.CONNECTED, agent='system', message='Connected to JobAI agent server')
		)

		# Replay recent events for this session only
		for event in list(self.event_history[session_id])[-50:]:
			await self.send_json(session_id, event.to_dict())

	def disconnect(self, session_id: str):
		"""Remove a connection and clean up."""
		self.active_connections.pop(session_id, None)
		self.session_user_map.pop(session_id, None)
		# Keep event_history for potential reconnection; it's bounded anyway

	async def send_json(self, session_id: str, data: Dict):
		"""Send JSON data to a specific session."""
		if session_id in self.active_connections:
			try:
				await self.active_connections[session_id].send_json(data)
			except Exception:
				self.disconnect(session_id)

	async def send_event(self, session_id: str, event: AgentEvent):
		"""Send an event to a specific session."""
		if session_id not in self.event_history:
			self.event_history[session_id] = deque(maxlen=self.MAX_EVENT_HISTORY)
		self.event_history[session_id].append(event)
		await self.send_json(session_id, event.to_dict())

	async def broadcast(self, event: AgentEvent):
		"""Broadcast an event to all connections."""
		data = event.to_dict()

		logger.info(f'[WS Broadcast] {event.type} -> {len(self.active_connections)} clients: {event.message[:50]}')

		disconnected = []
		for session_id, ws in self.active_connections.items():
			try:
				# Store in per-session history
				if session_id not in self.event_history:
					self.event_history[session_id] = deque(maxlen=self.MAX_EVENT_HISTORY)
				self.event_history[session_id].append(event)
				await ws.send_json(data)
			except Exception as e:
				logger.warning(f'[WS Broadcast] Failed to send to {session_id}: {e}')
				disconnected.append(session_id)

		# Clean up disconnected
		for sid in disconnected:
			self.disconnect(sid)

	async def request_hitl(self, session_id: str, question: str, context: str = '') -> str:
		"""
		Request human input via WebSocket.
		Blocks until response received.
		"""
		hitl_id = f'hitl_{datetime.now().timestamp()}'

		# Create future for response
		loop = asyncio.get_running_loop()
		future = loop.create_future()
		self.hitl_callbacks[hitl_id] = future

		# Send HITL request
		await self.send_event(
			session_id,
			AgentEvent(
				type=EventType.HITL_REQUEST, agent='applier', message=question, data={'hitl_id': hitl_id, 'context': context}
			),
		)

		# Wait for response (with timeout)
		try:
			response = await asyncio.wait_for(future, timeout=300)  # 5 min timeout
			return response
		except asyncio.TimeoutError:
			del self.hitl_callbacks[hitl_id]
			raise TimeoutError('HITL request timed out')

	def resolve_hitl(self, hitl_id: str, response: str) -> bool:
		"""Resolve a pending HITL request. Returns True if resolved, False otherwise."""
		if hitl_id in self.hitl_callbacks:
			future = self.hitl_callbacks[hitl_id]
			if not future.done():
				future.set_result(response)
			del self.hitl_callbacks[hitl_id]
			return True
		return False


# Global connection manager
manager = ConnectionManager()


class EventEmitter:
	"""
	Mixin class for agents to emit events.
	Attach to any agent class to enable real-time updates.
	"""

	def __init__(self, session_id: str = 'default'):
		self.session_id = session_id
		self._manager = manager

	async def emit(self, event_type: EventType, message: str, data: Optional[Dict] = None):
		"""Emit an event to the connected frontend."""
		event = AgentEvent(
			type=event_type, agent=self.__class__.__name__.replace('Agent', '').lower(), message=message, data=data
		)
		await self._manager.send_event(self.session_id, event)

	async def emit_screenshot(self, screenshot_base64: str):
		"""Emit a browser screenshot."""
		await self.emit(
			EventType.BROWSER_SCREENSHOT, 'Browser screenshot', {'screenshot': screenshot_base64, 'image': screenshot_base64}
		)

	async def ask_human_ws(self, question: str, context: str = '') -> str:
		"""Request human input via WebSocket instead of stdin."""
		return await self._manager.request_hitl(self.session_id, question, context)
