"""
Feature flags with deterministic rollout.

Supports:
- global enable/disable
- percentage rollout
- explicit per-user allow lists
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Dict, Optional, Set


@dataclass
class FlagRule:
	name: str
	enabled: bool = False
	rollout_percentage: int = 0
	allow_users: Set[str] = field(default_factory=set)

	@classmethod
	def from_dict(cls, name: str, payload: Dict) -> 'FlagRule':
		return cls(
			name=name,
			enabled=bool(payload.get('enabled', False)),
			rollout_percentage=max(0, min(100, int(payload.get('rollout_percentage', 0)))),
			allow_users=set(payload.get('allow_users', []) or []),
		)


class FeatureFlagManager:
	"""
	Deterministic and lightweight feature-flag manager.

	Expected env format:
	FEATURE_FLAGS_JSON='{"flag_name":{"enabled":true,"rollout_percentage":20,"allow_users":["u1"]}}'
	"""

	def __init__(self):
		self._rules: Dict[str, FlagRule] = {}
		self.reload()

	def reload(self) -> None:
		raw = os.getenv('FEATURE_FLAGS_JSON', '').strip()
		self._rules.clear()
		if not raw:
			return
		try:
			parsed = json.loads(raw)
			for name, config in parsed.items():
				if isinstance(config, dict):
					self._rules[name] = FlagRule.from_dict(name, config)
		except Exception:
			# Fail-closed on malformed config
			self._rules.clear()

	def _in_rollout_bucket(self, key: str, rollout_percentage: int) -> bool:
		if rollout_percentage <= 0:
			return False
		if rollout_percentage >= 100:
			return True
		digest = hashlib.sha256(key.encode('utf-8')).hexdigest()
		bucket = int(digest[:8], 16) % 100
		return bucket < rollout_percentage

	def is_enabled(self, flag_name: str, user_id: Optional[str] = None, default: bool = False) -> bool:
		rule = self._rules.get(flag_name)
		if not rule:
			return default
		if user_id and user_id in rule.allow_users:
			return True
		if not rule.enabled:
			return False
		if not user_id:
			return rule.rollout_percentage > 0
		return self._in_rollout_bucket(f'{flag_name}:{user_id}', rule.rollout_percentage)

	def all_rules(self) -> Dict[str, Dict]:
		return {
			name: {
				'enabled': rule.enabled,
				'rollout_percentage': rule.rollout_percentage,
				'allow_users_count': len(rule.allow_users),
			}
			for name, rule in self._rules.items()
		}


feature_flags = FeatureFlagManager()
