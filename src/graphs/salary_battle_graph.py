"""
LangGraph Salary Battle Graph — Turn-Based Negotiation State Machine

A stateful negotiation graph where each turn follows:
  receive_input → evaluate_move → generate_response → update_state

Features:
  - Turn-based state transitions
  - Configurable difficulty (easy/medium/hard)
  - Offer tracking with negotiation history
  - Win/loss condition evaluation
  - Persistence via LangGraph checkpointing
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ─── State Schema ───────────────────────────────────────────────

class BattlePhase(str, Enum):
    OPENING = "opening"
    COUNTER = "counter"
    OBJECTION_HANDLING = "objection_handling"
    FINAL_OFFER = "final_offer"
    CLOSED = "closed"


class NegotiationTurn(BaseModel):
    """A single turn in the negotiation."""
    turn_number: int = 0
    speaker: str = ""  # "user" or "ai"
    message: str = ""
    offer_amount: Optional[int] = None
    timestamp: str = ""


class SalaryBattleState(BaseModel):
    """
    Typed state for salary negotiation battle.
    """
    # --- Battle Config ---
    battle_id: str = ""
    role: str = ""
    company: str = ""
    location: str = ""
    difficulty: str = "medium"  # easy, medium, hard

    # --- Offer Tracking ---
    initial_offer: int = 0
    current_offer: int = 0
    target_salary: int = 0
    user_counter: Optional[int] = None
    best_offer_seen: int = 0

    # --- Negotiation State ---
    phase: str = BattlePhase.OPENING
    turn_count: int = 0
    max_turns: int = 10
    history: List[Dict[str, Any]] = Field(default_factory=list)

    # --- Current Turn ---
    user_input: str = ""
    ai_response: str = ""
    new_offer: Optional[int] = None
    status: str = "active"  # active, won, lost, stalemate

    # --- Scoring ---
    negotiation_score: int = 0  # 0-100 performance score
    tactics_used: List[str] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True


# ─── Node Functions ─────────────────────────────────────────────

async def evaluate_user_input_node(state: dict) -> dict:
    """Parse and evaluate the user's negotiation move."""
    user_input = state.get("user_input", "")
    turn_count = state.get("turn_count", 0) + 1
    history = state.get("history", [])

    # Record user turn
    turn = {
        "turn_number": turn_count,
        "speaker": "user",
        "message": user_input,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    history.append(turn)

    # Determine current phase based on turn count
    phase = state.get("phase", BattlePhase.OPENING)
    if turn_count <= 2:
        phase = BattlePhase.OPENING
    elif turn_count <= 5:
        phase = BattlePhase.COUNTER
    elif turn_count <= 8:
        phase = BattlePhase.OBJECTION_HANDLING
    else:
        phase = BattlePhase.FINAL_OFFER

    return {
        "turn_count": turn_count,
        "history": history,
        "phase": phase,
    }


async def generate_ai_response_node(state: dict) -> dict:
    """Generate the AI negotiator's response using the salary agent."""
    from src.agents.salary_agent import salary_agent

    history = state.get("history", [])
    user_input = state.get("user_input", "")

    battle_context = {
        "id": state.get("battle_id", ""),
        "role": state.get("role", ""),
        "company": state.get("company", ""),
        "initial_offer": state.get("initial_offer", 0),
        "current_offer": state.get("current_offer", 0),
        "target_salary": state.get("target_salary", 0),
        "difficulty": state.get("difficulty", "medium"),
        "phase": state.get("phase", BattlePhase.OPENING),
        "turn_count": state.get("turn_count", 0),
    }

    try:
        response = await salary_agent.negotiate_interactive(
            history=history,
            user_input=user_input,
            battle_context=battle_context,
        )

        ai_text = response.get("response_text", "")
        new_offer = response.get("new_offer")
        status = response.get("status", "active")

        # Track AI turn
        ai_turn = {
            "turn_number": state.get("turn_count", 0),
            "speaker": "ai",
            "message": ai_text,
            "offer_amount": new_offer,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        history_updated = state.get("history", []) + [ai_turn]

        # Detect tactics used
        tactics = state.get("tactics_used", [])
        if "anchor" in ai_text.lower():
            tactics.append("anchoring")
        if "market" in ai_text.lower() or "industry" in ai_text.lower():
            tactics.append("market_data")
        if "competing" in ai_text.lower() or "alternative" in ai_text.lower():
            tactics.append("competing_offers")

        return {
            "ai_response": ai_text,
            "new_offer": new_offer,
            "status": status,
            "history": history_updated,
            "current_offer": new_offer if new_offer else state.get("current_offer", 0),
            "best_offer_seen": max(
                state.get("best_offer_seen", 0),
                new_offer or 0
            ),
            "tactics_used": list(set(tactics)),
        }
    except Exception as e:
        logger.error(f"AI response generation failed: {e}")
        return {
            "ai_response": f"Let me reconsider... (Error occurred, please continue)",
            "status": "active",
        }


async def evaluate_outcome_node(state: dict) -> dict:
    """Evaluate if the battle is over and calculate score."""
    status = state.get("status", "active")
    turn_count = state.get("turn_count", 0)
    max_turns = state.get("max_turns", 10)
    initial_offer = state.get("initial_offer", 0)
    current_offer = state.get("current_offer", 0)
    target_salary = state.get("target_salary", 0)

    # Force end if max turns reached
    if turn_count >= max_turns and status == "active":
        status = "stalemate"

    # Calculate negotiation score (0-100)
    score = 0
    if initial_offer > 0 and target_salary > initial_offer:
        improvement = current_offer - initial_offer
        possible_improvement = target_salary - initial_offer
        score = min(100, int((improvement / max(possible_improvement, 1)) * 100))
    
    # Bonus for finishing quickly
    if status == "won" and turn_count <= 5:
        score = min(100, score + 15)

    # Update phase if closed
    phase = state.get("phase", BattlePhase.OPENING)
    if status in ("won", "lost", "stalemate"):
        phase = BattlePhase.CLOSED

    return {
        "status": status,
        "negotiation_score": max(0, score),
        "phase": phase,
    }


# ─── Conditional Edge Functions ─────────────────────────────────

def should_continue_battle(state: dict) -> str:
    """After outcome evaluation, check if battle continues."""
    status = state.get("status", "active")
    if status in ("won", "lost", "stalemate"):
        return "end"
    return "wait_for_input"


# ─── Graph Construction ────────────────────────────────────────

def create_salary_battle_graph() -> StateGraph:
    """
    Build the salary negotiation battle graph.

    Flow:
        evaluate_input → generate_response → evaluate_outcome → [loop or end]
    """
    graph = StateGraph(dict)

    # ── Add Nodes ──
    graph.add_node("evaluate_input", evaluate_user_input_node)
    graph.add_node("generate_response", generate_ai_response_node)
    graph.add_node("evaluate_outcome", evaluate_outcome_node)

    # ── Entry Point ──
    graph.set_entry_point("evaluate_input")

    # ── Edges ──
    graph.add_edge("evaluate_input", "generate_response")
    graph.add_edge("generate_response", "evaluate_outcome")

    graph.add_conditional_edges("evaluate_outcome", should_continue_battle, {
        "wait_for_input": END,  # Returns to caller for next WebSocket message
        "end": END,
    })

    return graph.compile()


# ─── Turn Runner ────────────────────────────────────────────────

async def run_battle_turn(
    battle_state: dict,
    user_input: str,
) -> dict:
    """
    Execute one turn of the salary battle.
    
    Args:
        battle_state: Current state dict (persisted between turns)
        user_input: The user's message
    
    Returns:
        Updated state dict with AI response
    """
    graph = create_salary_battle_graph()

    # Inject user input into state
    battle_state["user_input"] = user_input

    # Run one turn
    result = battle_state.copy()
    async for step in graph.astream(battle_state, stream_mode="updates"):
        for node_name, node_output in step.items():
            if isinstance(node_output, dict):
                result.update(node_output)

    return result
