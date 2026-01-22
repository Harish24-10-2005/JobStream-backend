"""
Chat API Routes
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
import datetime

from services.chat_orchestrator import chat_orchestrator

router = APIRouter()

class ChatMessage(BaseModel):
    content: str
    session_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    id: str
    role: str
    content: str
    intent: Optional[Dict[str, Any]] = None # The canvas command
    timestamp: str

@router.post("/message", response_model=ChatResponse)
async def send_message(message: ChatMessage):
    """
    Send a message to the AI assistant.
    The Orchestrator determines if a Canvas Action is needed.
    """
    try:
        # 1. Determine Intent
        intent = await chat_orchestrator.determine_intent(message.content)
        
        # 2. Return Response with Intent Data
        # The frontend will read 'intent' and switch the active Canvas accordingly
        
        return {
            "id": "msg_" + str(hash(message.content))[-8:],
            "role": "assistant",
            "content": intent.response_text,
            "intent": {
                "action": intent.action,
                "parameters": intent.parameters
            },
            "timestamp": datetime.datetime.now().strftime("%I:%M %p"),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
