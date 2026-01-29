"""
Pipeline API Routes
"""
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel
from typing import Optional, Dict
import asyncio
import json

from src.api.routes.jobs import get_current_user
from src.core.auth import AuthUser

router = APIRouter()


class PipelineConfig(BaseModel):
    query: str
    location: str = "Remote"
    auto_apply: bool = True
    min_match_score: int = 70


class PipelineStatus(BaseModel):
    running: bool
    current_agent: Optional[str] = None
    progress: int
    jobs_found: int
    jobs_applied: int



from src.core.redis_client import get_redis_client

# Define Redis key prefix for pipeline state
# Key format: pipeline:{user_id}:state

async def get_pipeline_state(user_id: str) -> dict:
    """Get or initialize state for a user from Redis."""
    try:
        redis = get_redis_client()
        key = f"pipeline:{user_id}:state"
        
        # Get all fields
        state = await redis.hgetall(key)
        
        if not state:
            # Initialize default state
            initial_state = {
                "running": "0",
                "current_agent": "None",
                "progress": "0",
                "jobs_found": "0",
                "jobs_applied": "0"
            }
            # Set multiple fields at once
            await redis.hset(key, mapping=initial_state)
            # Set expire time (e.g., 24 hours)
            await redis.expire(key, 86400)
            
            # Return proper types
            return {
                "running": False,
                "current_agent": None,
                "progress": 0,
                "jobs_found": 0,
                "jobs_applied": 0
            }
            
        # Convert types (Redis stores everything as strings)
        return {
            "running": state.get("running", "0") == "1",
            "current_agent": None if state.get("current_agent") == "None" else state.get("current_agent"),
            "progress": int(state.get("progress", 0)),
            "jobs_found": int(state.get("jobs_found", 0)),
            "jobs_applied": int(state.get("jobs_applied", 0))
        }
    except Exception as e:
        # Fallback in case Redis is down (so API doesn't crash completely)
        print(f"Redis Error: {e}")
        return {
           "running": False,
            "current_agent": None,
            "progress": 0,
            "jobs_found": 0,
            "jobs_applied": 0,
            "error": "Redis unavailable"
        }

async def update_pipeline_state(user_id: str, updates: dict):
    """Update specific fields in Redis state."""
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
    except Exception as e:
        print(f"Redis Update Error: {e}")

@router.get("/status")
async def get_pipeline_status(user: AuthUser = Depends(get_current_user)):
    """
    Get current pipeline status for the authenticated user.
    """
    return await get_pipeline_state(user.id)


@router.post("/start")
async def start_pipeline(config: PipelineConfig, user: AuthUser = Depends(get_current_user)):
    """
    Start the agentic pipeline for the authenticated user.
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
    
    return {
        "status": "started",
        "message": "Pipeline started successfully",
        "config": config.model_dump(),
    }


@router.post("/stop")
async def stop_pipeline(user: AuthUser = Depends(get_current_user)):
    """
    Stop the running pipeline.
    """
    await update_pipeline_state(user.id, {
        "running": False,
        "current_agent": None
    })
    
    return {
        "status": "stopped",
        "message": "Pipeline stopped",
    }


@router.post("/pause")
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



@router.websocket("/ws/{user_id}")
async def pipeline_websocket(websocket: WebSocket, user_id: str):
    """
    WebSocket endpoint for real-time pipeline updates.
    Secured via Token in Query Param.
    """
    # Extract token
    token = websocket.query_params.get("token")
    
    # Register with connection manager (handles Accept + Auth)
    from src.api.websocket import manager
    await manager.connect(websocket, user_id, token)
    
    try:
        while True:
            # Keep connection alive & listen for client messages (e.g. HITL responses)
            # The manager handles pushing events to this socket.
            # We can also start a background task to push Redis status updates if needed,
            # but ideally the Orchestrator pushes events.
            
            # For now, we can keep a simple heartbeat or command listener
            data = await websocket.receive_text()
            
            # Optional: Handle simple ping/pong or commands
            if data == "ping":
                await websocket.send_text("pong")
                
    except WebSocketDisconnect:
        manager.disconnect(user_id)


@router.post("/hitl/respond")
async def respond_to_hitl(response: dict, user: AuthUser = Depends(get_current_user)):
    """
    Respond to a Human-in-the-Loop prompt.
    """
    return {
        "status": "received",
        "message": "Response recorded, pipeline continuing",
    }
