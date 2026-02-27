"""
JobAI FastAPI Backend
API Gateway with WebSocket support for real-time updates
"""
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

import sys
import logging
import asyncio
import uvicorn
import time
from datetime import datetime
from fastapi import Request
from fastapi.responses import JSONResponse

# Import settings and middleware
from src.core.config import settings
from src.core.middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware,
    RequestSizeLimitMiddleware,
)
from src.core.rate_limit import ProductionRateLimitMiddleware

# Ensure logs directory exists
import os
os.makedirs("logs", exist_ok=True)

# Configure logging based on settings
log_handlers = [logging.StreamHandler()]
if not settings.is_development:
    log_handlers.append(logging.FileHandler("logs/app.log", mode="a", encoding="utf-8"))

logging.basicConfig(
    level=settings.get_log_level(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=log_handlers,
)
logger = logging.getLogger(__name__)

# Fix for Windows: browser-use requires ProactorEventLoop for subprocess support
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events with graceful draining."""
    # Debug Windows Event Loop
    if sys.platform == "win32":
        loop = asyncio.get_running_loop()
        logger.info(f"🪟 Windows Event Loop: {type(loop).__name__}")
        if not isinstance(loop, asyncio.ProactorEventLoop):
            logger.warning("⚠️ WARNING: Not using ProactorEventLoop! Subprocesses may fail.")

    logger.info(f"🚀 JobAI API Server starting... (Environment: {settings.environment})")
    logger.info(f"📊 Debug mode: {settings.debug}")
    logger.info(f"📈 Rate limiting: {'enabled' if settings.rate_limit_enabled else 'disabled'}")
    
    # ── Initialize DI Container ─────────────────────────────────────
    try:
        from src.core.container import container
        from src.core.event_bus import event_bus
        from src.core.guardrails import create_input_pipeline, create_chat_pipeline, create_output_pipeline
        from src.core.pii_detector import pii_detector
        
        # Register core services in DI container
        container.register_singleton("event_bus", lambda: event_bus)
        container.register_singleton("pii_detector", lambda: pii_detector)
        container.register_singleton("input_guardrails", create_input_pipeline)
        container.register_singleton("chat_guardrails", create_chat_pipeline)
        container.register_singleton("output_guardrails", create_output_pipeline)
        
        # Phase 1: Agent Intelligence & Observability
        from src.core.agent_memory import agent_memory
        from src.core.cost_tracker import cost_tracker
        from src.core.structured_logger import structured_logger
        from src.core.retry_budget import retry_budget
        from src.core.agent_protocol import agent_protocol
        
        container.register_instance("agent_memory", agent_memory)
        container.register_instance("cost_tracker", cost_tracker)
        container.register_instance("structured_logger", structured_logger)
        container.register_instance("retry_budget", retry_budget)
        container.register_instance("agent_protocol", agent_protocol)
        
        logger.info("📦 DI Container initialized with core services")
        logger.info("🧠 Agent Intelligence Layer registered (memory, costs, protocol)")
        
        # Emit startup event
        await event_bus.emit("system:startup", {
            "environment": settings.environment,
            "timestamp": datetime.now().isoformat(),
        })
        logger.info("🔌 Event Bus initialized")
    except Exception as e:
        logger.warning(f"⚠️ DI/EventBus init failed (non-fatal): {e}")
    
    # Initialize Telemetry (Observability) - optional
    try:
        from src.core.telemetry import setup_telemetry
        setup_telemetry()
        logger.info("📡 Telemetry initialized")
    except ImportError as e:
        logger.warning(f"⚠️ Telemetry disabled (missing dependency): {e}")
    except Exception as e:
        logger.warning(f"⚠️ Telemetry initialization failed: {e}")
    
    yield

    # ── Graceful Shutdown ──────────────────────────────────────
    logger.info("🛑 JobAI API Server shutting down — draining connections...")

    # 0. Emit shutdown event via event bus
    try:
        from src.core.event_bus import event_bus
        await event_bus.emit("system:shutdown", {
            "timestamp": datetime.now().isoformat(),
        })
    except Exception:
        pass

    # 1. Close all active WebSocket connections gracefully
    try:
        from src.api.websocket import manager as ws_manager
        active = list(ws_manager.active_connections.keys())
        for sid in active:
            try:
                ws = ws_manager.active_connections.get(sid)
                if ws:
                    await ws.close(code=1001, reason="Server shutting down")
            except Exception:
                pass
            ws_manager.disconnect(sid)
        logger.info(f"  Closed {len(active)} WebSocket connection(s)")
    except Exception as e:
        logger.warning(f"  WebSocket cleanup error: {e}")

    # 2. Close Redis connection pool
    try:
        from src.core.cache import cache
        if cache.redis:
            await cache.redis.close()
            logger.info("  Redis cache pool closed")
    except Exception as e:
        logger.warning(f"  Redis cleanup error: {e}")

    # 3. Close rate limiter Redis connection
    try:
        from src.core.rate_limiter import limiter
        if hasattr(limiter, 'redis'):
            await limiter.redis.close()
            logger.info("  Rate limiter Redis closed")
    except Exception:
        pass

    # 4. Reset DI container
    try:
        from src.core.container import container
        container.reset()
        logger.info("  DI container reset")
    except Exception:
        pass

    logger.info("✅ Graceful shutdown complete")


app = FastAPI(
    title="JobAI API",
    description="Backend API for JobAI Career Command Center",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,  # Disable docs in production
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url="/openapi.json" if settings.is_development else None,
)

# Import custom exceptions
from src.core.exceptions import JobAIException, ValidationError, NotFoundError
from fastapi.exceptions import HTTPException as FastAPIHTTPException

def _get_cors_headers(request: Request) -> dict:
    """Get CORS headers for error responses based on request origin."""
    origin = request.headers.get("origin", "")
    allowed_origins = settings.get_cors_origins()
    
    # Check if origin is allowed
    if origin in allowed_origins:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    return {}

# HTTP Exception Handler (401, 403, 404, etc.)
@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    logger.warning(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": True, "code": f"HTTP_{exc.status_code}", "message": str(exc.detail)},
        headers=_get_cors_headers(request),
    )

# Custom Exception Handler for JobAI errors
@app.exception_handler(JobAIException)
async def jobai_exception_handler(request: Request, exc: JobAIException):
    logger.warning(f"JobAI error [{exc.code}]: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
        headers=_get_cors_headers(request),
    )

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error: {str(exc)}", exc_info=True)
    
    cors_headers = _get_cors_headers(request)
    
    # Hide error details in production
    if settings.is_production:
        return JSONResponse(
            status_code=500,
            content={"error": True, "code": "INTERNAL_ERROR", "message": "Internal Server Error"},
            headers=cors_headers,
        )
    
    return JSONResponse(
        status_code=500,
        content={"error": True, "code": "INTERNAL_ERROR", "message": "Internal Server Error", "detail": str(exc)},
        headers=cors_headers,
    )

# ============================================
# Middleware Stack (order matters - last added = first executed)
# ============================================

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Request size limit middleware
app.add_middleware(RequestSizeLimitMiddleware, max_size=settings.max_request_size)

# Rate limiting middleware (conditional)
if settings.rate_limit_enabled:
    # Use Redis-based rate limiting in production
    redis_url = getattr(settings, 'redis_url', None)
    if settings.is_production and redis_url:
        app.add_middleware(
            ProductionRateLimitMiddleware,
            redis_url=redis_url,
            requests_per_minute=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_period,
        )
    else:
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_period,
        )

# CORS configuration for frontend (uses settings)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics (must be added AFTER all other middleware)
try:
    from src.core.metrics import setup_metrics
    setup_metrics(app)
except Exception as e:
    logger.warning(f"⚠️ Prometheus metrics disabled: {e}")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "JobAI API v2.0 - Browser-Use Style"}


@app.get("/api/health")
async def health_check():
    """Detailed health check."""
    # Include DI + Event Bus status
    di_status = {}
    try:
        from src.core.container import container
        di_status = container.health_check()
    except Exception:
        di_status = {"status": "unavailable"}
    
    eb_status = {}
    try:
        from src.core.event_bus import event_bus
        eb_status = event_bus.stats()
    except Exception:
        eb_status = {"status": "unavailable"}
    
    return {
        "status": "healthy",
        "version": "2.0.0",
        "environment": settings.environment,
        "features": {
            "websocket": True,
            "browser_streaming": True,
            "hitl": True,
            "langgraph": True,
            "guardrails": True,
            "event_bus": True,
        },
        "di_container": di_status,
        "event_bus": eb_status,
    }


@app.get("/api/ready")
async def readiness_check():
    """Kubernetes readiness probe."""
    # Add actual dependency checks here (database, external services)
    return {"status": "ready"}


@app.get("/api/live")
async def liveness_check():
    """Kubernetes liveness probe."""
    return {"status": "alive"}


# ============================================
# WebSocket Endpoint for Real-Time Updates
# ============================================

# ============================================
# WebSocket Endpoint for Real-Time Updates
# ============================================

from src.api.websocket import manager, AgentEvent, EventType

# Redis pub/sub subscriber for worker events
redis_subscriber_task = None

async def subscribe_to_worker_events(session_id: str, websocket: WebSocket):
    """
    Subscribe to Redis pub/sub channel for worker events.
    
    This bridges Celery worker events to WebSocket clients.
    Channel: jobai:events:{session_id}
    """
    if not settings.redis_url:
        return None
    
    redis_client = None
    pubsub = None
    channel = f"jobai:events:{session_id}"
    
    try:
        import redis.asyncio as aioredis
        import json
        
        redis_client = aioredis.from_url(settings.redis_url)
        pubsub = redis_client.pubsub()
        
        await pubsub.subscribe(channel)
        
        logger.info(f"Subscribed to Redis channel: {channel}")
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    event_data = json.loads(message["data"])
                    await websocket.send_json(event_data)
                except Exception as e:
                    logger.warning(f"Failed to forward worker event: {e}")
                    
    except Exception as e:
        logger.warning(f"Redis subscription failed (Redis may not be running): {e}")
    finally:
        try:
            if pubsub:
                await pubsub.unsubscribe(channel)
            if redis_client:
                await redis_client.close()
        except Exception:
            pass  # Ignore cleanup errors


async def handle_websocket_connection(websocket: WebSocket, session_id: str, user_id: str = None):
    """
    Shared WebSocket handler logic.
    
    Args:
        websocket: The WebSocket connection
        session_id: Session identifier for the connection
        user_id: Optional authenticated user ID for multi-user support
    """
    # CRITICAL: Accept the connection first
    await websocket.accept()
    logger.info(f"WebSocket connection accepted for session: {session_id}, user: {user_id}")
    
    await manager.connect(websocket, session_id, user_id=user_id)
    
    # Track active services
    applier_service = None
    applier_task = None
    redis_sub_task = None
    heartbeat_task = None
    
    # Start heartbeat to keep connection alive
    async def heartbeat():
        try:
            while True:
                await asyncio.sleep(30)  # Send ping every 30 seconds
                try:
                    await websocket.send_json({"type": "ping", "timestamp": int(time.time())})
                except Exception as e:
                    logger.warning(f"Heartbeat failed for {session_id}: {e}")
                    break
        except asyncio.CancelledError:
            pass
    
    heartbeat_task = asyncio.create_task(heartbeat())
    
    # Start Redis subscriber for worker events
    if settings.redis_url:
        redis_sub_task = asyncio.create_task(
            subscribe_to_worker_events(session_id, websocket)
        )
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_json()
            
            # Handle different message types
            msg_type = data.get("type", "")
            
            # SECURITY: Always use server-verified user_id from JWT token
            # Never trust user_id from client message payload to prevent spoofing
            msg_user_id = user_id
            
            if msg_type == "start_pipeline":
                # Start the pipeline in background
                query = data.get("query", "Software Engineer")
                location = data.get("location", "Remote")
                min_score = data.get("min_match_score", 70)
                auto_apply = data.get("auto_apply", False)
                
                # Optional agents
                use_company_research = data.get("use_company_research", False)
                use_resume_tailoring = data.get("use_resume_tailoring", False)
                use_cover_letter = data.get("use_cover_letter", False)
                
                from src.services.orchestrator import StreamingPipelineOrchestrator
                orchestrator = StreamingPipelineOrchestrator(session_id, user_id=msg_user_id)
                
                # Run in background task
                asyncio.create_task(
                    orchestrator.run(
                        query, location, min_score, auto_apply,
                        use_company_research, use_resume_tailoring, use_cover_letter
                    )
                )
                
            elif msg_type == "stop_pipeline":
                # Signal to stop (would need cancellation token in real impl)
                await manager.send_event(session_id, AgentEvent(
                    type=EventType.PIPELINE_COMPLETE,
                    agent="system",
                    message="Pipeline stopped by user"
                ))
                
            elif msg_type in ("hitl_response", "hitl:response"):
                # Handle HITL response
                payload = data.get("data") or data
                hitl_id = payload.get("hitl_id")
                response = payload.get("response", "")
                if applier_service:
                    applier_service.resolve_hitl(hitl_id, response)
                else:
                    manager.resolve_hitl(hitl_id, response)
                
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "start_apply":
                url = data.get("url", "")
                draft_mode = data.get("draft_mode", True)  # Default ON for trust
                use_celery = data.get("use_celery", False)  # Option to use worker
                
                if not url:
                    await manager.send_event(session_id, AgentEvent(
                        type=EventType.PIPELINE_ERROR,
                        agent="system",
                        message="No URL provided"
                    ))
                    continue
                
                if use_celery and settings.redis_url:
                    # Queue task in Celery worker
                    try:
                        from src.worker.tasks.applier_task import apply_to_job
                        
                        task = apply_to_job.delay(
                            job_url=url,
                            session_id=session_id,
                            draft_mode=draft_mode,
                            redis_url=settings.redis_url,
                        )
                        
                        await manager.send_event(session_id, AgentEvent(
                            type=EventType.TASK_QUEUED,
                            agent="system",
                            message=f"Task queued: {task.id}",
                            data={"task_id": task.id, "url": url}
                        ))
                        
                    except Exception as e:
                        logger.error(f"Failed to queue Celery task: {e}")
                        await manager.send_event(session_id, AgentEvent(
                            type=EventType.PIPELINE_ERROR,
                            agent="system",
                            message=f"Failed to queue task: {str(e)}"
                        ))
                else:
                    # Run directly in API server (original behavior)
                    from src.services.live_applier import LiveApplierService
                    applier_service = LiveApplierService(session_id, draft_mode=draft_mode, user_id=msg_user_id)
                    
                    # Run in background task
                    applier_task = asyncio.create_task(applier_service.run(url))
                
            elif msg_type == "applier:start":
                # Start live applier
                data_payload = data.get("data", {})
                url = data_payload.get("url", "")
                config = data_payload.get("config", {})
                session_id_from_msg = data_payload.get("session_id", session_id)
                
                if url and not applier_service:
                    from src.services.live_applier import LiveApplierService
                    applier_service = LiveApplierService(
                        session_id_from_msg, 
                        draft_mode=config.get("draft_mode", True), 
                        user_id=msg_user_id
                    )
                    
                    # Run in background task
                    applier_task = asyncio.create_task(applier_service.run(url))
                    
                    await manager.send_event(session_id, AgentEvent(
                        type=EventType.APPLIER_START,
                        agent="applier",
                        message=f"Starting applier for {url}",
                        data={"url": url, "config": config}
                    ))
                    
            elif msg_type == "applier:stop":
                if applier_service:
                    applier_service.stop()
                if applier_task:
                    applier_task.cancel()
                await manager.send_event(session_id, AgentEvent(
                    type=EventType.APPLIER_COMPLETE,
                    agent="applier",
                    message="Applier stopped by user"
                ))
                applier_service = None
                applier_task = None
            
            elif msg_type == "browser:screenshot":
                # Request screenshot
                if applier_service:
                    await applier_service.take_screenshot()
            
            elif msg_type == "chat:message":
                # Handle chat message
                data_payload = data.get("data") or data
                message = data_payload.get("message", "")
                sender = data_payload.get("sender", "user")
                
                if message:
                    # Broadcast message to all connected clients
                    await manager.send_event(session_id, AgentEvent(
                        type=EventType.CHAT_MESSAGE,
                        agent=sender,
                        message=message,
                        data=data_payload
                    ))
                    
                    # If there's an HITL request pending, resolve it
                    if sender == "user" and applier_service:
                        # Check if there are pending HITL requests
                        for hitl_id, future in list(manager.hitl_callbacks.items()):
                            if not future.done():
                                manager.resolve_hitl(hitl_id, message)
                                break
                
            elif msg_type == "interaction":
                # Handle remote control interaction (click, type, etc.)
                if applier_service:
                    await applier_service.perform_interaction(data)
            
            elif msg_type == "chat":
                # User sent a chat message - forward to agent if HITL pending
                message = data.get("message", "")
                if message:
                    await manager.send_event(session_id, AgentEvent(
                        type=EventType.CHAT_MESSAGE,
                        agent="user",
                        message=message
                    ))

            elif msg_type == "stop":
                 if applier_service:
                    applier_service.stop()
                 if applier_task:
                    applier_task.cancel()
                 await manager.send_event(session_id, AgentEvent(
                    type=EventType.PIPELINE_COMPLETE,
                    agent="system",
                    message="Process stopped by user"
                 ))
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session: {session_id}, user: {user_id}")
        if applier_service:
            applier_service.stop()
            try:
                await applier_service.cleanup()
            except Exception:
                pass
        if redis_sub_task:
            redis_sub_task.cancel()
        if heartbeat_task:
            heartbeat_task.cancel()
        if applier_task:
            applier_task.cancel()
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        if applier_service:
            applier_service.stop()
            try:
                await applier_service.cleanup()
            except Exception:
                pass
        if redis_sub_task:
            redis_sub_task.cancel()
        if heartbeat_task:
            heartbeat_task.cancel()
        if applier_task:
            applier_task.cancel()
        manager.disconnect(session_id)
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, token: Optional[str] = None):
    """WebSocket with optional JWT authentication for multi-user support."""
    user_id = None
    if token:
        try:
            from src.core.auth import verify_token
            payload = verify_token(token)
            user_id = payload.get("sub")
            logger.info(f"WebSocket auth OK for user: {user_id}, session: {session_id}")
        except Exception as e:
            logger.warning(f"WebSocket auth failed for session {session_id}: {e}")
            # Accept and immediately close with auth error
            await websocket.accept()
            await websocket.send_json({"type": "error", "message": "Authentication failed"})
            await websocket.close(code=4001, reason="Authentication failed")
            return
    
    await handle_websocket_connection(websocket, session_id, user_id=user_id)


@app.websocket("/ws/applier")
async def applier_websocket_endpoint(websocket: WebSocket, token: Optional[str] = None):
    """Applier WebSocket with optional JWT authentication for multi-user support."""
    session_id = f"applier_{int(time.time())}_{id(websocket)}"
    user_id = None
    if token:
        try:
            from src.core.auth import verify_token
            payload = verify_token(token)
            user_id = payload.get("sub")
            logger.info(f"Applier WebSocket auth OK for user: {user_id}, session: {session_id}")
        except Exception as e:
            logger.warning(f"Applier WebSocket auth failed for session {session_id}: {e}")
            # Accept and immediately close with auth error
            await websocket.accept()
            await websocket.send_json({"type": "error", "message": "Authentication failed"})
            await websocket.close(code=4001, reason="Authentication failed")
            return
    
    await handle_websocket_connection(websocket, session_id, user_id=user_id)


# ============================================
# REST API Routes
# ============================================

# Versioned API (canonical — use /api/v1/...)
from src.api.v1 import v1_router
app.include_router(v1_router)

# Legacy /api/ routes (backward compatibility — will be removed in v3)
from src.api.routes import jobs, agents, chat, pipeline

app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["Pipeline"])

# New Agent Routes
from src.api.routes import company, interview, salary, resume, cover_letter
app.include_router(company.router, prefix="/api/company", tags=["Company"])
app.include_router(interview.router, prefix="/api/interview", tags=["Interview"])
app.include_router(salary.router, prefix="/api/salary", tags=["Salary"])
app.include_router(resume.router, prefix="/api/resume", tags=["Resume"])
app.include_router(cover_letter.router, prefix="/api/cover-letter", tags=["Cover Letter"])

from src.api.routes import tracker
app.include_router(tracker.router, prefix="/api/tracker", tags=["Tracker"])

# NetworkAI Routes - LinkedIn X-Ray Search for Referrals
from src.api.routes import network
app.include_router(network.router, prefix="/api", tags=["NetworkAI"])

# User Profile Routes - Multi-tenant profile management
from src.api.routes import user
app.include_router(user.router, prefix="/api", tags=["User Profile"])

# RAG Routes - Document Context
# RAG Routes - Document Context
from src.api.routes import rag
app.include_router(rag.router, prefix="/api/rag", tags=["RAG"])

# Feedback & Analytics (Phase 1 — Intelligence Layer)
from src.api.routes import feedback, analytics
app.include_router(feedback.router, prefix="/api/feedback", tags=["Feedback"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])


# ============================================
# Task Status Endpoint (Celery polling fallback)
# ============================================

from src.api.schemas import LLMUsageResponse

@app.get("/api/v1/admin/llm-usage", tags=["Admin"], response_model=LLMUsageResponse)
@app.get("/api/admin/llm-usage", tags=["Admin"], include_in_schema=False)
async def get_llm_usage():
    """Return aggregated LLM token usage and estimated cost."""
    from src.core.llm_tracker import get_usage_tracker
    tracker = get_usage_tracker()
    return {
        "summary": tracker.get_summary(),
        "per_agent": tracker.get_per_agent_summary(),
    }


@app.get("/api/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """
    Get the status of a Celery task.
    
    This is a polling fallback if WebSocket is unavailable.
    Prefer WebSocket for real-time updates.
    """
    if not settings.redis_url:
        return {"error": "Task queue not configured", "task_id": task_id}
    
    try:
        from celery.result import AsyncResult
        from src.worker.celery_app import celery_app
        
        result = AsyncResult(task_id, app=celery_app)
        
        return {
            "task_id": task_id,
            "status": result.status,
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else None,
            "result": result.result if result.ready() and result.successful() else None,
            "error": str(result.result) if result.ready() and result.failed() else None,
        }
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        return {"error": str(e), "task_id": task_id}


@app.post("/api/tasks/{task_id}/revoke")
async def revoke_task(task_id: str, terminate: bool = False):
    """
    Cancel a running or pending Celery task.
    
    Args:
        task_id: The task ID to revoke
        terminate: If True, forcefully terminate running task
    """
    if not settings.redis_url:
        return {"error": "Task queue not configured", "task_id": task_id}
    
    try:
        from src.worker.celery_app import celery_app
        
        celery_app.control.revoke(task_id, terminate=terminate)
        
        return {
            "task_id": task_id,
            "revoked": True,
            "terminated": terminate,
        }
    except Exception as e:
        logger.error(f"Failed to revoke task: {e}")
        return {"error": str(e), "task_id": task_id}



if __name__ == "__main__":
    # FORCE Windows Proactor Event Loop for subprocess support (browser-use)
    # This is critical on Windows, especially with Uvicorn
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            logger.info("🔧 Enforced WindowsProactorEventLoopPolicy")
        except AttributeError:
            logger.warning("⚠️ Could not set WindowsProactorEventLoopPolicy")

    # Disable reload to ensure ProactorEventLoop is used correctly on Windows
    # Uvicorn with reload often forces SelectorEventLoop
    logger.info(f"Starting Uvicorn (environment: {settings.environment})...")
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development and sys.platform != "win32",
        log_level=settings.log_level.lower(),
    )
