"""
Analytics API Routes — Dashboard, Agent Performance, Cost Tracking

Provides endpoints for monitoring system health, agent performance,
LLM costs, and user career analytics.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from src.core.auth import get_current_user, AuthUser
from src.core.cost_tracker import cost_tracker
from src.core.agent_memory import agent_memory
from src.core.retry_budget import retry_budget

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(user: AuthUser = Depends(get_current_user)):
    """
    Aggregate dashboard stats — applications, agent performance, costs.
    """
    # Collect feedback summaries for all agents
    agents = [
        "scout_agent", "analyst_agent", "resume_agent",
        "cover_letter_agent", "interview_agent", "salary_agent",
        "company_agent", "network_agent",
    ]
    agent_ratings = {}
    for agent in agents:
        summary = await agent_memory.get_feedback_summary(agent, user.id)
        if summary["total"] > 0:
            agent_ratings[agent] = {
                "avg_rating": summary["avg_rating"],
                "total_feedback": summary["total"],
            }

    # Cost summary
    daily_spend = cost_tracker.get_daily_spend()

    return {
        "agent_ratings": agent_ratings,
        "cost_summary": daily_spend,
        "memory_stats": agent_memory.stats(),
        "system_health": {
            "retry_budget": retry_budget.stats(),
        },
    }


@router.get("/agent-performance")
async def get_agent_performance(user: AuthUser = Depends(get_current_user)):
    """Per-agent performance metrics — success rates, latency, cost."""
    agents = [
        "scout_agent", "analyst_agent", "resume_agent",
        "cover_letter_agent", "interview_agent", "salary_agent",
        "company_agent", "network_agent",
    ]

    performance = {}
    for agent in agents:
        cost_report = cost_tracker.get_agent_report(agent)
        feedback = await agent_memory.get_feedback_summary(agent, user.id)

        performance[agent] = {
            "total_llm_calls": cost_report.total_calls,
            "total_cost_usd": cost_report.total_cost_usd,
            "avg_cost_per_call": cost_report.avg_cost_per_call,
            "models_used": cost_report.models_used,
            "total_input_tokens": cost_report.total_input_tokens,
            "total_output_tokens": cost_report.total_output_tokens,
            "user_rating": feedback["avg_rating"],
            "feedback_count": feedback["total"],
        }

    return {"agents": performance}


@router.get("/costs")
async def get_cost_breakdown(user: AuthUser = Depends(get_current_user)):
    """LLM cost breakdown by agent, model, and provider."""
    return {
        "daily": cost_tracker.get_daily_spend(),
        "breakdown": cost_tracker.get_full_breakdown(),
    }


@router.get("/costs/{agent_name}")
async def get_agent_cost(
    agent_name: str,
    user: AuthUser = Depends(get_current_user),
):
    """Get detailed cost report for a specific agent."""
    from dataclasses import asdict
    report = cost_tracker.get_agent_report(agent_name)
    return asdict(report)


@router.get("/retry-health")
async def get_retry_health(user: AuthUser = Depends(get_current_user)):
    """Get retry budget health for all tracked services."""
    return {"services": retry_budget.get_all_health()}


@router.get("/memory/{agent_name}")
async def get_agent_memories(
    agent_name: str,
    user: AuthUser = Depends(get_current_user),
    limit: int = 20,
):
    """Get stored memories for an agent (user-scoped)."""
    memories = await agent_memory.recall_all(agent_name, user.id, limit=limit)
    learnings = await agent_memory.get_learnings(agent_name, user.id)
    return {
        "agent": agent_name,
        "memories": memories,
        "learnings": learnings,
        "total": len(memories),
    }


@router.get("/system-health")
async def get_system_health(user: AuthUser = Depends(get_current_user)):
    """Comprehensive system health check."""
    return {
        "memory": agent_memory.stats(),
        "costs": cost_tracker.stats(),
        "retry_budget": retry_budget.stats(),
    }
