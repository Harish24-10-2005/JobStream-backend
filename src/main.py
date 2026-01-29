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
    """Handle startup and shutdown events."""
    # Debug Windows Event Loop
    if sys.platform == "win32":
        loop = asyncio.get_running_loop()
        logger.info(f"🪟 Windows Event Loop: {type(loop).__name__}")
        if not isinstance(loop, asyncio.ProactorEventLoop):
            logger.warning("⚠️ WARNING: Not using ProactorEventLoop! Subprocesses may fail.")

    logger.info(f"🚀 JobAI API Server starting... (Environment: {settings.environment})")
    logger.info(f"📊 Debug mode: {settings.debug}")
    logger.info(f"� Rate limiting: {'enabled' if settings.rate_limit_enabled else 'disabled'}")
    
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
    logger.info("🛑 JobAI API Server shutting down...")


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


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "JobAI API v2.0 - Browser-Use Style"}


@app.get("/api/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "environment": settings.environment,
        "features": {
            "websocket": True,
            "browser_streaming": True,
            "hitl": True,
        },
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
    await manager.connect(websocket, session_id)
    
    # Track active services
    applier_service = None
    applier_task = None
    redis_sub_task = None
    
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
            
            # Allow client to pass user_id in message for authentication
            msg_user_id = data.get("user_id") or user_id
            
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
                await manager.broadcast(AgentEvent(
                    type=EventType.PIPELINE_COMPLETE,
                    agent="system",
                    message="Pipeline stopped by user"
                ))
                
            elif msg_type == "hitl_response":
                # Handle HITL response
                hitl_id = data.get("hitl_id")
                response = data.get("response", "")
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
                        from worker.tasks.applier_task import apply_to_job
                        
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
                
            elif msg_type == "interaction":
                # Handle remote control interaction (click, type, etc.)
                if applier_service:
                    await applier_service.perform_interaction(data)
            
            elif msg_type == "chat":
                # User sent a chat message - forward to agent if HITL pending
                message = data.get("message", "")
                if message:
                    await manager.broadcast(AgentEvent(
                        type=EventType.CHAT_MESSAGE,
                        agent="user",
                        message=message
                    ))

            elif msg_type == "stop":
                 if applier_service:
                    applier_service.stop()
                 if applier_task:
                    applier_task.cancel()
                 await manager.broadcast(AgentEvent(
                    type=EventType.PIPELINE_COMPLETE,
                    agent="system",
                    message="Process stopped by user"
                 ))
                
    except WebSocketDisconnect:
        if applier_service:
             applier_service.stop()
        if redis_sub_task:
            redis_sub_task.cancel()
        manager.disconnect(session_id)


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, token: Optional[str] = None):
    """WebSocket with optional JWT authentication for multi-user support."""
    user_id = None
    if token:
        try:
            from src.core.auth import verify_token
            payload = verify_token(token)
            user_id = payload.get("sub")
            logger.info(f"WebSocket authenticated for user: {user_id}")
        except Exception as e:
            logger.warning(f"WebSocket auth failed: {e}")
    await handle_websocket_connection(websocket, session_id, user_id=user_id)


@app.websocket("/ws/applier/{session_id}")
async def applier_websocket_endpoint(websocket: WebSocket, session_id: str, token: Optional[str] = None):
    """Applier WebSocket with optional JWT authentication for multi-user support."""
    user_id = None
    if token:
        try:
            from src.core.auth import verify_token
            payload = verify_token(token)
            user_id = payload.get("sub")
            logger.info(f"Applier WebSocket authenticated for user: {user_id}")
        except Exception as e:
            logger.warning(f"Applier WebSocket auth failed: {e}")
    await handle_websocket_connection(websocket, session_id, user_id=user_id)


# ============================================
# REST API Routes
# ============================================

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


# ============================================
# Task Status Endpoint (Celery polling fallback)
# ============================================

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
        from worker.celery_app import celery_app
        
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
        from worker.celery_app import celery_app
        
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
