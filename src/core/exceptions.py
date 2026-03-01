"""
Custom Exceptions for JobAI
Provides structured error handling across the application
"""

from typing import Any, Dict, Optional


class JobAIException(Exception):
	"""Base exception for all JobAI errors."""

	def __init__(
		self, message: str, code: str = 'INTERNAL_ERROR', details: Optional[Dict[str, Any]] = None, status_code: int = 500
	):
		super().__init__(message)
		self.message = message
		self.code = code
		self.details = details or {}
		self.status_code = status_code

	def to_dict(self) -> Dict[str, Any]:
		"""Convert exception to API response format."""
		return {'error': True, 'code': self.code, 'message': self.message, 'details': self.details}


class ValidationError(JobAIException):
	"""Invalid input data."""

	def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict] = None):
		super().__init__(message=message, code='VALIDATION_ERROR', details={'field': field, **(details or {})}, status_code=400)


class NotFoundError(JobAIException):
	"""Resource not found."""

	def __init__(self, resource: str, identifier: str):
		super().__init__(
			message=f'{resource} not found: {identifier}',
			code='NOT_FOUND',
			details={'resource': resource, 'identifier': identifier},
			status_code=404,
		)


class DatabaseError(JobAIException):
	"""Database operation failed."""

	def __init__(self, message: str, operation: Optional[str] = None, details: Optional[Dict] = None):
		super().__init__(
			message=message, code='DATABASE_ERROR', details={'operation': operation, **(details or {})}, status_code=500
		)


class AgentError(JobAIException):
	"""AI Agent operation failed."""

	def __init__(self, agent: str, message: str, details: Optional[Dict] = None):
		super().__init__(
			message=f"Agent '{agent}' failed: {message}",
			code='AGENT_ERROR',
			details={'agent': agent, **(details or {})},
			status_code=500,
		)


class LLMError(JobAIException):
	"""LLM provider error."""

	def __init__(self, provider: str, message: str, is_rate_limit: bool = False):
		super().__init__(
			message=f'LLM error ({provider}): {message}',
			code='RATE_LIMIT_ERROR' if is_rate_limit else 'LLM_ERROR',
			details={'provider': provider, 'is_rate_limit': is_rate_limit},
			status_code=429 if is_rate_limit else 502,
		)


class AuthenticationError(JobAIException):
	"""Authentication failed."""

	def __init__(self, message: str = 'Authentication required'):
		super().__init__(message=message, code='AUTHENTICATION_ERROR', status_code=401)


class AuthorizationError(JobAIException):
	"""Authorization failed."""

	def __init__(self, message: str = 'Access denied'):
		super().__init__(message=message, code='AUTHORIZATION_ERROR', status_code=403)


class RateLimitError(JobAIException):
	"""Rate limit exceeded."""

	def __init__(self, retry_after: int = 60):
		super().__init__(
			message='Rate limit exceeded. Please try again later.',
			code='RATE_LIMIT_ERROR',
			details={'retry_after': retry_after},
			status_code=429,
		)


class ExternalServiceError(JobAIException):
	"""External service (API) error."""

	def __init__(self, service: str, message: str, status_code: int = 502):
		super().__init__(
			message=f'External service error ({service}): {message}',
			code='EXTERNAL_SERVICE_ERROR',
			details={'service': service},
			status_code=status_code,
		)
