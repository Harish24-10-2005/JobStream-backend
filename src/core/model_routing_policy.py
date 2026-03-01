"""
Policy-first model routing concepts for production AI systems.

This module is provider-agnostic and gives:
- deterministic tier selection
- budget-aware routing
- latency-aware overrides
"""

from dataclasses import dataclass
from enum import Enum


class ModelTier(str, Enum):
	CHEAP = 'cheap'
	BALANCED = 'balanced'
	PREMIUM = 'premium'


class TaskComplexity(str, Enum):
	LOW = 'low'
	MEDIUM = 'medium'
	HIGH = 'high'


@dataclass
class RoutingDecision:
	tier: ModelTier
	temperature: float
	max_tokens: int
	reason: str


class ModelRoutingPolicy:
	"""
	Reference policy aligned with production constraints.

	Inputs:
	- complexity (task difficulty)
	- budget_remaining_usd (hard cost guardrail)
	- latency_sensitive (interactive workloads)
	- requires_grounding (facts/evidence-heavy workload)
	"""

	def choose(
		self,
		complexity: TaskComplexity,
		budget_remaining_usd: float,
		latency_sensitive: bool = False,
		requires_grounding: bool = False,
	) -> RoutingDecision:
		if budget_remaining_usd <= 0.01:
			return RoutingDecision(
				tier=ModelTier.CHEAP,
				temperature=0.2,
				max_tokens=1200,
				reason='Budget protection mode',
			)

		if latency_sensitive and complexity != TaskComplexity.HIGH:
			return RoutingDecision(
				tier=ModelTier.CHEAP,
				temperature=0.2,
				max_tokens=1500,
				reason='Latency-sensitive path',
			)

		if complexity == TaskComplexity.HIGH or requires_grounding:
			return RoutingDecision(
				tier=ModelTier.PREMIUM,
				temperature=0.1 if requires_grounding else 0.3,
				max_tokens=3500,
				reason='High-complexity or grounding-heavy task',
			)

		if complexity == TaskComplexity.MEDIUM:
			return RoutingDecision(
				tier=ModelTier.BALANCED,
				temperature=0.3,
				max_tokens=2500,
				reason='Balanced default for medium complexity',
			)

		return RoutingDecision(
			tier=ModelTier.CHEAP,
			temperature=0.4,
			max_tokens=1800,
			reason='Low complexity default',
		)


model_routing_policy = ModelRoutingPolicy()
