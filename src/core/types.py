from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class AgentResponse(BaseModel):
	"""
	Standardized response envelope for AI agents.
	Ensures consistent error and success contracts across all agents.
	"""

	success: bool
	data: Optional[Dict[str, Any]] = None
	error: Optional[str] = None
	error_code: Optional[str] = None
	metadata: Optional[Dict[str, Any]] = None

	model_config = ConfigDict(extra='allow')

	@classmethod
	def create_success(cls, data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None, **kwargs) -> 'AgentResponse':
		"""Helper to create a success response."""
		return cls(success=True, data=data, error=None, error_code=None, metadata=metadata or {}, **kwargs)

	@classmethod
	def create_error(
		cls, message: str, code: str = 'AGENT_ERROR', data: Optional[Dict[str, Any]] = None, **kwargs
	) -> 'AgentResponse':
		"""Helper to create an error response."""
		return cls(success=False, data=data, error=message, error_code=code, **kwargs)
