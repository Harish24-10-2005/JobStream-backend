"""
Salary Negotiation Routes
"""
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List, Dict
import logging

from src.agents.salary_agent import salary_agent
from src.core.auth import get_current_user, AuthUser
from src.api.schemas import SalaryResearchResponse, SalaryNegotiationResponse

router = APIRouter()
logger = logging.getLogger(__name__)

class SalaryResearchRequest(BaseModel):
    role: str
    location: str
    experience_years: int = 3

class SalaryNegotiationRequest(BaseModel):
    role: str
    location: str
    current_offer: int
    bonus: int = 0
    equity: int = 0
    experience_years: int = 3
    competing_offers: Optional[List[int]] = None

@router.post("/research", response_model=SalaryResearchResponse)
async def research_salary(
    request: SalaryResearchRequest,
    user: AuthUser = Depends(get_current_user)
):
    """
    Research market salary for a role.
    """
    try:
        result = await salary_agent.research_salary(
            role=request.role,
            location=request.location,
            experience_years=request.experience_years
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/negotiate", response_model=SalaryNegotiationResponse)
async def negotiate_offer(
    request: SalaryNegotiationRequest,
    user: AuthUser = Depends(get_current_user)
):
    """
    Generate negotiation strategy for an offer.
    """
    try:
        result = await salary_agent.negotiate_offer(
            role=request.role,
            location=request.location,
            current_offer=request.current_offer,
            bonus=request.bonus,
            equity=request.equity,
            experience_years=request.experience_years,
            competing_offers=request.competing_offers
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================================================================
# NEW: Salary Battle WebSocket
# ==================================================================
from src.services.salary_service import salary_service

@router.websocket("/ws/battle/{battle_id}")
async def salary_battle_websocket(websocket: WebSocket, battle_id: str):
    """
    Real-time Salary Negotiation Battle.
    """
    await websocket.accept()
    
    try:
        # 1. Fetch Battle Context (Mock for MVP if DB fail)
        # battle = await salary_service.get_battle(battle_id)
        # For now, we construct context from query params or defaulting
        battle_context = {
            "id": battle_id,
            "role": "Senior Developer",
            "initial_offer": 120000,
            "current_offer": 120000,
            "target_salary": 150000,
            "difficulty": "medium",
            "company": "TechCorp"
        }
        
        await websocket.send_text(f"Connected to Negotiation Battle: {battle_id}")
        
        while True:
            # 1. Receive User Input
            data = await websocket.receive_text()
            
            # 2. Log User Message
            await salary_service.log_message(battle_id, "user", data)
            
            # 3. Get History
            history = await salary_service.get_battle_history(battle_id)
            
            # 4. Agent Move
            response = await salary_agent.negotiate_interactive(
                history=history,
                user_input=data,
                battle_context=battle_context
            )
            
            # 5. Connect Updates
            new_offer = response.get("new_offer")
            status = response.get("status")
            text = response.get("response_text")
            
            # Update local context for next turn
            if new_offer:
                battle_context["current_offer"] = new_offer
            
            # Log AI response
            await salary_service.log_message(battle_id, "ai", text, offer_amount=new_offer)
            
            # Update Battle Status in DB
            if new_offer or status != "active":
                await salary_service.update_battle_status(battle_id, status, new_offer)
            
            # 6. Send to Client
            await websocket.send_json(response)
            
            if status in ["won", "lost"]:
                await websocket.close()
                break

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from salary battle {battle_id}")
    except Exception as e:
        logger.error(f"Salary battle WebSocket error: {e}")
        await websocket.close()
