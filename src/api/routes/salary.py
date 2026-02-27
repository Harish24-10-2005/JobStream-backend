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
# Salary Battle WebSocket — LangGraph State Machine
# ==================================================================
from src.services.salary_service import salary_service
from src.graphs.salary_battle_graph import run_battle_turn

@router.websocket("/ws/battle/{battle_id}")
async def salary_battle_websocket(websocket: WebSocket, battle_id: str):
    """
    Real-time Salary Negotiation Battle using LangGraph state machine.
    
    Each WebSocket message triggers one turn of the negotiation graph:
      evaluate_input → generate_response → evaluate_outcome
    
    State persists across turns for proper conversation flow.
    """
    await websocket.accept()
    
    try:
        # Initialize battle state (LangGraph typed state)
        battle_state = {
            "battle_id": battle_id,
            "role": "Senior Developer",
            "company": "TechCorp",
            "location": "San Francisco",
            "difficulty": "medium",
            "initial_offer": 120000,
            "current_offer": 120000,
            "target_salary": 150000,
            "best_offer_seen": 120000,
            "phase": "opening",
            "turn_count": 0,
            "max_turns": 10,
            "history": [],
            "user_input": "",
            "ai_response": "",
            "new_offer": None,
            "status": "active",
            "negotiation_score": 0,
            "tactics_used": [],
        }
        
        await websocket.send_json({
            "type": "battle:start",
            "battle_id": battle_id,
            "engine": "langgraph",
            "initial_offer": battle_state["initial_offer"],
            "target_salary": battle_state["target_salary"],
            "message": f"Connected to Negotiation Battle: {battle_id}",
        })
        
        while True:
            # 1. Receive user input
            data = await websocket.receive_text()
            
            # 2. Log user message
            await salary_service.log_message(battle_id, "user", data)
            
            # 3. Run one turn through LangGraph
            battle_state = await run_battle_turn(battle_state, data)
            
            # 4. Extract response
            ai_text = battle_state.get("ai_response", "")
            new_offer = battle_state.get("new_offer")
            status = battle_state.get("status", "active")
            
            # 5. Log AI response
            await salary_service.log_message(battle_id, "ai", ai_text, offer_amount=new_offer)
            
            # 6. Update DB if state changed
            if new_offer or status != "active":
                await salary_service.update_battle_status(battle_id, status, new_offer)
            
            # 7. Send response to client
            response = {
                "response_text": ai_text,
                "new_offer": new_offer,
                "status": status,
                "phase": battle_state.get("phase", "opening"),
                "turn_count": battle_state.get("turn_count", 0),
                "negotiation_score": battle_state.get("negotiation_score", 0),
                "tactics_used": battle_state.get("tactics_used", []),
                "best_offer": battle_state.get("best_offer_seen", 0),
            }
            await websocket.send_json(response)
            
            # 8. End battle if finished
            if status in ["won", "lost", "stalemate"]:
                await websocket.send_json({
                    "type": "battle:end",
                    "final_score": battle_state.get("negotiation_score", 0),
                    "final_offer": battle_state.get("current_offer", 0),
                    "status": status,
                })
                await websocket.close()
                break

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from salary battle {battle_id}")
    except Exception as e:
        logger.error(f"Salary battle WebSocket error: {e}")
        await websocket.close()
