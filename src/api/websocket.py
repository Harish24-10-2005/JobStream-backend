"""
WebSocket Manager for Real-Time Agent Updates
Handles connections, broadcasts, and HITL prompts
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from fastapi import WebSocket, WebSocketDisconnect
from dataclasses import dataclass, asdict
from enum import Enum


class EventType(str, Enum):
    # Connection events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    
    # Pipeline events
    PIPELINE_START = "pipeline:start"
    PIPELINE_COMPLETE = "pipeline:complete"
    PIPELINE_ERROR = "pipeline:error"
    
    # Scout events
    SCOUT_START = "scout:start"
    SCOUT_SEARCHING = "scout:searching"
    SCOUT_FOUND = "scout:found"
    SCOUT_COMPLETE = "scout:complete"
    
    # Analyst events
    ANALYST_START = "analyst:start"
    ANALYST_FETCHING = "analyst:fetching"
    ANALYST_ANALYZING = "analyst:analyzing"
    ANALYST_RESULT = "analyst:result"
    
    # Company Researcher events
    COMPANY_START = "company:start"
    COMPANY_RESEARCHING = "company:researching"
    COMPANY_RESULT = "company:result"
    
    # Resume Tailor events
    RESUME_START = "resume:start"
    RESUME_TAILORING = "resume:tailoring"
    RESUME_GENERATED = "resume:generated"
    RESUME_COMPLETE = "resume:complete"
    
    # Cover Letter events
    COVER_LETTER_START = "cover_letter:start"
    COVER_LETTER_GENERATING = "cover_letter:generating"
    COVER_LETTER_COMPLETE = "cover_letter:complete"
    
    # Applier events
    APPLIER_START = "applier:start"
    APPLIER_NAVIGATE = "applier:navigate"
    APPLIER_CLICK = "applier:click"
    APPLIER_TYPE = "applier:type"
    APPLIER_UPLOAD = "applier:upload"
    APPLIER_SCREENSHOT = "applier:screenshot"
    APPLIER_COMPLETE = "applier:complete"
    
    # Draft Mode events (Trust-building: show before submit)
    DRAFT_REVIEW = "draft:review"        # Form filled, awaiting user confirmation
    DRAFT_CONFIRM = "draft:confirm"      # User confirmed, proceed to submit
    DRAFT_EDIT = "draft:edit"            # User wants to edit, return control
    
    # HITL events
    HITL_REQUEST = "hitl:request"
    HITL_RESPONSE = "hitl:response"
    
    # Browser events
    BROWSER_SCREENSHOT = "browser:screenshot"
    
    # Chat events (for Live Applier)
    CHAT_MESSAGE = "chat:message"
    
    # Async Task Queue events (Celery integration)
    TASK_QUEUED = "task:queued"          # Task added to queue
    TASK_STARTED = "task:started"        # Worker started processing
    TASK_PROGRESS = "task:progress"      # Progress update from worker
    TASK_COMPLETE = "task:complete"      # Task finished successfully
    TASK_FAILED = "task:failed"          # Task failed with error
    
    # NetworkAI events
    NETWORK_SEARCH_START = "network:search_start"
    NETWORK_MATCH_FOUND = "network:match_found"
    NETWORK_SEARCH_COMPLETE = "network:search_complete"


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
            self.timestamp = datetime.now().strftime("%H:%M:%S")
    
    def to_dict(self) -> Dict:
        return {
            "type": self.type.value if isinstance(self.type, EventType) else self.type,
            "agent": self.agent,
            "message": self.message,
            "data": self.data or {},
            "timestamp": self.timestamp
        }


class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""
    

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.event_history: List[AgentEvent] = []
        self.hitl_callbacks: Dict[str, asyncio.Future] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str, token: str = None):
        """Accept and register a new connection with Auth."""
        await websocket.accept()
        
        # Authenticate
        try:
            from src.core.auth import verify_token
            if token:
                 payload = verify_token(token)
                 # Optionally store user info
                 # user_id = payload.get("sub")
            else:
                # In development, we might allow no token, but for Phase 2 we want security.
                # If you want to strictly enforce it:
                # await websocket.close(code=4003) # Forbidden
                # return
                pass
        except Exception as e:
            print(f"WebSocket Auth Failed: {e}")
            await websocket.close(code=4003)
            return

        self.active_connections[session_id] = websocket
        
        # Send connection confirmation
        await self.send_event(session_id, AgentEvent(
            type=EventType.CONNECTED,
            agent="system",
            message="Connected to JobAI agent server"
        ))
        
        # Send event history for reconnection
        for event in self.event_history[-50:]:  # Last 50 events
            await self.send_json(session_id, event.to_dict())
    
    def disconnect(self, session_id: str):
        """Remove a connection."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
    
    async def send_json(self, session_id: str, data: Dict):
        """Send JSON data to a specific session."""
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json(data)
            except Exception:
                self.disconnect(session_id)
    
    async def send_event(self, session_id: str, event: AgentEvent):
        """Send an event to a specific session."""
        self.event_history.append(event)
        await self.send_json(session_id, event.to_dict())
    
    async def broadcast(self, event: AgentEvent):
        """Broadcast an event to all connections."""
        self.event_history.append(event)
        data = event.to_dict()
        
        disconnected = []
        for session_id, ws in self.active_connections.items():
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(session_id)
        
        # Clean up disconnected
        for sid in disconnected:
            self.disconnect(sid)
    
    async def request_hitl(self, session_id: str, question: str, context: str = "") -> str:
        """
        Request human input via WebSocket.
        Blocks until response received.
        """
        hitl_id = f"hitl_{datetime.now().timestamp()}"
        
        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self.hitl_callbacks[hitl_id] = future
        
        # Send HITL request
        await self.send_event(session_id, AgentEvent(
            type=EventType.HITL_REQUEST,
            agent="applier",
            message=question,
            data={"hitl_id": hitl_id, "context": context}
        ))
        
        # Wait for response (with timeout)
        try:
            response = await asyncio.wait_for(future, timeout=300)  # 5 min timeout
            return response
        except asyncio.TimeoutError:
            del self.hitl_callbacks[hitl_id]
            raise TimeoutError("HITL request timed out")
    
    def resolve_hitl(self, hitl_id: str, response: str):
        """Resolve a pending HITL request."""
        if hitl_id in self.hitl_callbacks:
            self.hitl_callbacks[hitl_id].set_result(response)
            del self.hitl_callbacks[hitl_id]


# Global connection manager
manager = ConnectionManager()


class EventEmitter:
    """
    Mixin class for agents to emit events.
    Attach to any agent class to enable real-time updates.
    """
    
    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self._manager = manager
    
    async def emit(self, event_type: EventType, message: str, data: Optional[Dict] = None):
        """Emit an event to the connected frontend."""
        event = AgentEvent(
            type=event_type,
            agent=self.__class__.__name__.replace("Agent", "").lower(),
            message=message,
            data=data
        )
        await self._manager.broadcast(event)
    
    async def emit_screenshot(self, screenshot_base64: str):
        """Emit a browser screenshot."""
        await self.emit(
            EventType.BROWSER_SCREENSHOT,
            "Browser screenshot",
            {"screenshot": screenshot_base64}
        )
    
    async def ask_human_ws(self, question: str, context: str = "") -> str:
        """Request human input via WebSocket instead of stdin."""
        return await self._manager.request_hitl(self.session_id, question, context)
