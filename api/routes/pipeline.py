"""
Pipeline API Routes
"""
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel
from typing import Optional, Dict
import asyncio
import json

from api.routes.jobs import get_current_user
from api.routes.jobs import get_current_user
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


# In-memory state keyed by user_id
# pipeline_states[user_id] = { ... }
pipeline_states: Dict[str, dict] = {}


def get_pipeline_state(user_id: str) -> dict:
    """Get or initialize state for a user."""
    if user_id not in pipeline_states:
        pipeline_states[user_id] = {
            "running": False,
            "current_agent": None,
            "progress": 0,
            "jobs_found": 0,
            "jobs_applied": 0,
        }
    return pipeline_states[user_id]


@router.get("/status")
async def get_pipeline_status(user: AuthUser = Depends(get_current_user)):
    """
    Get current pipeline status for the authenticated user.
    """
    return get_pipeline_state(user.id)


@router.post("/start")
async def start_pipeline(config: PipelineConfig, user: AuthUser = Depends(get_current_user)):
    """
    Start the agentic pipeline for the authenticated user.
    """
    state = get_pipeline_state(user.id)
    
    if state["running"]:
        raise HTTPException(status_code=400, detail="Pipeline is already running")
    
    state["running"] = True
    state["current_agent"] = "scout"
    state["progress"] = 0
    state["jobs_found"] = 0
    state["jobs_applied"] = 0
    
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
    state = get_pipeline_state(user.id)
    
    state["running"] = False
    state["current_agent"] = None
    
    return {
        "status": "stopped",
        "message": "Pipeline stopped",
    }


@router.post("/pause")
async def pause_pipeline(user: AuthUser = Depends(get_current_user)):
    """
    Pause the running pipeline.
    """
    state = get_pipeline_state(user.id)
    
    if not state["running"]:
        raise HTTPException(status_code=400, detail="Pipeline is not running")
    
    state["running"] = False
    
    return {
        "status": "paused",
        "message": "Pipeline paused",
    }


@router.websocket("/ws/{user_id}")
async def pipeline_websocket(websocket: WebSocket, user_id: str):
    """
    WebSocket endpoint for real-time pipeline updates.
    Note: In production, use a token in query param for secure Auth logic here.
    """
    await websocket.accept()
    try:
        while True:
            # Send pipeline status updates for specific user
            state = get_pipeline_state(user_id)
            await websocket.send_json({
                "type": "status",
                "data": state,
            })
            
            # Mock log - in reality, listen to user-specific Redis channel
            if state["running"]:
                await websocket.send_json({
                    "type": "log",
                    "data": {
                        "agent": state.get("current_agent", "System"),
                        "message": "Processing...",
                        "timestamp": "Now",
                    },
                })
            
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass


@router.post("/hitl/respond")
async def respond_to_hitl(response: dict, user: AuthUser = Depends(get_current_user)):
    """
    Respond to a Human-in-the-Loop prompt.
    """
    return {
        "status": "received",
        "message": "Response recorded, pipeline continuing",
    }
