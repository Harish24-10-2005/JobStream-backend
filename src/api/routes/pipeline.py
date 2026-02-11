"""
Pipeline API Routes
"""
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel
from typing import Optional, Dict
import asyncio
import json
import logging
import time

from src.api.websocket import manager, AgentEvent, EventType
from src.core.auth import get_current_user, AuthUser
from src.api.schemas import PipelineStatusResponse, PipelineStartResponse, PipelineActionResponse, HITLResponse

router = APIRouter()
logger = logging.getLogger(__name__)


class PipelineConfig(BaseModel):
    query: str
    location: str = "Remote"
    auto_apply: bool = True
    min_match_score: int = 70
    session_id: Optional[str] = None


class PipelineStatus(BaseModel):
    running: bool
    current_agent: Optional[str] = None
    progress: int
    jobs_found: int
    jobs_applied: int


# Try to import Redis, but provide fallback
try:
    from src.core.redis_client import get_redis_client
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# In-memory fallback store (for development without Redis)
_memory_store: Dict[str, dict] = {}

def _get_default_state() -> dict:
    """Return default pipeline state."""
    return {
        "running": False,
        "current_agent": None,
        "progress": 0,
        "jobs_found": 0,
        "jobs_applied": 0
    }

async def _check_redis_connection() -> bool:
    """Check if Redis is available."""
    if not REDIS_AVAILABLE:
        return False
    try:
        redis = get_redis_client()
        await redis.ping()
        return True
    except Exception:
        return False

async def get_pipeline_state(user_id: str) -> dict:
    """Get or initialize state for a user. Uses Redis if available, otherwise in-memory."""
    
    # Try Redis first
    if REDIS_AVAILABLE:
        try:
            redis = get_redis_client()
            key = f"pipeline:{user_id}:state"
            
            # Get all fields
            state = await redis.hgetall(key)
            
            if not state:
                # Initialize default state in Redis
                initial_state = {
                    "running": "0",
                    "current_agent": "None",
                    "progress": "0",
                    "jobs_found": "0",
                    "jobs_applied": "0"
                }
                await redis.hset(key, mapping=initial_state)
                await redis.expire(key, 86400)
                return _get_default_state()
                
            # Convert types (Redis stores everything as strings)
            return {
                "running": state.get("running", "0") == "1",
                "current_agent": None if state.get("current_agent") == "None" else state.get("current_agent"),
                "progress": int(state.get("progress", 0)),
                "jobs_found": int(state.get("jobs_found", 0)),
                "jobs_applied": int(state.get("jobs_applied", 0))
            }
        except Exception as e:
            logger.warning(f"Redis Error (falling back to memory): {e}")
            # Fall through to memory store
    
    # In-memory fallback
    if user_id not in _memory_store:
        _memory_store[user_id] = _get_default_state()
    return _memory_store[user_id].copy()

async def update_pipeline_state(user_id: str, updates: dict):
    """Update specific fields in state. Uses Redis if available, otherwise in-memory."""
    
    # Try Redis first
    if REDIS_AVAILABLE:
        try:
            redis = get_redis_client()
            key = f"pipeline:{user_id}:state"
            
            # Convert booleans to 1/0 and None to literal "None"
            redis_updates = {}
            for k, v in updates.items():
                if isinstance(v, bool):
                    redis_updates[k] = "1" if v else "0"
                elif v is None:
                    redis_updates[k] = "None"
                else:
                    redis_updates[k] = str(v)
                    
            await redis.hset(key, mapping=redis_updates)
            return
        except Exception as e:
            logger.warning(f"Redis Update Error (falling back to memory): {e}")
            # Fall through to memory store
    
    # In-memory fallback
    if user_id not in _memory_store:
        _memory_store[user_id] = _get_default_state()
    _memory_store[user_id].update(updates)


@router.get("/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(user: AuthUser = Depends(get_current_user)):
    """
    Get current pipeline status for the authenticated user.
    """
    return await get_pipeline_state(user.id)


# Store active orchestrators for stop functionality
_active_orchestrators: Dict[str, "StreamingPipelineOrchestrator"] = {}


async def _run_pipeline_task(user_id: str, session_id: str, config: dict):
    """Background task that runs the pipeline orchestrator."""
    from src.services.orchestrator import StreamingPipelineOrchestrator
    
    try:
        orchestrator = StreamingPipelineOrchestrator(
            session_id=session_id,
            user_id=user_id
        )
        _active_orchestrators[user_id] = orchestrator
        
        await orchestrator.run(
            query=config["query"],
            location=config["location"],
            min_match_score=config["min_match_score"],
            auto_apply=config["auto_apply"],
            use_resume_tailoring=True,
            use_cover_letter=True
        )
    except Exception as e:
        logger.error(f"Pipeline error for user {user_id}: {e}")
    finally:
        # Update state when pipeline finishes
        await update_pipeline_state(user_id, {
            "running": False,
            "current_agent": None
        })
        if user_id in _active_orchestrators:
            del _active_orchestrators[user_id]


from fastapi import BackgroundTasks

@router.post("/start", response_model=PipelineStartResponse)
async def start_pipeline(
    config: PipelineConfig, 
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user)
):
    """
    Start the agentic pipeline for the authenticated user.
    Runs Scout → Analyst → Resume → Cover Letter → Applier in background.
    """
    state = await get_pipeline_state(user.id)
    
    if state["running"]:
        raise HTTPException(status_code=400, detail="Pipeline is already running")
    
    await update_pipeline_state(user.id, {
        "running": True,
        "current_agent": "scout",
        "progress": 0,
        "jobs_found": 0,
        "jobs_applied": 0
    })
    
    # Generate session ID for WebSocket events
    session_id = config.session_id or f"pipeline_{user.id}_{int(time.time() * 1000)}"
    
    # Add pipeline task to background
    background_tasks.add_task(
        _run_pipeline_task,
        user.id,
        session_id,
        config.model_dump()
    )
    
    return {
        "status": "started",
        "message": "Pipeline started successfully",
        "session_id": session_id,
        "config": config.model_dump(),
    }


@router.post("/stop", response_model=PipelineActionResponse)
async def stop_pipeline(user: AuthUser = Depends(get_current_user)):
    """
    Stop the running pipeline.
    """
    # Stop the active orchestrator if exists
    if user.id in _active_orchestrators:
        _active_orchestrators[user.id].stop()
        del _active_orchestrators[user.id]
    
    await update_pipeline_state(user.id, {
        "running": False,
        "current_agent": None
    })
    
    return {
        "status": "stopped",
        "message": "Pipeline stopped",
    }


@router.post("/pause", response_model=PipelineActionResponse)
async def pause_pipeline(user: AuthUser = Depends(get_current_user)):
    """
    Pause the running pipeline.
    """
    state = await get_pipeline_state(user.id)
    
    if not state["running"]:
        raise HTTPException(status_code=400, detail="Pipeline is not running")
    
    await update_pipeline_state(user.id, {
        "running": False
    })
    
    return {
        "status": "paused",
        "message": "Pipeline paused",
    }



@router.websocket("/ws/{session_id}")
async def pipeline_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time pipeline updates.
    Secured via Token in Query Param.
    """
    # Accept the WebSocket connection FIRST
    await websocket.accept()
    logger.info(f"Pipeline WebSocket connection accepted for session: {session_id}")
    
    # Extract and verify token
    token = websocket.query_params.get("token")
    user_id = None
    if token:
        try:
            from src.core.auth import verify_token
            payload = verify_token(token)
            user_id = payload.get("sub")
            logger.info(f"Pipeline WS authenticated user: {user_id}")
        except Exception as e:
            logger.warning(f"Pipeline WS auth failed for session {session_id}: {e}")
            # Allow connection but without user binding (for backward compat)
    
    # Register with connection manager
    await manager.connect(websocket, session_id, token, user_id=user_id)
    
    try:
        while True:
            # Listen for client messages
            data = await websocket.receive_text()
            logger.debug(f"Pipeline WS received from {session_id}: {data[:100]}")
            
            # Handle ping/pong (both raw text and JSON format)
            try:
                import json
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    continue
                if msg.get("type") in ("hitl_response", "hitl:response"):
                    hitl_id = msg.get("hitl_id")
                    response = msg.get("response", "")
                    if hitl_id:
                        manager.resolve_hitl(hitl_id, response)
                    continue
                if msg.get("type") == "chat:message":
                    # Broadcast chat message to session
                    payload = msg.get("data") or msg
                    message = payload.get("message", "")
                    sender = payload.get("sender", "user")
                    if message:
                        await manager.send_event(session_id, AgentEvent(
                            type=EventType.CHAT_MESSAGE,
                            agent=sender,
                            message=message,
                            data=payload
                        ))
                    continue
            except json.JSONDecodeError:
                pass
            
            if data == "ping":
                await websocket.send_text("pong")
                
    except WebSocketDisconnect:
        logger.info(f"Pipeline WebSocket disconnected: {session_id}")
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"Pipeline WebSocket error for {session_id}: {e}")
        manager.disconnect(session_id)


@router.post("/hitl/respond", response_model=HITLResponse)
async def respond_to_hitl(response: dict, user: AuthUser = Depends(get_current_user)):
    """
    Respond to a Human-in-the-Loop prompt.
    """
    hitl_id = response.get("hitl_id")
    answer = response.get("response", "")
    
    if not hitl_id:
        raise HTTPException(status_code=400, detail="hitl_id is required")
    
    resolved = manager.resolve_hitl(hitl_id, answer)
    if not resolved:
        raise HTTPException(status_code=404, detail="HITL prompt not found or already resolved")
    
    return {
        "status": "resolved",
        "hitl_id": hitl_id,
        "message": "Response recorded, pipeline continuing",
    }
