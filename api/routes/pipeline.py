"""
Pipeline API Routes
"""
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional
import asyncio
import json

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


# In-memory state (would be Redis in production)
pipeline_state = {
    "running": False,
    "current_agent": None,
    "progress": 0,
    "jobs_found": 0,
    "jobs_applied": 0,
}


@router.get("/status")
async def get_pipeline_status():
    """
    Get current pipeline status.
    """
    return pipeline_state


@router.post("/start")
async def start_pipeline(config: PipelineConfig):
    """
    Start the agentic pipeline.
    """
    global pipeline_state
    
    if pipeline_state["running"]:
        raise HTTPException(status_code=400, detail="Pipeline is already running")
    
    pipeline_state["running"] = True
    pipeline_state["current_agent"] = "scout"
    pipeline_state["progress"] = 0
    
    return {
        "status": "started",
        "message": "Pipeline started successfully",
        "config": config.model_dump(),
    }


@router.post("/stop")
async def stop_pipeline():
    """
    Stop the running pipeline.
    """
    global pipeline_state
    
    pipeline_state["running"] = False
    pipeline_state["current_agent"] = None
    
    return {
        "status": "stopped",
        "message": "Pipeline stopped",
    }


@router.post("/pause")
async def pause_pipeline():
    """
    Pause the running pipeline.
    """
    global pipeline_state
    
    if not pipeline_state["running"]:
        raise HTTPException(status_code=400, detail="Pipeline is not running")
    
    pipeline_state["running"] = False
    
    return {
        "status": "paused",
        "message": "Pipeline paused",
    }


@router.websocket("/ws")
async def pipeline_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time pipeline updates.
    """
    await websocket.accept()
    try:
        while True:
            # Send pipeline status updates
            await websocket.send_json({
                "type": "status",
                "data": pipeline_state,
            })
            
            # Also send mock log updates
            await websocket.send_json({
                "type": "log",
                "data": {
                    "agent": "Scout",
                    "message": "Searching for jobs...",
                    "timestamp": "10:24:15",
                },
            })
            
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass


@router.post("/hitl/respond")
async def respond_to_hitl(response: dict):
    """
    Respond to a Human-in-the-Loop prompt.
    """
    return {
        "status": "received",
        "message": "Response recorded, pipeline continuing",
    }
