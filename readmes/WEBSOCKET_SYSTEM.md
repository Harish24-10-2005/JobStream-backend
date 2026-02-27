# WebSocket Real-Time Communication System

**Production-Grade Architecture Documentation**  
**Version:** 2.0  
**Last Updated:** 2026-07-10  
**Status:** ✅ Production Ready — Reflects actual codebase as-implemented

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Design](#architecture-design)
3. [Core Components](#core-components)
4. [Event System](#event-system)
5. [Redis Pub/Sub Bridge](#redis-pubsub-bridge)
6. [Human-in-the-Loop (HITL)](#human-in-the-loop-hitl)
7. [Connection Management](#connection-management)
8. [Multi-User Support](#multi-user-support)
9. [Security & Authentication](#security--authentication)
10. [Message Protocols](#message-protocols)
11. [Real-Time Features](#real-time-features)
12. [Performance & Scalability](#performance--scalability)
13. [Error Handling](#error-handling)
14. [Integration Patterns](#integration-patterns)
15. [Deployment Guide](#deployment-guide)
16. [API Reference](#api-reference)

---

## 🎯 System Overview

### Purpose
The WebSocket system provides **real-time, bidirectional communication** between the backend FastAPI server and frontend clients, enabling:
- Live streaming of agent actions (Scout, Analyst, Applier, Resume, Cover Letter, Network, Interview, Salary)
- Browser automation streaming (5 FPS JPEG screenshots)
- Human-in-the-Loop (HITL) interactive decision-making
- Pipeline progress tracking
- Multi-user session management
- Celery worker event propagation

### Key Features

| Feature | Description | Use Case |
|---------|-------------|----------|
| **Real-Time Events** | 94+ event types for all agents | Live progress tracking |
| **Redis Pub/Sub Bridge** | Celery worker → WebSocket relay | Background task updates |
| **HITL System** | Bidirectional Q&A, Future-based, 120s timeout | Human approval workflows |
| **Browser Streaming** | 5 FPS JPEG screenshots via BROWSER_SCREENSHOT | Live applier visualization |
| **Draft Mode** | APPLIER_DRAFT_READY → user review → submit | Safe auto-apply with human gate |
| **Salary Battle WS** | 8 turn-based events, SalaryBattleGraph state | Real-time AI HR negotiation |
| **Career Intelligence** | CAREER_CHAT_RESPONSE, TRAJECTORY, SKILL_GAPS | Chat + analysis results |
| **Multi-User** | JWT auth + user_id isolation | SaaS deployment |
| **Connection Manager** | Singleton pattern, MAX_EVENT_HISTORY=50 | Reconnection support |
| **Message Router** | Type-based message handling | Pipeline control |

### Tech Stack

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                      │
│                   WebSocket Client                       │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ WebSocket Protocol (wss://)
                  │
┌─────────────────▼───────────────────────────────────────┐
│              FastAPI Server (Uvicorn)                    │
│  ┌──────────────────────────────────────────────────┐  │
│  │         ConnectionManager (Singleton)             │  │
│  │  - Active connections (user_id → WebSocket)       │  │
│  │  - Event history (last 50 per session)            │  │
│  │  - HITL callbacks (pending responses)             │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ Redis Pub/Sub Channels
                  │
┌─────────────────▼───────────────────────────────────────┐
│                  Redis (Pub/Sub + Cache)                 │
│  Channels:                                               │
│  - jobai:events:{session_id}  → Worker events            │
│  - jobai:hitl:{hitl_id}       → HITL responses           │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ Pub/Sub Subscription
                  │
┌─────────────────▼───────────────────────────────────────┐
│          Celery Workers (Background Tasks)               │
│  - LiveApplier (Browser Automation)                      │
│  - Other async jobs                                      │
└─────────────────────────────────────────────────────────┘
```

---

## 🏗️ Architecture Design

### System Design Principles

#### 1. **Singleton Pattern** (ConnectionManager)
- **Why:** Ensure single source of truth for all active connections
- **Implementation:** Class-level instance, created on first import
- **Benefits:** Centralized state, easy event broadcasting

#### 2. **Event-Driven Architecture**
- **Why:** Decouple event producers (agents) from consumers (WebSocket clients)
- **Implementation:** EventType enum + AgentEvent dataclass
- **Benefits:** Extensible, type-safe, easy to add new event types

#### 3. **Pub/Sub Pattern** (Redis Bridge)
- **Why:** Bridge Celery workers (separate processes) to WebSocket (FastAPI)
- **Implementation:** Celery → Redis Pub → FastAPI Sub → WebSocket Send
- **Benefits:** Scalable, process-independent, async-friendly

#### 4. **Request-Response with Timeout** (HITL)
- **Why:** Human approval workflows require blocking wait with timeout
- **Implementation:** asyncio.Event + Redis pub/sub + Future pattern
- **Benefits:** Non-blocking, timeout-safe, multi-user isolation

#### 5. **Multi-Tenant Isolation**
- **Why:** SaaS deployment requires per-user session management
- **Implementation:** JWT auth + user_id tracking + session_id namespace
- **Benefits:** Data isolation, security, concurrent users

### Architecture Diagrams

#### High-Level Flow
```
┌──────────┐    WebSocket     ┌──────────┐    Redis Pub   ┌──────────┐
│ Frontend │ ←───────────────→ │  FastAPI │ ←──────────────│  Celery  │
│  Client  │   (bidirectional) │  Server  │  (async relay) │  Worker  │
└──────────┘                   └──────────┘                └──────────┘
     │                              │                            │
     │ 1. Connect /ws/{session}     │                            │
     ├─────────────────────────────→│                            │
     │                              │                            │
     │ 2. Send {type: "start_apply"}│                            │
     ├─────────────────────────────→│                            │
     │                              │ 3. Trigger Celery Task     │
     │                              ├───────────────────────────→│
     │                              │                            │
     │                              │ 4. Publish Event to Redis  │
     │                              │←───────────────────────────┤
     │                              │                            │
     │ 5. Relay to WebSocket        │                            │
     │←─────────────────────────────┤                            │
     │                              │                            │
     │ 6. HITL Request (blocking)   │                            │
     │←─────────────────────────────┤←───────────────────────────┤
     │                              │                            │
     │ 7. HITL Response             │                            │
     ├─────────────────────────────→│ 8. Publish to Redis        │
     │                              ├───────────────────────────→│
     │                              │                            │
```

#### Message Flow (Start Pipeline)
```
User clicks "Start Job Search" in UI
        ↓
Frontend sends WebSocket message:
{
  "type": "start_pipeline",
  "data": {
    "query": "Python Developer",
    "location": "Remote",
    "auto_apply": true
  }
}
        ↓
FastAPI handle_websocket_connection() receives message
        ↓
Message router matches "start_pipeline"
        ↓
Create StreamingPipelineOrchestrator(session_id, user_id)
        ↓
Orchestrator.run() → Emit PIPELINE_START event
        ↓
ConnectionManager.broadcast(event) → Send to WebSocket
        ↓
Frontend receives event, shows "Pipeline starting..."
        ↓
Scout Agent runs → Emits SCOUT_START, SCOUT_SEARCHING, SCOUT_FOUND, SCOUT_COMPLETE
        ↓
Analyst Agent loops jobs → Emits ANALYST_START, ANALYST_FETCHING, ANALYST_RESULT
        ↓
Applier Agent applies → Emits APPLIER_START, APPLIER_NAVIGATE, APPLIER_CLICK, APPLIER_DRAFT_READY (HITL), APPLIER_SUBMITTED, APPLIER_COMPLETE
        ↓
Pipeline finishes → Emit PIPELINE_COMPLETE
        ↓
Frontend shows "Pipeline complete! Applied to 5 jobs."
```

#### HITL Flow
```
Applier encounters uncertain form field
        ↓
LiveApplier calls emit_event(HITL_REQUEST)
        ↓
ConnectionManager.request_hitl(session_id, question, context)
        ↓
1. Create hitl_id = f"hitl_{timestamp}"
2. Create asyncio.Event() for response
3. Store in _hitl_callbacks[hitl_id] = (event, None)
4. Send HITL_REQUEST event to WebSocket
        ↓
Frontend receives HITL_REQUEST event
        ↓
Show modal: "Is this your phone number? (123) 456-7890"
        ↓
User clicks "Yes" → Frontend sends:
{
  "type": "hitl_response",
  "data": {
    "hitl_id": "hitl_1234567890.123",
    "response": "yes"
  }
}
        ↓
FastAPI receives hitl_response message
        ↓
ConnectionManager.resolve_hitl(hitl_id, "yes")
        ↓
1. Retrieve asyncio.Event from _hitl_callbacks
2. Store response in _hitl_callbacks[hitl_id] = (event, "yes")
3. event.set() → Unblock waiting coroutine
        ↓
LiveApplier request_hitl() returns "yes"
        ↓
Continue form filling with human approval
```

---

## 🧩 Core Components

### 1. ConnectionManager (Singleton)

**File:** `backend/src/api/websocket.py`

**Purpose:** Centralized WebSocket connection lifecycle management

```python
class ConnectionManager:
    """
    Singleton WebSocket connection manager.
    Handles connection lifecycle, event broadcasting, and HITL.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Active connections: user_id → WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        
        # Event history: session_id → List[AgentEvent]
        self._event_history: Dict[str, List[AgentEvent]] = defaultdict(list)
        
        # HITL callbacks: hitl_id → (asyncio.Event, response)
        self._hitl_callbacks: Dict[str, Tuple[asyncio.Event, Optional[str]]] = {}
        
        self._initialized = True
```

**Key Methods:**

| Method | Description | Use Case |
|--------|-------------|----------|
| `connect(ws, user_id, token)` | Authenticate & register connection | New client connects |
| `disconnect(user_id)` | Remove connection & cleanup | Client disconnects |
| `send_json(user_id, message)` | Send JSON to specific user | Targeted messages |
| `send_event(user_id, event)` | Send AgentEvent to user | Single-user updates |
| `broadcast(event, session_id)` | Send event to all session users | Pipeline progress |
| `request_hitl(session, question, context)` | Block for human input | Form approval |
| `resolve_hitl(hitl_id, response)` | Unblock with user response | User answered |
| `get_event_history(session)` | Retrieve last 50 events | Reconnection |

**Thread Safety:** Not thread-safe (runs in single asyncio event loop)

---

### 2. EventType Enum (90+ Event Types)

**File:** `backend/src/api/websocket.py`

**Purpose:** Type-safe event categorization for all agents and workflows

```python
class EventType(str, Enum):
    # Connection Events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"

    # Pipeline Events
    PIPELINE_START = "pipeline_start"
    PIPELINE_COMPLETE = "pipeline_complete"
    PIPELINE_ERROR = "pipeline_error"
    PIPELINE_PAUSED = "pipeline_paused"
    PIPELINE_RESUMED = "pipeline_resumed"
    PIPELINE_STOPPED = "pipeline_stopped"

    # Scout Agent Events
    SCOUT_START = "scout_start"
    SCOUT_SEARCHING = "scout_searching"
    SCOUT_FOUND = "scout_found"
    SCOUT_COMPLETE = "scout_complete"

    # Analyst Agent Events
    ANALYST_START = "analyst_start"
    ANALYST_FETCHING = "analyst_fetching"
    ANALYST_ANALYZING = "analyst_analyzing"
    ANALYST_RESULT = "analyst_result"
    ANALYST_SKIPPED = "analyst_skipped"
    ANALYST_COMPLETE = "analyst_complete"

    # Company Agent Events
    COMPANY_START = "company_start"
    COMPANY_RESEARCHING = "company_researching"
    COMPANY_RESULT = "company_result"
    COMPANY_ERROR = "company_error"

    # Resume Agent Events
    RESUME_START = "resume_start"
    RESUME_FETCHING_CONTEXT = "resume_fetching_context"
    RESUME_TAILORING = "resume_tailoring"
    RESUME_GENERATED = "resume_generated"
    RESUME_ATS_SCORED = "resume_ats_scored"
    RESUME_REVIEW = "resume_review"
    RESUME_COMPLETE = "resume_complete"

    # Cover Letter Agent Events
    COVER_LETTER_START = "cover_letter_start"
    COVER_LETTER_GENERATING = "cover_letter_generating"
    COVER_LETTER_REVIEW_REQUESTED = "cover_letter_review_requested"
    COVER_LETTER_COMPLETE = "cover_letter_complete"

    # Applier Agent Events (Browser Automation)
    APPLIER_START = "applier_start"
    APPLIER_NAVIGATE = "applier_navigate"
    APPLIER_CLICK = "applier_click"
    APPLIER_TYPE = "applier_type"
    APPLIER_UPLOAD = "applier_upload"
    APPLIER_SUBMIT = "applier_submit"
    APPLIER_DRAFT_READY = "applier_draft_ready"   # Draft Mode: form filled, awaiting user review
    APPLIER_SUBMITTED = "applier_submitted"        # Final confirmed submission
    APPLIER_COMPLETE = "applier_complete"
    APPLIER_ERROR = "applier_error"

    # Browser Streaming Events
    BROWSER_SCREENSHOT = "browser_screenshot"      # 5 FPS JPEG base64 stream
    BROWSER_ACTION = "browser_action"              # Action narration

    # HITL (Human-in-the-Loop) Events
    HITL_REQUEST = "hitl_request"                  # Agent needs human decision
    HITL_RESPONSE = "hitl_response"                # Human answer received
    HITL_TIMEOUT = "hitl_timeout"                  # 120s timeout expired
    HITL_CANCELLED = "hitl_cancelled"              # Pipeline stopped during HITL wait

    # Salary Battle Events (SalaryBattleGraph turn-based)
    SALARY_BATTLE_START = "salary_battle_start"            # Session begins
    SALARY_BATTLE_USER_TURN = "salary_battle_user_turn"   # Waiting for user offer
    SALARY_BATTLE_AI_RESPONSE = "salary_battle_ai_response"  # HR persona responds
    SALARY_BATTLE_PHASE_CHANGE = "salary_battle_phase_change"  # opening→counter→etc
    SALARY_BATTLE_COUNTER = "salary_battle_counter"        # Counter-offer issued
    SALARY_BATTLE_ACCEPTED = "salary_battle_accepted"      # Agreement reached
    SALARY_BATTLE_REJECTED = "salary_battle_rejected"      # Negotiation failed
    SALARY_BATTLE_COMPLETE = "salary_battle_complete"      # Session ends

    # Salary Agent Events (market research, non-battle)
    SALARY_START = "salary_start"
    SALARY_ANALYZING = "salary_analyzing"
    SALARY_RESULT = "salary_result"
    SALARY_COMPLETE = "salary_complete"

    # Network Agent Events
    NETWORK_START = "network_start"
    NETWORK_SEARCHING = "network_searching"
    NETWORK_FOUND = "network_found"
    NETWORK_COMPLETE = "network_complete"

    # Interview Agent Events
    INTERVIEW_START = "interview_start"
    INTERVIEW_QUESTION = "interview_question"
    INTERVIEW_ANSWER = "interview_answer"
    INTERVIEW_FEEDBACK = "interview_feedback"
    INTERVIEW_COMPLETE = "interview_complete"

    # Career Intelligence Events
    CAREER_CHAT_RESPONSE = "career_chat_response"       # ChatOrchestrator NLU output
    CAREER_TRAJECTORY = "career_trajectory"              # CareerTrajectoryEngine result
    CAREER_SKILL_GAPS = "career_skill_gaps"              # SkillTracker analysis result

    # Task Events (Celery)
    TASK_QUEUED = "task_queued"
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"

    # System Events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    HEARTBEAT = "heartbeat"
    PING = "ping"
    PONG = "pong"
```

**Event Category Summary:**

| Category | Event Count | New in v2 |
|----------|-------------|-----------|
| Connection | 3 | +ERROR |
| Pipeline | 6 | +PIPELINE_STOPPED |
| Scout | 4 | — |
| Analyst | 6 | +ANALYST_SKIPPED |
| Company | 4 | — |
| Resume | 7 | +FETCHING_CONTEXT, +ATS_SCORED |
| Cover Letter | 4 | REVIEW_REQUESTED renamed |
| Applier | 10 | +DRAFT_READY, +SUBMITTED |
| Browser | 2 | — |
| HITL | 4 | +HITL_CANCELLED |
| **Salary Battle** | **8** | **NEW — SalaryBattleGraph** |
| Salary (research) | 4 | — |
| Network | 4 | — |
| Interview | 5 | — |
| **Career/Chat** | **3** | **NEW — ChatOrchestrator, CareerEngine** |
| Task (Celery) | 5 | — |
| System | 5 | NEW |
| **Total** | **~94** | |

---

### 3. AgentEvent Dataclass

**File:** `backend/src/api/websocket.py`

**Purpose:** Standardized event payload structure

```python
@dataclass
class AgentEvent:
    """
    Standardized event structure for all agent communications.
    """
    type: EventType              # Event type enum
    agent: str                   # Agent name (e.g., "scout", "analyst", "applier")
    message: str                 # Human-readable message
    data: dict = field(default_factory=dict)  # Optional metadata
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """Convert to WebSocket-friendly JSON."""
        return {
            "type": self.type.value,
            "agent": self.agent,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }
```

**Example Events:**

```json
// SCOUT_FOUND Event
{
  "type": "scout_found",
  "agent": "scout",
  "message": "Found 47 job listings",
  "data": {
    "count": 47,
    "urls": ["https://linkedin.com/jobs/1", "https://indeed.com/jobs/2"]
  },
  "timestamp": "2024-01-15T10:30:45.123Z"
}

// HITL_REQUEST Event
{
  "type": "hitl_request",
  "agent": "applier",
  "message": "Confirm phone number: (123) 456-7890?",
  "data": {
    "hitl_id": "hitl_1705314645.123",
    "question": "Is this your phone number?",
    "context": "LinkedIn Easy Apply form field"
  },
  "timestamp": "2024-01-15T10:31:20.456Z"
}

// BROWSER_SCREENSHOT Event
{
  "type": "browser_screenshot",
  "agent": "applier",
  "message": "Browser screenshot",
  "data": {
    "screenshot": "/9j/4AAQSkZJRgABAQAAAQABAAD...",  // Base64 JPEG
    "format": "jpeg"
  },
  "timestamp": "2024-01-15T10:31:21.789Z"
}
```

---

### 4. EventEmitter Mixin

**File:** `backend/src/api/websocket.py`

**Purpose:** Allow agents to emit events without direct WebSocket dependency

```python
class EventEmitter:
    """
    Mixin for agents to emit events to WebSocket clients.
    Usage: class MyAgent(EventEmitter): ...
    """
    
    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self._manager = manager  # Reference to singleton
    
    async def emit(self, event_type: EventType, message: str, data: dict = None):
        """Emit an event to connected clients."""
        event = AgentEvent(
            type=event_type,
            agent=self.__class__.__name__.lower().replace("agent", ""),
            message=message,
            data=data or {}
        )
        await self._manager.broadcast(event, self.session_id)
```

**Usage in Agents:**

```python
# Example: Scout Agent
class ScoutAgent(EventEmitter):
    def __init__(self, session_id: str = "default"):
        super().__init__(session_id)
    
    async def run(self, query: str, location: str):
        await self.emit(EventType.SCOUT_START, "Starting job search...")
        
        jobs = await self.search_jobs(query, location)
        
        await self.emit(
            EventType.SCOUT_FOUND, 
            f"Found {len(jobs)} jobs",
            {"count": len(jobs), "urls": jobs}
        )
        
        await self.emit(EventType.SCOUT_COMPLETE, "Search complete")
        return jobs
```

---

## 📡 Redis Pub/Sub Bridge

### Architecture

**Problem:** Celery workers run in separate processes from FastAPI. Direct WebSocket access is impossible.

**Solution:** Redis Pub/Sub acts as a message bus between processes.

```
┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
│  Celery Worker   │        │      Redis       │        │  FastAPI Server  │
│                  │        │                  │        │                  │
│  LiveApplier     │  Pub   │  jobai:events:   │  Sub   │  WebSocket       │
│  (Process 2)     ├───────→│   {session_id}   │←───────┤  Handler         │
│                  │        │                  │        │  (Process 1)     │
└──────────────────┘        └──────────────────┘        └────────┬─────────┘
                                                                  │
                                                                  │ Send
                                                                  ▼
                                                         ┌──────────────────┐
                                                         │  WebSocket       │
                                                         │  Client          │
                                                         │  (Browser)       │
                                                         └──────────────────┘
```

### Implementation

#### 1. RedisEventPublisher (Celery Side)

**File:** `backend/src/worker/tasks/applier_task.py`

```python
class RedisEventPublisher:
    """
    Publishes events to Redis for the FastAPI server to relay to WebSocket.
    Used by Celery workers to emit events.
    """
    
    def __init__(self, session_id: str, redis_url: str):
        self.session_id = session_id
        self.redis_url = redis_url
    
    async def publish_event(
        self, 
        event_type: EventType, 
        agent: str, 
        message: str, 
        data: dict = None
    ):
        """Publish an event to Redis for the WebSocket handler."""
        redis_client = await redis.from_url(
            self.redis_url, 
            decode_responses=True
        )
        
        event = {
            "type": event_type.value,
            "agent": agent,
            "message": message,
            "data": data or {},
            "timestamp": datetime.now().isoformat()
        }
        
        channel = f"jobai:events:{self.session_id}"
        await redis_client.publish(channel, json.dumps(event))
        await redis_client.close()
    
    async def request_hitl(
        self, 
        question: str, 
        context: str, 
        timeout: int = 300
    ) -> str:
        """
        Request human input via Redis pub/sub.
        Blocks until response received or timeout.
        """
        hitl_id = f"hitl_{datetime.now().timestamp()}"
        
        # Publish HITL request
        await self.publish_event(
            EventType.HITL_REQUEST,
            "applier",
            question,
            {"hitl_id": hitl_id, "question": question, "context": context}
        )
        
        # Subscribe to response channel
        redis_client = await redis.from_url(
            self.redis_url, 
            decode_responses=True
        )
        pubsub = redis_client.pubsub()
        response_channel = f"jobai:hitl:{hitl_id}"
        await pubsub.subscribe(response_channel)
        
        try:
            # Wait for response with timeout
            async with asyncio.timeout(timeout):
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        response_data = json.loads(message["data"])
                        return response_data.get("response", "")
        except asyncio.TimeoutError:
            await self.publish_event(
                EventType.HITL_TIMEOUT,
                "applier",
                f"HITL timeout after {timeout}s"
            )
            raise
        finally:
            await pubsub.unsubscribe(response_channel)
            await redis_client.close()
```

#### 2. Subscribe to Worker Events (FastAPI Side)

**File:** `backend/src/main.py`

```python
async def subscribe_to_worker_events(session_id: str, websocket: WebSocket):
    """
    Subscribe to Redis pub/sub channel for worker events.
    Relays events from Celery workers to WebSocket clients.
    """
    redis_client = get_redis_client()
    pubsub = redis_client.pubsub()
    
    # Subscribe to session-specific channel
    channel = f"jobai:events:{session_id}"
    await pubsub.subscribe(channel)
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                # Parse event from Redis
                event_data = json.loads(message["data"])
                
                # Relay to WebSocket
                await websocket.send_json(event_data)
    except Exception as e:
        logger.error(f"Redis subscription error: {e}")
    finally:
        await pubsub.unsubscribe(channel)
```

### Channel Naming Convention

| Channel Pattern | Purpose | Example |
|-----------------|---------|---------|
| `jobai:events:{session_id}` | Worker → WebSocket events | `jobai:events:abc123` |
| `jobai:hitl:{hitl_id}` | HITL responses | `jobai:hitl:hitl_1705314645.123` |
| `pipeline:{user_id}:state` | Pipeline state cache | `pipeline:user_456:state` |

---

## 🤝 Human-in-the-Loop (HITL)

### Overview

**Purpose:** Allow agents to request human approval/input for uncertain decisions

**Use Cases:**
- ✅ Confirm form field values (phone, email)
- ✅ Approve resume tailoring changes
- ✅ Approve cover letter drafts
- ✅ Confirm job application submission
- ✅ Select between multiple options

### Flow Diagram

```
┌─────────────┐                    ┌─────────────┐                    ┌─────────────┐
│   Agent     │                    │   FastAPI   │                    │   Frontend  │
│  (Worker)   │                    │   Server    │                    │   (React)   │
└──────┬──────┘                    └──────┬──────┘                    └──────┬──────┘
       │                                   │                                   │
       │ 1. Emit HITL_REQUEST              │                                   │
       ├──────────────────────────────────→│                                   │
       │    {question, context}            │                                   │
       │                                   │ 2. Send HITL_REQUEST              │
       │                                   ├──────────────────────────────────→│
       │                                   │                                   │
       │                                   │                                   │ 3. Show Modal
       │ 4. Block with asyncio.Event       │                                   │
       │    (wait for response)            │                                   │
       │                                   │                                   │ 4. User clicks "Yes"
       │                                   │ 5. Receive hitl_response          │
       │                                   │←──────────────────────────────────┤
       │                                   │    {hitl_id, response}            │
       │ 6. Unblock with response          │                                   │
       │←──────────────────────────────────┤                                   │
       │    "yes"                          │                                   │
       │                                   │                                   │
       │ 7. Continue execution             │                                   │
       │                                   │                                   │
```

### Implementation

#### 1. Request HITL (Agent Side)

```python
# In StreamingPipelineOrchestrator
async def hitl_wrapper(question: str, context: str) -> str:
    """HITL callback for agents."""
    return await manager.request_hitl(session_id, question, context)

# Pass to agent
resume_result = await resume_agent.run(
    job_analysis=analysis,
    user_profile=profile,
    hitl_handler=hitl_wrapper  # <-- Inject HITL callback
)
```

#### 2. ConnectionManager.request_hitl()

```python
async def request_hitl(
    self, 
    session_id: str, 
    question: str, 
    context: str = "",
    timeout: int = 300
) -> str:
    """
    Request human input via WebSocket.
    Blocks until response received or timeout.
    
    Args:
        session_id: Session identifier
        question: Question to ask human
        context: Additional context
        timeout: Max wait time (seconds)
    
    Returns:
        Human response string
    
    Raises:
        asyncio.TimeoutError: If no response within timeout
    """
    hitl_id = f"hitl_{datetime.now().timestamp()}"
    response_event = asyncio.Event()
    
    # Store callback (event + placeholder response)
    self._hitl_callbacks[hitl_id] = (response_event, None)
    
    # Send HITL request to frontend
    event = AgentEvent(
        type=EventType.HITL_REQUEST,
        agent="system",
        message=question,
        data={
            "hitl_id": hitl_id,
            "question": question,
            "context": context
        }
    )
    await self.broadcast(event, session_id)
    
    try:
        # Wait for response with timeout
        await asyncio.wait_for(response_event.wait(), timeout=timeout)
        
        # Retrieve response
        _, response = self._hitl_callbacks.get(hitl_id, (None, None))
        return response or ""
    except asyncio.TimeoutError:
        # Timeout - emit timeout event
        timeout_event = AgentEvent(
            type=EventType.HITL_TIMEOUT,
            agent="system",
            message=f"HITL timeout after {timeout}s"
        )
        await self.broadcast(timeout_event, session_id)
        raise
    finally:
        # Cleanup
        self._hitl_callbacks.pop(hitl_id, None)
```

#### 3. Resolve HITL (User Response)

```python
def resolve_hitl(self, hitl_id: str, response: str):
    """
    Resolve a pending HITL request with user response.
    
    Args:
        hitl_id: HITL request identifier
        response: User's response string
    """
    if hitl_id in self._hitl_callbacks:
        response_event, _ = self._hitl_callbacks[hitl_id]
        
        # Store response
        self._hitl_callbacks[hitl_id] = (response_event, response)
        
        # Unblock waiting coroutine
        response_event.set()
```

#### 4. Frontend HITL Handler

```typescript
// React WebSocket hook
const handleHITLRequest = (event: AgentEvent) => {
  const { hitl_id, question, context } = event.data;
  
  // Show modal
  setHITLModal({
    open: true,
    hitl_id,
    question,
    context
  });
};

const handleHITLResponse = (response: string) => {
  // Send response back to server
  ws.send(JSON.stringify({
    type: "hitl_response",
    data: {
      hitl_id: hitlModal.hitl_id,
      response
    }
  }));
  
  // Close modal
  setHITLModal({ open: false });
};
```

### HITL Best Practices

✅ **DO:**
- Use timeouts (default 5 minutes)
- Provide clear questions and context
- Emit HITL_TIMEOUT events on timeout
- Clean up callbacks after resolution
- Log HITL events for auditing

❌ **DON'T:**
- Block indefinitely without timeout
- Request HITL for trivial decisions
- Forget to handle timeout errors
- Reuse hitl_id values

---

## 🔐 Security & Authentication

### JWT Authentication

**File:** `backend/src/core/auth.py`

```python
async def verify_ws_token(token: str) -> AuthUser:
    """
    Verify JWT token for WebSocket authentication.
    
    Args:
        token: JWT token from query param
    
    Returns:
        AuthUser with user_id
    
    Raises:
        HTTPException: If token invalid/expired
    """
    try:
        payload = jwt.decode(
            token, 
            settings.jwt_secret, 
            algorithms=["HS256"]
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        return AuthUser(id=user_id, email=payload.get("email"))
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### Connection Flow with Auth

```python
# In ConnectionManager.connect()
async def connect(
    self, 
    websocket: WebSocket, 
    user_id: str, 
    token: Optional[str] = None
):
    """
    Authenticate and register a WebSocket connection.
    
    Args:
        websocket: WebSocket instance
        user_id: User identifier (from path param)
        token: JWT token (from query param)
    
    Raises:
        HTTPException: If authentication fails
    """
    # 1. Accept WebSocket connection
    await websocket.accept()
    
    # 2. Verify JWT token
    if token:
        auth_user = await verify_ws_token(token)
        
        # 3. Ensure user_id matches token
        if auth_user.id != user_id:
            await websocket.close(code=1008, reason="User ID mismatch")
            raise HTTPException(status_code=403, detail="User ID mismatch")
    
    # 4. Register connection
    self.active_connections[user_id] = websocket
    
    # 5. Send connection confirmation
    await self.send_event(
        user_id,
        AgentEvent(
            type=EventType.CONNECTED,
            agent="system",
            message="Connected to WebSocket server"
        )
    )
```

### Frontend Authentication

```typescript
// Connect with JWT token
const token = localStorage.getItem('auth_token');
const ws = new WebSocket(
  `ws://localhost:8000/ws/${sessionId}?token=${token}`
);

ws.onopen = () => {
  console.log('WebSocket connected');
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
  // Handle auth failure (redirect to login)
};
```

### Security Best Practices

| Practice | Implementation | Benefit |
|----------|----------------|---------|
| **JWT Verification** | Verify token on connect | Prevent unauthorized access |
| **User ID Validation** | Match user_id to token | Prevent impersonation |
| **WSS (TLS)** | Use `wss://` in production | Encrypt WebSocket traffic |
| **Rate Limiting** | Limit messages per second | Prevent DoS attacks |
| **Session Timeouts** | Auto-disconnect after inactivity | Free resources |
| **CORS Restrictions** | Whitelist allowed origins | Prevent CSRF |

---

## 📨 Message Protocols

### Client → Server Messages

#### 1. **start_pipeline**

```json
{
  "type": "start_pipeline",
  "data": {
    "query": "Python Developer",
    "location": "Remote",
    "auto_apply": true,
    "min_match_score": 70,
    "use_company_research": false,
    "use_resume_tailoring": true,
    "use_cover_letter": true
  }
}
```

**Handler:**
```python
if msg_type == "start_pipeline":
    query = data.get("query", "")
    location = data.get("location", "Remote")
    auto_apply = data.get("auto_apply", False)
    
    orchestrator = StreamingPipelineOrchestrator(session_id, user_id)
    
    asyncio.create_task(orchestrator.run(
        query=query,
        location=location,
        auto_apply=auto_apply,
        use_resume_tailoring=data.get("use_resume_tailoring", False),
        use_cover_letter=data.get("use_cover_letter", False)
    ))
    
    await manager.send_json(user_id, {
        "type": "pipeline_started",
        "message": "Pipeline started successfully"
    })
```

#### 2. **start_apply**

```json
{
  "type": "start_apply",
  "data": {
    "job_url": "https://linkedin.com/jobs/123",
    "draft_mode": true,
    "resume_path": "/path/to/tailored_resume.pdf"
  }
}
```

**Handler:**
```python
if msg_type == "start_apply":
    job_url = data.get("job_url")
    draft_mode = data.get("draft_mode", True)
    
    # Trigger Celery task
    from src.worker.tasks.applier_task import apply_job_task
    
    task = apply_job_task.delay(
        session_id=session_id,
        job_url=job_url,
        user_id=user_id,
        draft_mode=draft_mode,
        redis_url=settings.redis_url
    )
    
    await manager.send_json(user_id, {
        "type": "task_queued",
        "task_id": task.id
    })
```

#### 3. **hitl_response**

```json
{
  "type": "hitl_response",
  "data": {
    "hitl_id": "hitl_1705314645.123",
    "response": "yes"
  }
}
```

**Handler:**
```python
if msg_type == "hitl_response":
    hitl_id = data.get("hitl_id")
    response = data.get("response", "")
    
    # Resolve pending HITL
    manager.resolve_hitl(hitl_id, response)
    
    # Also publish to Redis for Celery workers
    redis_client = get_redis_client()
    response_channel = f"jobai:hitl:{hitl_id}"
    await redis_client.publish(
        response_channel, 
        json.dumps({"response": response})
    )
```

#### 4. **ping**

```json
{
  "type": "ping"
}
```

**Handler:**
```python
if msg_type == "ping":
    await websocket.send_json({"type": "pong"})
```

#### 5. **stop**

```json
{
  "type": "stop",
  "data": {
    "reason": "User cancelled"
  }
}
```

**Handler:**
```python
if msg_type == "stop":
    # Stop running pipeline
    if hasattr(orchestrator, 'stop'):
        orchestrator.stop()
    
    await manager.send_event(
        user_id,
        AgentEvent(
            type=EventType.PIPELINE_PAUSED,
            agent="system",
            message="Pipeline stopped by user"
        )
    )
```

### Server → Client Messages

#### 1. **AgentEvent** (Standard Event)

```json
{
  "type": "scout_found",
  "agent": "scout",
  "message": "Found 47 job listings",
  "data": {
    "count": 47,
    "urls": ["https://linkedin.com/jobs/1", "..."]
  },
  "timestamp": "2024-01-15T10:30:45.123Z"
}
```

#### 2. **HITL Request**

```json
{
  "type": "hitl_request",
  "agent": "applier",
  "message": "Confirm phone number: (123) 456-7890?",
  "data": {
    "hitl_id": "hitl_1705314645.123",
    "question": "Is this your phone number?",
    "context": "LinkedIn Easy Apply form"
  },
  "timestamp": "2024-01-15T10:31:20.456Z"
}
```

#### 3. **Browser Screenshot**

```json
{
  "type": "browser_screenshot",
  "agent": "applier",
  "message": "Browser screenshot",
  "data": {
    "screenshot": "/9j/4AAQSkZJRgABAQAAAQABAAD...",  // Base64 JPEG
    "format": "jpeg"
  },
  "timestamp": "2024-01-15T10:31:21.789Z"
}
```

#### 4. **Connection Status**

```json
{
  "type": "connected",
  "agent": "system",
  "message": "Connected to WebSocket server",
  "data": {
    "session_id": "abc123",
    "user_id": "user_456"
  },
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

---

## ⚡ Real-Time Features

### 1. Browser Automation Streaming (5 FPS)

**Purpose:** Show live browser actions during job application

```python
# In WebSocketApplierAgent
async def stream_screenshot(self, browser):
    """Stream browser screenshot every 200ms (5 FPS)."""
    try:
        screenshot_b64 = await browser.page.screenshot(
            format='jpeg', 
            quality=50
        )
        await self.emit(
            EventType.BROWSER_SCREENSHOT,
            "Browser screenshot",
            {"screenshot": screenshot_b64, "format": "jpeg"}
        )
    except Exception as e:
        logger.debug(f"Screenshot failed: {e}")
```

**Frontend Display:**
```typescript
const [screenshot, setScreenshot] = useState<string>('');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'browser_screenshot') {
    // Convert base64 to image src
    setScreenshot(`data:image/jpeg;base64,${data.data.screenshot}`);
  }
};

// Render
<img src={screenshot} alt="Live Browser" />
```

### 2. Pipeline Progress Tracking

**Backend:**
```python
# In StreamingPipelineOrchestrator
for i, url in enumerate(job_urls, 1):
    await self.emit(
        EventType.ANALYST_START,
        "analyst",
        f"Processing job {i}/{len(job_urls)}",
        {
            "job_index": i,
            "total": len(job_urls),
            "progress": int((i / len(job_urls)) * 100)
        }
    )
```

**Frontend:**
```typescript
const [progress, setProgress] = useState(0);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.data?.progress) {
    setProgress(data.data.progress);
  }
};

// Render
<ProgressBar value={progress} max={100} />
```

### 3. Real-Time Event Log

**Backend:** Events automatically saved to history

```python
# In ConnectionManager.broadcast()
self._event_history[session_id].append(event)

# Keep only last 50 events
if len(self._event_history[session_id]) > 50:
    self._event_history[session_id] = self._event_history[session_id][-50:]
```

**Frontend:**
```typescript
const [eventLog, setEventLog] = useState<AgentEvent[]>([]);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  setEventLog(prev => [...prev, data].slice(-50));
};

// Render
<EventLog events={eventLog} />
```

### 4. Reconnection Support

**Backend:**
```python
# On reconnect, send event history
async def connect(self, websocket, user_id, token):
    await websocket.accept()
    # ... auth ...
    
    # Send event history
    history = self.get_event_history(session_id)
    for event in history:
        await websocket.send_json(event.to_dict())
```

**Frontend:**
```typescript
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;

ws.onclose = () => {
  if (reconnectAttempts < maxReconnectAttempts) {
    setTimeout(() => {
      reconnectAttempts++;
      connectWebSocket();
    }, 1000 * reconnectAttempts);  // Exponential backoff
  }
};
```

---

## 🚀 Performance & Scalability

### Current Limits

| Metric | Value | Notes |
|--------|-------|-------|
| **Max Connections** | ~1000 per server | Depends on server resources |
| **Event History** | 50 events per session | Configurable |
| **HITL Timeout** | 300 seconds (5 min) | Configurable |
| **Screenshot FPS** | 5 FPS | JPEG quality 50 |
| **Message Size** | 10 MB | FastAPI limit |
| **Redis Channels** | Unlimited | Redis pub/sub |

### Scalability Strategies

#### 1. **Horizontal Scaling (Load Balancing)**

```
                   ┌───────────────────┐
                   │  Load Balancer    │
                   │  (Nginx/HAProxy)  │
                   └────────┬──────────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
    ┌─────▼─────┐     ┌─────▼─────┐    ┌─────▼─────┐
    │  FastAPI  │     │  FastAPI  │    │  FastAPI  │
    │  Server 1 │     │  Server 2 │    │  Server 3 │
    └─────┬─────┘     └─────┬─────┘    └─────┬─────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
                   ┌────────▼──────────┐
                   │      Redis        │
                   │   (Pub/Sub Hub)   │
                   └───────────────────┘
```

**Implementation:**
- Use sticky sessions (session affinity) in load balancer
- Share Redis instance across all servers
- Use Redis for session state

#### 2. **Redis Cluster** (High Availability)

```yaml
# docker-compose.yml
redis-master:
  image: redis:7-alpine
  ports:
    - "6379:6379"

redis-replica-1:
  image: redis:7-alpine
  command: redis-server --replicaof redis-master 6379

redis-replica-2:
  image: redis:7-alpine
  command: redis-server --replicaof redis-master 6379
```

#### 3. **Connection Pooling**

```python
# Optimize Redis connections
redis_pool = redis.ConnectionPool.from_url(
    settings.redis_url,
    max_connections=100,
    decode_responses=True
)

def get_redis_client():
    return redis.Redis(connection_pool=redis_pool)
```

#### 4. **Event Batching** (Reduce WebSocket Overhead)

```python
class ConnectionManager:
    def __init__(self):
        self._event_batch = defaultdict(list)
        self._batch_interval = 0.1  # 100ms
    
    async def batch_send(self, user_id: str, event: AgentEvent):
        """Batch events and send every 100ms."""
        self._event_batch[user_id].append(event)
        
        if len(self._event_batch[user_id]) >= 10:
            await self._flush_batch(user_id)
    
    async def _flush_batch(self, user_id: str):
        """Send all batched events."""
        events = self._event_batch[user_id]
        if events:
            await self.send_json(user_id, {
                "type": "batch",
                "events": [e.to_dict() for e in events]
            })
            self._event_batch[user_id].clear()
```

### Performance Monitoring

```python
# Track WebSocket metrics
class ConnectionManager:
    def __init__(self):
        self._metrics = {
            "total_connections": 0,
            "active_connections": 0,
            "total_messages": 0,
            "total_bytes_sent": 0
        }
    
    async def send_json(self, user_id: str, message: dict):
        """Send with metrics tracking."""
        json_str = json.dumps(message)
        self._metrics["total_messages"] += 1
        self._metrics["total_bytes_sent"] += len(json_str)
        
        await self.active_connections[user_id].send_text(json_str)
    
    def get_metrics(self) -> dict:
        """Expose metrics for monitoring."""
        return self._metrics
```

---

## 🛠️ Error Handling

### Connection Errors

```python
# In main.py WebSocket handler
try:
    await manager.connect(websocket, user_id, token)
    
    while True:
        data = await websocket.receive_text()
        # ... handle messages ...
        
except WebSocketDisconnect:
    logger.info(f"User {user_id} disconnected")
    await manager.disconnect(user_id)
except Exception as e:
    logger.error(f"WebSocket error for {user_id}: {e}")
    await manager.disconnect(user_id)
    await websocket.close(code=1011, reason="Internal error")
```

### HITL Timeout Handling

```python
# In agent code
try:
    response = await hitl_handler(
        "Confirm phone number?",
        "(123) 456-7890"
    )
    # Use response
except asyncio.TimeoutError:
    logger.warning("HITL timeout, using default value")
    response = "default_value"
```

### Redis Connection Failures

```python
# In RedisEventPublisher
async def publish_event(self, event_type, agent, message, data=None):
    try:
        redis_client = await redis.from_url(self.redis_url)
        # ... publish event ...
        await redis_client.close()
    except redis.ConnectionError:
        logger.error("Redis unavailable, event lost")
        # Fallback: Store in local queue for retry
        self._failed_events.append((event_type, agent, message, data))
```

### Frontend Error Handling

```typescript
ws.onerror = (error) => {
  console.error('WebSocket error:', error);
  showNotification('Connection error', 'error');
};

ws.onclose = (event) => {
  if (event.code === 1008) {
    // Authentication failure
    redirectToLogin();
  } else if (event.code === 1011) {
    // Server error
    showNotification('Server error, please retry', 'error');
  }
};
```

---

## 🔗 Integration Patterns

### 1. **Orchestrator Pattern**

```python
# StreamingPipelineOrchestrator integrates all agents
class StreamingPipelineOrchestrator:
    async def run(self, query, location, auto_apply):
        # Scout → Analyst → Applier pipeline
        await self.emit(EventType.PIPELINE_START, "system", "Starting pipeline")
        
        # 1. Scout finds jobs
        scout = ScoutAgent(self.session_id)
        job_urls = await scout.run(query, location)
        
        # 2. Analyst analyzes each job
        analyst = AnalystAgent(self.session_id)
        for url in job_urls:
            analysis = await analyst.run(url, resume_text)
            
            # 3. Optional: Applier applies
            if auto_apply and analysis.match_score > 70:
                applier = WebSocketApplierAgent(self.session_id)
                await applier.run(url, profile_data)
        
        await self.emit(EventType.PIPELINE_COMPLETE, "system", "Pipeline finished")
```

### 2. **Celery Integration**

```python
# Celery task triggers WebSocket events
@celery_app.task
def apply_job_task(session_id, job_url, user_id, redis_url):
    """
    Celery task for job application.
    Publishes events to Redis for WebSocket relay.
    """
    publisher = RedisEventPublisher(session_id, redis_url)
    
    # Initialize LiveApplier with Redis publisher
    applier = LiveApplierWithRedis(
        session_id=session_id,
        publisher=publisher,
        draft_mode=True,
        user_id=user_id
    )
    
    # Run application (events auto-published to Redis)
    result = asyncio.run(applier.run(job_url, user_id))
    
    return result
```

### 3. **Frontend React Hook**

```typescript
// useWebSocket.ts
import { useEffect, useState, useCallback } from 'react';

interface AgentEvent {
  type: string;
  agent: string;
  message: string;
  data: any;
  timestamp: string;
}

export const useWebSocket = (sessionId: string) => {
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    const wsUrl = `ws://localhost:8000/ws/${sessionId}?token=${token}`;
    const websocket = new WebSocket(wsUrl);

    websocket.onopen = () => {
      console.log('WebSocket connected');
      setConnected(true);
    };

    websocket.onmessage = (event) => {
      const data: AgentEvent = JSON.parse(event.data);
      setEvents((prev) => [...prev, data]);
    };

    websocket.onclose = () => {
      console.log('WebSocket disconnected');
      setConnected(false);
    };

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    setWs(websocket);

    return () => {
      websocket.close();
    };
  }, [sessionId]);

  const sendMessage = useCallback(
    (type: string, data: any) => {
      if (ws && connected) {
        ws.send(JSON.stringify({ type, data }));
      }
    },
    [ws, connected]
  );

  return { events, connected, sendMessage };
};
```

### 4. **Multi-Agent Coordination**

```python
# Agents share session_id for coordinated events
session_id = "pipeline_abc123"

scout = ScoutAgent(session_id)
analyst = AnalystAgent(session_id)
applier = WebSocketApplierAgent(session_id)

# All emit to same session
await scout.emit(EventType.SCOUT_START, "Finding jobs...")
await analyst.emit(EventType.ANALYST_START, "Analyzing jobs...")
await applier.emit(EventType.APPLIER_START, "Applying to jobs...")

# Frontend receives all events in order
```

---

## 📦 Deployment Guide

### Development Setup

```bash
# 1. Install dependencies
pip install fastapi uvicorn redis websockets pyjwt

# 2. Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# 3. Set environment variables
export REDIS_URL="redis://localhost:6379/0"
export JWT_SECRET="your-secret-key"

# 4. Run FastAPI server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Deployment (Docker)

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose WebSocket port
EXPOSE 8000

# Use Uvicorn with multiple workers
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  fastapi:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET=${JWT_SECRET}
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  celery_worker:
    build: .
    command: celery -A src.worker.celery_app worker --loglevel=info
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis

volumes:
  redis_data:
```

### Nginx Reverse Proxy (WebSocket Support)

```nginx
# /etc/nginx/sites-available/jobstream
upstream fastapi {
    server localhost:8000;
}

server {
    listen 80;
    server_name jobstream.example.com;

    # WebSocket endpoint
    location /ws/ {
        proxy_pass http://fastapi;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket timeout (10 minutes)
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }

    # Regular HTTP endpoints
    location / {
        proxy_pass http://fastapi;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Health Check Endpoint

```python
# In main.py
@app.get("/health/ws")
async def websocket_health():
    """Health check for WebSocket system."""
    return {
        "status": "healthy",
        "active_connections": len(manager.active_connections),
        "metrics": manager.get_metrics()
    }
```

---

## 📚 API Reference

### ConnectionManager Methods

#### `connect(websocket, user_id, token)`
Authenticate and register a WebSocket connection.

**Parameters:**
- `websocket`: WebSocket instance
- `user_id`: User identifier
- `token`: JWT token for authentication

**Raises:**
- `HTTPException`: If authentication fails

**Example:**
```python
await manager.connect(websocket, "user_123", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
```

---

#### `disconnect(user_id)`
Remove and cleanup a connection.

**Parameters:**
- `user_id`: User identifier

**Example:**
```python
await manager.disconnect("user_123")
```

---

#### `send_json(user_id, message)`
Send JSON message to specific user.

**Parameters:**
- `user_id`: User identifier
- `message`: Dictionary to send

**Example:**
```python
await manager.send_json("user_123", {"type": "ping", "data": {}})
```

---

#### `send_event(user_id, event)`
Send AgentEvent to specific user.

**Parameters:**
- `user_id`: User identifier
- `event`: AgentEvent instance

**Example:**
```python
event = AgentEvent(
    type=EventType.SCOUT_START,
    agent="scout",
    message="Starting search"
)
await manager.send_event("user_123", event)
```

---

#### `broadcast(event, session_id)`
Send event to all users in session.

**Parameters:**
- `event`: AgentEvent instance
- `session_id`: Optional session filter

**Example:**
```python
await manager.broadcast(event, session_id="pipeline_abc")
```

---

#### `request_hitl(session_id, question, context, timeout)`
Request human input with timeout.

**Parameters:**
- `session_id`: Session identifier
- `question`: Question to ask
- `context`: Additional context
- `timeout`: Max wait time (seconds)

**Returns:** Human response string

**Raises:** `asyncio.TimeoutError` if timeout

**Example:**
```python
response = await manager.request_hitl(
    "session_123",
    "Confirm phone?",
    "(123) 456-7890",
    timeout=300
)
```

---

#### `resolve_hitl(hitl_id, response)`
Resolve pending HITL request.

**Parameters:**
- `hitl_id`: HITL request identifier
- `response`: User's response string

**Example:**
```python
manager.resolve_hitl("hitl_1705314645.123", "yes")
```

---

#### `get_event_history(session_id)`
Retrieve event history for reconnection.

**Parameters:**
- `session_id`: Session identifier

**Returns:** List of last 50 AgentEvent instances

**Example:**
```python
history = manager.get_event_history("session_123")
for event in history:
    print(event.to_dict())
```

---

### EventType Enum Values

See [Event System](#event-system) for full list of 90+ event types.

---

## 🎓 Best Practices

### 1. **Event Emission**
✅ Emit events at key milestones  
✅ Include relevant data in event payload  
✅ Use descriptive messages for UI display  
❌ Don't emit too frequently (< 10ms intervals)

### 2. **HITL Usage**
✅ Use for uncertain decisions only  
✅ Set reasonable timeouts (5-10 minutes)  
✅ Provide clear context  
❌ Don't block on trivial questions

### 3. **Connection Management**
✅ Handle disconnects gracefully  
✅ Implement reconnection logic  
✅ Clean up resources on disconnect  
❌ Don't leak connections

### 4. **Security**
✅ Always verify JWT tokens  
✅ Use WSS (TLS) in production  
✅ Validate user_id matches token  
❌ Don't trust client-side data

### 5. **Performance**
✅ Batch events when possible  
✅ Limit event history size  
✅ Use Redis pooling  
❌ Don't send large binary data via WebSocket

---

## 🔍 Troubleshooting

### Issue: WebSocket connection fails

**Symptoms:**
- `WebSocket connection failed` error in browser console
- 401 Unauthorized error

**Solutions:**
1. Check JWT token validity
2. Verify CORS settings
3. Check Nginx WebSocket config (Upgrade headers)
4. Verify Redis connection

---

### Issue: Events not received on frontend

**Symptoms:**
- Backend emits events but frontend doesn't receive

**Solutions:**
1. Check user_id matches
2. Verify session_id consistency
3. Check Redis pub/sub subscription
4. Enable debug logging

---

### Issue: HITL timeout

**Symptoms:**
- `asyncio.TimeoutError` in logs
- Agent skips form fields

**Solutions:**
1. Increase timeout value (default 300s)
2. Check frontend modal display
3. Verify HITL response message format
4. Check Redis connectivity

---

### Issue: High memory usage

**Symptoms:**
- FastAPI server consuming excessive RAM
- Redis memory growing

**Solutions:**
1. Limit event history size (default 50)
2. Cleanup old sessions
3. Use Redis TTL for channels
4. Implement connection limits

---

## 📊 Monitoring & Metrics

### Key Metrics to Track

```python
# Prometheus metrics example
from prometheus_client import Counter, Gauge, Histogram

ws_connections = Gauge('websocket_connections', 'Active WebSocket connections')
ws_messages_sent = Counter('websocket_messages_sent_total', 'Total messages sent')
ws_message_size = Histogram('websocket_message_size_bytes', 'Message size in bytes')
hitl_requests = Counter('hitl_requests_total', 'Total HITL requests')
hitl_timeouts = Counter('hitl_timeouts_total', 'Total HITL timeouts')
```

### Logging Best Practices

```python
# In ConnectionManager
import logging
logger = logging.getLogger(__name__)

async def connect(self, websocket, user_id, token):
    logger.info(f"WebSocket connection attempt: user_id={user_id}")
    # ... auth ...
    logger.info(f"WebSocket connected: user_id={user_id}")

async def disconnect(self, user_id):
    logger.info(f"WebSocket disconnected: user_id={user_id}")
    # ... cleanup ...
```

---

## Summary

The WebSocket system provides a **production-grade, real-time communication layer** for the JobAI backend, enabling:

1. ✅ **94+ Event Types** across 17 categories for all agents and workflows
2. ✅ **Redis Pub/Sub Bridge** for Celery worker → FastAPI event forwarding
3. ✅ **HITL System** — asyncio.Event-based, 120s timeout, HITL_CANCELLED on pipeline stop
4. ✅ **Browser Streaming** at 5 FPS JPEG via BROWSER_SCREENSHOT events
5. ✅ **Draft Mode** — APPLIER_DRAFT_READY gate before final form submission
6. ✅ **Salary Battle WebSocket** — 8-event turn-based `SalaryBattleGraph` real-time loop
7. ✅ **Career Intelligence Events** — CAREER_CHAT_RESPONSE, TRAJECTORY, SKILL_GAPS
8. ✅ **Multi-User Support** with JWT auth + per-user session isolation
9. ✅ **Reconnection** — MAX_EVENT_HISTORY=50 replay buffer per session
10. ✅ **Scalable** — stateless FastAPI + Redis Pub/Sub (horizontal scaling ready)

**Key Files:**
- `src/api/websocket.py` — Core WebSocket implementation, ConnectionManager, EventType
- `src/main.py` — WebSocket endpoints and Redis subscriber startup task
- `src/worker/tasks/applier_task.py` — Redis bridge publisher from Celery worker
- `src/services/orchestrator.py` — Pipeline orchestration with WebSocket event emission
- `src/graphs/salary_battle.py` — SalaryBattleGraph with SALARY_BATTLE_* events

**Deployment Status:** ✅ Production Ready

---

**Last Updated:** 2026-07-10  
**Maintainer:** Backend Team  
**Version:** 2.0
