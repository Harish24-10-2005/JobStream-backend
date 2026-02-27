"""
LLM Cost Tracker — Token Usage & Spend Monitoring

Tracks every LLM call's token consumption and estimated cost.
Supports per-agent budget enforcement and daily spend limits.

Pricing is configurable and defaults to approximate rates
for Groq, OpenRouter, and Gemini as of early 2025.

Usage:
    from src.core.cost_tracker import cost_tracker
    
    cost_tracker.record("resume_agent", "groq", "llama-3.1-8b", 500, 200)
    report = cost_tracker.get_daily_spend()
    ok = cost_tracker.check_budget("resume_agent")
"""

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# Approximate pricing per 1M tokens (USD) — update as providers change rates
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # Groq — free tier / very cheap
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-70b-versatile": {"input": 0.59, "output": 0.79},
    # OpenRouter — varies by model
    "qwen/qwen3-coder:free": {"input": 0.0, "output": 0.0},
    "deepseek/deepseek-chat": {"input": 0.14, "output": 0.28},
    "meta-llama/llama-3.1-8b-instruct:free": {"input": 0.0, "output": 0.0},
    # Gemini
    "gemini-2.0-flash-exp": {"input": 0.075, "output": 0.30},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
    # Mistral
    "mistral-small-2506": {"input": 0.10, "output": 0.30},
}

# Default pricing for unknown models
DEFAULT_PRICING = {"input": 0.50, "output": 1.00}


@dataclass
class CostRecord:
    """A single LLM invocation cost record."""
    agent_name: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    session_id: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentCostReport:
    """Aggregated cost report for a single agent."""
    agent_name: str
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    avg_cost_per_call: float
    models_used: List[str]


class CostTracker:
    """
    Tracks LLM token usage and costs across all agents.
    
    Records are kept in-memory for fast access and optionally
    persisted to Supabase for historical analysis.
    
    Supports:
      - Per-agent daily budgets
      - Global daily spend limits
      - Cost breakdown by agent/model/provider
    """

    def __init__(
        self,
        daily_budget_usd: float = 5.0,
        agent_budgets: Optional[Dict[str, float]] = None,
    ):
        self.daily_budget_usd = daily_budget_usd
        self.agent_budgets = agent_budgets or {}
        self._records: List[CostRecord] = []
        self._daily_totals: Dict[str, float] = defaultdict(float)  # agent -> USD
        self._last_reset: str = self._today()
        self._supabase = None

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _maybe_reset_daily(self):
        """Reset daily counters if the date has changed."""
        today = self._today()
        if today != self._last_reset:
            self._daily_totals.clear()
            self._last_reset = today
            logger.info("[CostTracker] Daily counters reset")

    @staticmethod
    def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost in USD for a given call."""
        pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 6)

    def record(
        self,
        agent_name: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        session_id: str = "",
    ) -> CostRecord:
        """
        Record a single LLM invocation's cost.
        
        Called automatically by UnifiedLLM after each call.
        Non-blocking — failures are logged, never raised.
        """
        self._maybe_reset_daily()

        cost = self.estimate_cost(model, input_tokens, output_tokens)
        record = CostRecord(
            agent_name=agent_name,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            session_id=session_id,
        )

        self._records.append(record)
        self._daily_totals[agent_name] += cost

        logger.debug(
            f"[CostTracker] {agent_name} | {provider}/{model} | "
            f"in={input_tokens} out={output_tokens} | ${cost:.6f}"
        )

        # Persist async (best-effort)
        self._persist(record)

        return record

    def _persist(self, record: CostRecord):
        """Persist cost record to Supabase (best-effort)."""
        if self._supabase is None:
            try:
                from src.services.supabase_client import supabase_client
                self._supabase = supabase_client
            except Exception:
                return

        try:
            self._supabase.table("llm_costs").insert({
                "agent_name": record.agent_name,
                "provider": record.provider,
                "model": record.model,
                "input_tokens": record.input_tokens,
                "output_tokens": record.output_tokens,
                "cost_usd": record.cost_usd,
                "session_id": record.session_id,
            }).execute()
        except Exception as e:
            logger.debug(f"[CostTracker] Failed to persist: {e}")

    # ── Budget Enforcement ──────────────────────────────────────

    def check_budget(self, agent_name: str) -> bool:
        """
        Check if an agent is within its daily budget.
        
        Returns True if the agent can proceed, False if budget exhausted.
        """
        self._maybe_reset_daily()

        agent_budget = self.agent_budgets.get(agent_name, self.daily_budget_usd)
        current_spend = self._daily_totals.get(agent_name, 0)

        if current_spend >= agent_budget:
            logger.warning(
                f"[CostTracker] Budget exceeded for {agent_name}: "
                f"${current_spend:.4f} >= ${agent_budget:.4f}"
            )
            return False
        return True

    def get_remaining_budget(self, agent_name: str) -> float:
        """Get remaining budget in USD for an agent today."""
        self._maybe_reset_daily()
        agent_budget = self.agent_budgets.get(agent_name, self.daily_budget_usd)
        spent = self._daily_totals.get(agent_name, 0)
        return max(0, agent_budget - spent)

    # ── Reporting ───────────────────────────────────────────────

    def get_daily_spend(self) -> Dict[str, Any]:
        """Get today's total spend breakdown."""
        self._maybe_reset_daily()
        total = sum(self._daily_totals.values())
        return {
            "date": self._today(),
            "total_usd": round(total, 4),
            "budget_usd": self.daily_budget_usd,
            "budget_remaining_usd": round(max(0, self.daily_budget_usd - total), 4),
            "by_agent": {k: round(v, 4) for k, v in self._daily_totals.items()},
        }

    def get_agent_report(self, agent_name: str) -> AgentCostReport:
        """Get detailed cost report for a specific agent."""
        agent_records = [r for r in self._records if r.agent_name == agent_name]

        if not agent_records:
            return AgentCostReport(
                agent_name=agent_name,
                total_calls=0,
                total_input_tokens=0,
                total_output_tokens=0,
                total_cost_usd=0,
                avg_cost_per_call=0,
                models_used=[],
            )

        total_cost = sum(r.cost_usd for r in agent_records)
        models = list(set(r.model for r in agent_records))

        return AgentCostReport(
            agent_name=agent_name,
            total_calls=len(agent_records),
            total_input_tokens=sum(r.input_tokens for r in agent_records),
            total_output_tokens=sum(r.output_tokens for r in agent_records),
            total_cost_usd=round(total_cost, 4),
            avg_cost_per_call=round(total_cost / len(agent_records), 6),
            models_used=models,
        )

    def get_full_breakdown(self) -> Dict[str, Any]:
        """Get a complete cost breakdown across all agents and models."""
        by_agent: Dict[str, float] = defaultdict(float)
        by_model: Dict[str, float] = defaultdict(float)
        by_provider: Dict[str, float] = defaultdict(float)

        for r in self._records:
            by_agent[r.agent_name] += r.cost_usd
            by_model[r.model] += r.cost_usd
            by_provider[r.provider] += r.cost_usd

        total_tokens_in = sum(r.input_tokens for r in self._records)
        total_tokens_out = sum(r.output_tokens for r in self._records)

        return {
            "total_calls": len(self._records),
            "total_cost_usd": round(sum(r.cost_usd for r in self._records), 4),
            "total_input_tokens": total_tokens_in,
            "total_output_tokens": total_tokens_out,
            "by_agent": {k: round(v, 4) for k, v in by_agent.items()},
            "by_model": {k: round(v, 4) for k, v in by_model.items()},
            "by_provider": {k: round(v, 4) for k, v in by_provider.items()},
        }

    def stats(self) -> Dict[str, Any]:
        """Return tracker stats for health checks."""
        return {
            "total_records": len(self._records),
            "daily_spend": self.get_daily_spend(),
        }


# ── Singleton ───────────────────────────────────────────────────

cost_tracker = CostTracker()
